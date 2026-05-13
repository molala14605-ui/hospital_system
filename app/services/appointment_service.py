import logging
from datetime import datetime, timedelta, timezone
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import Appointment, AppointmentStatus, Doctor, Patient, UserRole
from app.schemas.appointment import AppointmentCreate
from app.services.cache import cache_service

logger = logging.getLogger(__name__)


def ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_slot_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Normalize to UTC and enforce duration + past + max length rules."""
    settings = get_settings()
    start = ensure_aware_utc(start)
    end = ensure_aware_utc(end)
    if end <= start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_time must be after start_time")
    duration = end - start
    min_len = timedelta(minutes=settings.min_appointment_minutes)
    if duration < min_len:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointment must be at least {settings.min_appointment_minutes} minutes",
        )
    max_len = timedelta(hours=settings.max_appointment_hours)
    if duration > max_len:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Appointment cannot exceed {settings.max_appointment_hours} hours",
        )
    now = datetime.now(timezone.utc)
    grace = timedelta(seconds=settings.booking_past_grace_seconds)
    if start < now - grace:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book or reschedule in the past",
        )
    return start, end


def _overlap_clause(doctor_id: int, start, end):
    return (
        Appointment.doctor_id == doctor_id,
        Appointment.status != AppointmentStatus.CANCELLED.value,
        Appointment.start_time < end,
        Appointment.end_time > start,
    )


def has_overlap(db: Session, doctor_id: int, start, end, exclude_appointment_id: int | None = None) -> bool:
    q = db.query(Appointment).filter(*_overlap_clause(doctor_id, start, end))
    if exclude_appointment_id is not None:
        q = q.filter(Appointment.id != exclude_appointment_id)
    return q.first() is not None


def _appointments_filtered_query(db: Session, doctor_id: int | None, patient_id: int | None):
    q = db.query(Appointment)
    if doctor_id is not None:
        q = q.filter(Appointment.doctor_id == doctor_id)
    if patient_id is not None:
        q = q.filter(Appointment.patient_id == patient_id)
    return q


def list_appointments_page(
    db: Session,
    *,
    doctor_id: int | None = None,
    patient_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[Sequence[Appointment], int]:
    total = _appointments_filtered_query(db, doctor_id, patient_id).count()
    items = (
        _appointments_filtered_query(db, doctor_id, patient_id)
        .options(joinedload(Appointment.doctor), joinedload(Appointment.patient))
        .order_by(Appointment.start_time.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_appointment(db: Session, appointment_id: int) -> Appointment | None:
    return (
        db.query(Appointment)
        .options(joinedload(Appointment.doctor), joinedload(Appointment.patient))
        .filter(Appointment.id == appointment_id)
        .first()
    )


def create_appointment(db: Session, patient: Patient, data: AppointmentCreate) -> Appointment:
    start, end = validate_slot_window(data.start_time, data.end_time)
    if has_overlap(db, data.doctor_id, start, end):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor already has an appointment in this time slot",
        )
    ap = Appointment(
        doctor_id=data.doctor_id,
        patient_id=patient.id,
        start_time=start,
        end_time=end,
        reason=data.reason,
        status=AppointmentStatus.SCHEDULED.value,
    )
    db.add(ap)
    db.commit()
    db.refresh(ap)
    logger.info("Appointment created id=%s doctor=%s patient=%s", ap.id, ap.doctor_id, ap.patient_id)
    cache_service.invalidate_appointment_lists()
    return ap


def reschedule_appointment(
    db: Session,
    appointment: Appointment,
    *,
    start_time: datetime,
    end_time: datetime,
    new_doctor_id: int | None,
    actor_role: str,
    patient: Patient | None,
    doctor: Doctor | None,
) -> Appointment:
    if appointment.status != AppointmentStatus.SCHEDULED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only scheduled appointments can be rescheduled",
        )

    target_doctor_id = appointment.doctor_id
    if new_doctor_id is not None:
        if actor_role != UserRole.ADMIN.value:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can reassign doctor")
        if new_doctor_id != appointment.doctor_id and not db.get(Doctor, new_doctor_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        target_doctor_id = new_doctor_id

    if actor_role == UserRole.PATIENT.value:
        if not patient or appointment.patient_id != patient.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your appointment")
        if new_doctor_id is not None and new_doctor_id != appointment.doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patients cannot change doctor")
    elif actor_role == UserRole.DOCTOR.value:
        if not doctor or appointment.doctor_id != doctor.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your appointment")
        if new_doctor_id is not None and new_doctor_id != appointment.doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctors cannot reassign to another doctor")
    elif actor_role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    start, end = validate_slot_window(start_time, end_time)
    if has_overlap(db, target_doctor_id, start, end, exclude_appointment_id=appointment.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor already has an appointment in this time slot",
        )

    appointment.start_time = start
    appointment.end_time = end
    appointment.doctor_id = target_doctor_id
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    logger.info("Appointment rescheduled id=%s doctor=%s", appointment.id, appointment.doctor_id)
    cache_service.invalidate_appointment_lists()
    return appointment


def update_appointment_status(
    db: Session,
    appointment: Appointment,
    new_status: str,
    *,
    actor_role: str,
) -> Appointment:
    current = appointment.status
    allowed = False
    if actor_role == UserRole.ADMIN.value:
        allowed = True
    elif actor_role == UserRole.DOCTOR.value:
        if new_status == AppointmentStatus.COMPLETED.value:
            allowed = current == AppointmentStatus.SCHEDULED.value
        elif new_status == AppointmentStatus.CANCELLED.value:
            allowed = current == AppointmentStatus.SCHEDULED.value
        else:
            allowed = False
    elif actor_role == UserRole.PATIENT.value:
        allowed = new_status == AppointmentStatus.CANCELLED.value and current == AppointmentStatus.SCHEDULED.value

    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to set this status")

    if new_status == AppointmentStatus.COMPLETED.value and current != AppointmentStatus.SCHEDULED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only complete a scheduled appointment")
    if new_status == AppointmentStatus.CANCELLED.value and current == AppointmentStatus.COMPLETED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot cancel a completed appointment")

    appointment.status = new_status
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    logger.info("Appointment status updated id=%s status=%s", appointment.id, new_status)
    cache_service.invalidate_appointment_lists()
    return appointment


def delete_appointment(db: Session, appointment: Appointment) -> None:
    aid = appointment.id
    db.delete(appointment)
    db.commit()
    logger.warning("Appointment deleted id=%s", aid)
    cache_service.invalidate_appointment_lists()

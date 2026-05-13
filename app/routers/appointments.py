from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, get_patient_profile, require_roles
from app.models import Doctor, Patient, User, UserRole
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentResponse,
    AppointmentUpdateStatus,
    PaginatedAppointments,
)
from app.services import appointment_service

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _to_response(ap) -> AppointmentResponse:
    return AppointmentResponse.model_validate(ap)


@router.get("", response_model=PaginatedAppointments)
def list_appointments(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
    doctor_id: int | None = Query(None),
    patient_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
) -> PaginatedAppointments:
    settings = get_settings()
    ps = page_size if page_size is not None else settings.appointments_default_page_size
    ps = min(ps, settings.appointments_max_page_size)

    if current.role == UserRole.ADMIN.value:
        d, p = doctor_id, patient_id
    elif current.role == UserRole.DOCTOR.value:
        doc = db.query(Doctor).filter(Doctor.user_id == current.id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Doctor profile not found")
        if doctor_id is not None and doctor_id != doc.id:
            raise HTTPException(status_code=403, detail="Can only view own schedule")
        d, p = doc.id, patient_id
    elif current.role == UserRole.PATIENT.value:
        pat = db.query(Patient).filter(Patient.user_id == current.id).first()
        if not pat:
            raise HTTPException(status_code=404, detail="Patient profile not found")
        if patient_id is not None and patient_id != pat.id:
            raise HTTPException(status_code=403, detail="Can only view own appointments")
        d, p = doctor_id, pat.id
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    items, total = appointment_service.list_appointments_page(db, doctor_id=d, patient_id=p, page=page, page_size=ps)
    pages = ceil(total / ps) if total else 0
    return PaginatedAppointments(
        items=[_to_response(a) for a in items],
        total=total,
        page=page,
        page_size=ps,
        total_pages=pages,
    )


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> AppointmentResponse:
    ap = appointment_service.get_appointment(db, appointment_id)
    if not ap:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current.role == UserRole.ADMIN.value:
        pass
    elif current.role == UserRole.DOCTOR.value:
        doc = db.query(Doctor).filter(Doctor.user_id == current.id).first()
        if not doc or ap.doctor_id != doc.id:
            raise HTTPException(status_code=403, detail="Not your appointment")
    elif current.role == UserRole.PATIENT.value:
        pat = db.query(Patient).filter(Patient.user_id == current.id).first()
        if not pat or ap.patient_id != pat.id:
            raise HTTPException(status_code=403, detail="Not your appointment")
    else:
        raise HTTPException(status_code=403, detail="Invalid role")
    return _to_response(ap)


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def book(
    data: AppointmentCreate,
    patient: Patient = Depends(get_patient_profile),
    db: Session = Depends(get_db),
) -> AppointmentResponse:
    ap = appointment_service.create_appointment(db, patient, data)
    return _to_response(ap)


@router.put("/{appointment_id}/status", response_model=AppointmentResponse)
def update_status(
    appointment_id: int,
    body: AppointmentUpdateStatus,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> AppointmentResponse:
    ap = appointment_service.get_appointment(db, appointment_id)
    if not ap:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current.role == UserRole.PATIENT.value:
        pat = db.query(Patient).filter(Patient.user_id == current.id).first()
        if not pat or ap.patient_id != pat.id:
            raise HTTPException(status_code=403, detail="Not your appointment")
    elif current.role == UserRole.DOCTOR.value:
        doc = db.query(Doctor).filter(Doctor.user_id == current.id).first()
        if not doc or ap.doctor_id != doc.id:
            raise HTTPException(status_code=403, detail="Not your appointment")
    elif current.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Not allowed")

    appointment_service.update_appointment_status(db, ap, body.status.value, actor_role=current.role)
    db.refresh(ap)
    return _to_response(ap)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
def reschedule(
    appointment_id: int,
    body: AppointmentReschedule,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> AppointmentResponse:
    ap = appointment_service.get_appointment(db, appointment_id)
    if not ap:
        raise HTTPException(status_code=404, detail="Appointment not found")

    pat = db.query(Patient).filter(Patient.user_id == current.id).first() if current.role == UserRole.PATIENT.value else None
    doc = db.query(Doctor).filter(Doctor.user_id == current.id).first() if current.role == UserRole.DOCTOR.value else None

    new_doc = body.doctor_id if current.role == UserRole.ADMIN.value else None

    appointment_service.reschedule_appointment(
        db,
        ap,
        start_time=body.start_time,
        end_time=body.end_time,
        new_doctor_id=new_doc,
        actor_role=current.role,
        patient=pat,
        doctor=doc,
    )
    db.refresh(ap)
    return _to_response(ap)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN.value)),
) -> None:
    ap = appointment_service.get_appointment(db, appointment_id)
    if not ap:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appointment_service.delete_appointment(db, ap)

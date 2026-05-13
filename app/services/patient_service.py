import logging
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import Appointment, Patient, User, UserRole
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.cache import cache_service
from app.utils.security import get_password_hash

logger = logging.getLogger(__name__)


def _patient_to_dict(p: Patient) -> dict[str, Any]:
    return {
        "id": p.id,
        "user_id": p.user_id,
        "phone": p.phone,
        "medical_notes": p.medical_notes,
        "full_name": p.user.full_name if p.user else None,
        "email": p.user.email if p.user else None,
    }


def list_patients(db: Session) -> list[dict[str, Any]]:
    cached = cache_service.get_json("patients:all")
    if cached is not None:
        logger.debug("patients list cache hit")
        return cached
    rows = db.query(Patient).options(joinedload(Patient.user)).order_by(Patient.id).all()
    payload = [_patient_to_dict(p) for p in rows]
    cache_service.set_json("patients:all", payload)
    return payload


def get_patient(db: Session, patient_id: int) -> dict[str, Any] | None:
    key = f"patients:id:{patient_id}"
    cached = cache_service.get_json(key)
    if cached is not None:
        return cached
    p = db.query(Patient).options(joinedload(Patient.user)).filter(Patient.id == patient_id).first()
    if not p:
        return None
    payload = _patient_to_dict(p)
    cache_service.set_json(key, payload)
    return payload


def create_patient(db: Session, data: PatientCreate) -> Patient:
    if db.query(User).filter(User.email == data.email).first():
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=UserRole.PATIENT.value,
    )
    db.add(user)
    db.flush()
    pat = Patient(user_id=user.id, phone=data.phone, medical_notes=data.medical_notes)
    db.add(pat)
    db.commit()
    db.refresh(pat)
    logger.info("Patient created id=%s", pat.id)
    cache_service.invalidate_patients()
    cache_service.invalidate_patient(pat.id)
    return pat


def update_patient(db: Session, patient: Patient, data: PatientUpdate) -> Patient:
    if data.phone is not None:
        patient.phone = data.phone
    if data.medical_notes is not None:
        patient.medical_notes = data.medical_notes
    db.add(patient)
    db.commit()
    db.refresh(patient)
    logger.info("Patient updated id=%s", patient.id)
    cache_service.invalidate_patients()
    cache_service.invalidate_patient(patient.id)
    return patient


def delete_patient(db: Session, patient: Patient) -> None:
    from fastapi import HTTPException, status

    n = db.query(Appointment).filter(Appointment.patient_id == patient.id).count()
    if n:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete patient with existing appointments",
        )
    user = patient.user
    pid = patient.id
    db.delete(patient)
    if user:
        db.delete(user)
    db.commit()
    logger.warning("Patient deleted id=%s", pid)
    cache_service.invalidate_patients()
    cache_service.invalidate_patient(pid)

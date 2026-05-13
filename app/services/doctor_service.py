import logging
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import Appointment, Doctor, User, UserRole
from app.schemas.doctor import DoctorCreate, DoctorUpdate
from app.services.cache import cache_service
from app.utils.security import get_password_hash

logger = logging.getLogger(__name__)


def _doctor_to_dict(d: Doctor) -> dict[str, Any]:
    return {
        "id": d.id,
        "user_id": d.user_id,
        "specialization": d.specialization,
        "department": d.department,
        "bio": d.bio,
        "full_name": d.user.full_name if d.user else None,
        "email": d.user.email if d.user else None,
    }


def list_doctors(db: Session) -> list[dict[str, Any]]:
    cached = cache_service.get_json("doctors:all")
    if cached is not None:
        logger.debug("doctors list cache hit")
        return cached
    rows = db.query(Doctor).options(joinedload(Doctor.user)).order_by(Doctor.id).all()
    payload = [_doctor_to_dict(d) for d in rows]
    cache_service.set_json("doctors:all", payload)
    logger.debug("doctors list cache miss, stored")
    return payload


def get_doctor(db: Session, doctor_id: int) -> dict[str, Any] | None:
    key = f"doctors:id:{doctor_id}"
    cached = cache_service.get_json(key)
    if cached is not None:
        logger.debug("doctor id=%s cache hit", doctor_id)
        return cached
    d = db.query(Doctor).options(joinedload(Doctor.user)).filter(Doctor.id == doctor_id).first()
    if not d:
        return None
    payload = _doctor_to_dict(d)
    cache_service.set_json(key, payload)
    return payload


def create_doctor(db: Session, data: DoctorCreate) -> Doctor:
    if db.query(User).filter(User.email == data.email).first():
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=UserRole.DOCTOR.value,
    )
    db.add(user)
    db.flush()
    doc = Doctor(user_id=user.id, specialization=data.specialization, department=data.department, bio=data.bio)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info("Doctor created id=%s user_id=%s", doc.id, user.id)
    cache_service.invalidate_doctors()
    cache_service.invalidate_doctor(doc.id)
    return doc


def update_doctor(db: Session, doctor: Doctor, data: DoctorUpdate) -> Doctor:
    if data.specialization is not None:
        doctor.specialization = data.specialization
    if data.department is not None:
        doctor.department = data.department
    if data.bio is not None:
        doctor.bio = data.bio
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    logger.info("Doctor updated id=%s", doctor.id)
    cache_service.invalidate_doctors()
    cache_service.invalidate_doctor(doctor.id)
    return doctor


def delete_doctor(db: Session, doctor: Doctor) -> None:
    from fastapi import HTTPException, status

    n = db.query(Appointment).filter(Appointment.doctor_id == doctor.id).count()
    if n:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete doctor with existing appointments",
        )
    user = doctor.user
    did = doctor.id
    db.delete(doctor)
    if user:
        db.delete(user)
    db.commit()
    logger.warning("Doctor deleted id=%s", did)
    cache_service.invalidate_doctors()
    cache_service.invalidate_doctor(did)

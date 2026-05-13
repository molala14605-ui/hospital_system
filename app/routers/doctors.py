import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import Doctor, User, UserRole
from app.schemas.doctor import DoctorCreate, DoctorResponse, DoctorUpdate
from app.services import doctor_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorResponse])
def list_doctors(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DoctorResponse]:
    rows = doctor_service.list_doctors(db)
    return [DoctorResponse.model_validate(r) for r in rows]


@router.get("/{doctor_id}", response_model=DoctorResponse)
def get_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DoctorResponse:
    row = doctor_service.get_doctor(db, doctor_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return DoctorResponse.model_validate(row)


@router.post("", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
def create_doctor(
    data: DoctorCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN.value)),
) -> DoctorResponse:
    doc = doctor_service.create_doctor(db, data)
    db.refresh(doc)
    row = doctor_service.get_doctor(db, doc.id)
    assert row
    return DoctorResponse.model_validate(row)


@router.put("/{doctor_id}", response_model=DoctorResponse)
def update_doctor(
    doctor_id: int,
    data: DoctorUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN.value)),
) -> DoctorResponse:
    doc = db.get(Doctor, doctor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")
    doctor_service.update_doctor(db, doc, data)
    row = doctor_service.get_doctor(db, doctor_id)
    assert row
    return DoctorResponse.model_validate(row)


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doctor(
    doctor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN.value)),
) -> None:
    doc = db.get(Doctor, doctor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")
    doctor_service.delete_doctor(db, doc)

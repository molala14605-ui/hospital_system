import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_patient_profile, require_roles
from app.models import Patient, User, UserRole
from app.schemas.patient import PatientCreate, PatientResponse, PatientUpdate
from app.services import patient_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/me", response_model=PatientResponse)
def get_me(
    patient: Annotated[Patient, Depends(get_patient_profile)],
    db: Session = Depends(get_db),
) -> PatientResponse:
    row = patient_service.get_patient(db, patient.id)
    assert row
    return PatientResponse.model_validate(row)


@router.get("", response_model=list[PatientResponse])
def list_patients(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN.value)),
) -> list[PatientResponse]:
    rows = patient_service.list_patients(db)
    return [PatientResponse.model_validate(r) for r in rows]


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> PatientResponse:
    if current.role == UserRole.ADMIN.value:
        pass
    elif current.role == UserRole.PATIENT.value:
        mine = db.query(Patient).filter(Patient.user_id == current.id).first()
        if not mine or mine.id != patient_id:
            raise HTTPException(status_code=403, detail="Can only access own patient record")
    else:
        raise HTTPException(status_code=403, detail="Not allowed")
    row = patient_service.get_patient(db, patient_id)
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")
    return PatientResponse.model_validate(row)


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    data: PatientCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN.value)),
) -> PatientResponse:
    pat = patient_service.create_patient(db, data)
    row = patient_service.get_patient(db, pat.id)
    assert row
    return PatientResponse.model_validate(row)


@router.put("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    data: PatientUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> PatientResponse:
    pat = db.get(Patient, patient_id)
    if not pat:
        raise HTTPException(status_code=404, detail="Patient not found")
    if current.role == UserRole.ADMIN.value:
        pass
    elif current.role == UserRole.PATIENT.value and pat.user_id == current.id:
        if data.medical_notes is not None:
            raise HTTPException(status_code=403, detail="Patients cannot update medical notes")
    else:
        raise HTTPException(status_code=403, detail="Not allowed")
    patient_service.update_patient(db, pat, data)
    row = patient_service.get_patient(db, patient_id)
    assert row
    return PatientResponse.model_validate(row)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN.value)),
) -> None:
    pat = db.get(Patient, patient_id)
    if not pat:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient_service.delete_patient(db, pat)

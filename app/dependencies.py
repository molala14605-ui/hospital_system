from typing import Annotated
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Doctor, Patient, User, UserRole
from app.utils.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except (JWTError, ValueError, TypeError):
        logging.getLogger(__name__).warning("JWT validation failed")
        raise credentials_exception
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_roles(*roles: str):
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker


def get_doctor_profile(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> Doctor:
    if user.role != UserRole.DOCTOR.value:
        raise HTTPException(status_code=403, detail="Not a doctor account")
    doc = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return doc


def get_patient_profile(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> Patient:
    if user.role != UserRole.PATIENT.value:
        raise HTTPException(status_code=403, detail="Not a patient account")
    pat = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not pat:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return pat

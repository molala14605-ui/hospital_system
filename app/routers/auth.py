import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Patient, User, UserRole
from app.ratelimit import check_login_rate, check_register_rate, check_token_rate
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.utils.security import create_access_token, get_password_hash, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: UserCreate,
    db: Session = Depends(get_db),
    _: None = Depends(check_register_rate),
) -> User:
    if db.query(User).filter(User.email == str(data.email)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        email=str(data.email),
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=UserRole.PATIENT.value,
    )
    db.add(user)
    db.flush()
    patient = Patient(user_id=user.id)
    db.add(patient)
    db.commit()
    db.refresh(user)
    logger.info("User registered patient user_id=%s email=%s", user.id, user.email)
    return user


@router.post("/login", response_model=Token)
def login_json(
    data: UserLogin,
    db: Session = Depends(get_db),
    _: None = Depends(check_login_rate),
) -> Token:
    """JSON login for SPA / tests (email + password)."""
    user = db.query(User).filter(User.email == str(data.email)).first()
    if not user or not verify_password(data.password, user.hashed_password):
        logger.warning("Login failed email=%s", data.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(str(user.id), user.role)
    logger.info("Login success user_id=%s", user.id)
    return Token(access_token=token)


@router.post("/token", response_model=Token)
def login_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
    _: None = Depends(check_token_rate),
) -> Token:
    """OAuth2 compatible token endpoint (use email as username)."""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("Token login failed username=%s", form_data.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(str(user.id), user.role)
    logger.info("Token login success user_id=%s", user.id)
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current: User = Depends(get_current_user)) -> User:
    return current

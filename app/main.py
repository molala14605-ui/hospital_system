import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.models import Doctor, Patient, User, UserRole
from app.routers import appointments, auth, doctors, monitoring, patients
from app.utils.logging_config import setup_logging
from app.utils.security import get_password_hash

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.bootstrap_admin_email).first()
        if not existing:
            admin = User(
                email=settings.bootstrap_admin_email,
                hashed_password=get_password_hash(settings.bootstrap_admin_password),
                full_name="System Administrator",
                role=UserRole.ADMIN.value,
            )
            db.add(admin)
            db.commit()
            logger.warning(
                "Bootstrap admin user created email=%s (change password in production)",
                settings.bootstrap_admin_email,
            )

        if not db.query(User).filter(User.email == settings.bootstrap_demo_doctor_email).first():
            doc_user = User(
                email=settings.bootstrap_demo_doctor_email,
                hashed_password=get_password_hash(settings.bootstrap_demo_doctor_password),
                full_name=settings.bootstrap_demo_doctor_full_name,
                role=UserRole.DOCTOR.value,
            )
            db.add(doc_user)
            db.flush()
            db.add(
                Doctor(
                    user_id=doc_user.id,
                    specialization="طب عام",
                    department="تجريبي",
                    bio="حساب تجريبي للطبيب — غيّر كلمة المرور في الإنتاج.",
                )
            )
            db.commit()
            logger.warning("Bootstrap demo doctor created email=%s", settings.bootstrap_demo_doctor_email)

        if not db.query(User).filter(User.email == settings.bootstrap_demo_patient_email).first():
            pat_user = User(
                email=settings.bootstrap_demo_patient_email,
                hashed_password=get_password_hash(settings.bootstrap_demo_patient_password),
                full_name=settings.bootstrap_demo_patient_full_name,
                role=UserRole.PATIENT.value,
            )
            db.add(pat_user)
            db.flush()
            db.add(Patient(user_id=pat_user.id, phone=None, medical_notes=None))
            db.commit()
            logger.warning("Bootstrap demo patient created email=%s", settings.bootstrap_demo_patient_email)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "Hospital appointments with JWT roles (admin / doctor / patient), "
        "booking rules, pagination, reschedule, Redis cache-aside, and metrics."
    ),
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"message": "Validation error", "errors": exc.errors()},
    )


@app.get("/health")
def health():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()
    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": False, "service": settings.app_name},
        )
    return {"status": "healthy", "database": True, "service": settings.app_name}


@app.get("/metrics")
def prometheus_metrics() -> PlainTextResponse:
    data = generate_latest()
    return PlainTextResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.get("/dashboard", include_in_schema=False)
def dashboard_page() -> FileResponse:
    return FileResponse(ROOT / "static" / "dashboard.html")


app.include_router(auth.router, prefix="/api/v1")
app.include_router(doctors.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(appointments.router, prefix="/api/v1")
app.include_router(monitoring.router, prefix="/api/v1")

frontend_dir = ROOT / "frontend"
if frontend_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=str(frontend_dir), html=True), name="ui")

static_dir = ROOT / "static"
if static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(static_dir)), name="assets")

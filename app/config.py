from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Hospital Appointment System"
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    database_url: str = "sqlite:///./hospital.db"

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True
    cache_ttl_seconds: int = 300

    bootstrap_admin_email: str = "admin@hospital.example.com"
    bootstrap_admin_password: str = "Admin123!"

    # Demo accounts (created on startup if missing — for UI / local testing only)
    bootstrap_demo_doctor_email: str = "doctor.demo@hospital.example.com"
    bootstrap_demo_doctor_password: str = "Doctor123!"
    bootstrap_demo_doctor_full_name: str = "د. تجريبي"

    bootstrap_demo_patient_email: str = "patient.demo@hospital.example.com"
    bootstrap_demo_patient_password: str = "Patient123!"
    bootstrap_demo_patient_full_name: str = "مريض تجريبي"

    # Booking rules
    min_appointment_minutes: int = 15
    max_appointment_hours: int = 12
    booking_past_grace_seconds: int = 60

    # Appointments list
    appointments_default_page_size: int = 20
    appointments_max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()

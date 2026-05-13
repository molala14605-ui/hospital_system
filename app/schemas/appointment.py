from datetime import datetime
from enum import Enum
from math import ceil

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AppointmentStatusEnum(str, Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"


class AppointmentBase(BaseModel):
    doctor_id: int
    start_time: datetime
    end_time: datetime
    reason: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def check_times(self) -> "AppointmentBase":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdateStatus(BaseModel):
    status: AppointmentStatusEnum


class AppointmentReschedule(BaseModel):
    """Reschedule a scheduled appointment. Only admin may set doctor_id to reassign."""

    start_time: datetime
    end_time: datetime
    doctor_id: int | None = Field(
        default=None,
        description="Optional. Admin only: assign appointment to another doctor.",
    )

    @model_validator(mode="after")
    def check_times(self) -> "AppointmentReschedule":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    patient_id: int
    start_time: datetime
    end_time: datetime
    status: str
    reason: str | None
    created_at: datetime


class PaginatedAppointments(BaseModel):
    items: list[AppointmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

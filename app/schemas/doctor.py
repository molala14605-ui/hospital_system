from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DoctorBase(BaseModel):
    specialization: str = Field(..., min_length=1, max_length=255)
    department: str | None = Field(None, max_length=255)
    bio: str | None = None


class DoctorCreate(DoctorBase):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)


class DoctorUpdate(BaseModel):
    specialization: str | None = Field(None, min_length=1, max_length=255)
    department: str | None = None
    bio: str | None = None


class DoctorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    specialization: str
    department: str | None
    bio: str | None
    full_name: str | None = None
    email: str | None = None

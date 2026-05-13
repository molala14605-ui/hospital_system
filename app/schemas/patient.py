from pydantic import BaseModel, ConfigDict, Field


class PatientBase(BaseModel):
    phone: str | None = Field(None, max_length=50)
    medical_notes: str | None = None


class PatientCreate(PatientBase):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)


class PatientUpdate(BaseModel):
    phone: str | None = Field(None, max_length=50)
    medical_notes: str | None = None


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    phone: str | None
    medical_notes: str | None
    full_name: str | None = None
    email: str | None = None

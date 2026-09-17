import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.candidate import CandidateSource


class CandidateCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    location: str | None = Field(default=None, max_length=255)
    current_title: str | None = Field(default=None, max_length=255)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    source: CandidateSource = CandidateSource.RECRUITER_ADDED


class CandidateUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    location: str | None = Field(default=None, max_length=255)
    current_title: str | None = Field(default=None, max_length=255)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    is_active: bool | None = None


class CandidateDeleteRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    location: str | None
    current_title: str | None
    years_experience: int | None
    source: CandidateSource
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus


class JobCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    employment_type: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1)
    openings_count: int = Field(default=1, ge=1)


class JobUpdateRequest(BaseModel):
    """All fields optional — a PATCH applies only what the caller sends
    (`exclude_unset=True` at the service layer)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    employment_type: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, min_length=1)
    status: JobStatus | None = None
    openings_count: int | None = Field(default=None, ge=1)


class JobDeleteRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    employment_type: str | None
    description: str
    status: JobStatus
    openings_count: int
    created_by: uuid.UUID
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

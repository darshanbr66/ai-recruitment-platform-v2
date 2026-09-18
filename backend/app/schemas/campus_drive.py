import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.campus_drive import CampusDriveStatus


class CampusDriveCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    college_name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    batch_year: int | None = Field(default=None, ge=1980, le=2100)
    start_date: date | None = None
    end_date: date | None = None
    registration_deadline: date | None = None
    default_assessment_id: uuid.UUID | None = None

    # Exactly one of these two identifies the job this drive hires for —
    # an existing job, or a brand-new one entered inline (see
    # docs/campus-hiring.md's redesigned "Can't find the job? + Add New
    # Job" flow).
    job_id: uuid.UUID | None = None
    new_job_title: str | None = Field(default=None, min_length=1, max_length=255)
    new_job_description: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _exactly_one_job_source(self) -> "CampusDriveCreateRequest":
        if bool(self.job_id) == bool(self.new_job_title):
            raise ValueError(
                "Provide either an existing job_id or a new_job_title, not both or neither."
            )
        if self.new_job_title and not self.new_job_description:
            raise ValueError("new_job_description is required when creating a new job.")
        return self


class CampusDriveDeleteRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class CampusDriveUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    college_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    batch_year: int | None = Field(default=None, ge=1980, le=2100)
    start_date: date | None = None
    end_date: date | None = None
    registration_deadline: date | None = None
    default_assessment_id: uuid.UUID | None = None
    status: CampusDriveStatus | None = None


class CampusDriveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    job_id: uuid.UUID
    job_title: str
    college_name: str
    description: str | None
    batch_year: int | None
    start_date: date | None
    end_date: date | None
    registration_deadline: date | None
    default_assessment_id: uuid.UUID | None
    default_assessment_title: str | None
    status: CampusDriveStatus
    application_count: int
    deleted_at: datetime | None = None
    created_at: datetime
    # Only populated by the create/regenerate-link endpoints — the raw
    # token is shown once, like an assessment invitation link.
    application_link: str | None = None


class CampusDriveFunnelCounts(BaseModel):
    registered: int
    screening: int
    assessment_invited: int
    assessment_completed: int
    assessment_passed: int
    assessment_failed: int
    shortlisted: int
    interview: int
    selected: int
    rejected: int
    hired: int

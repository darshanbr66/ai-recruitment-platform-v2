import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import ApplicationSource, ApplicationStatus


class ApplicationSortField(StrEnum):
    """What the Applications list can be ordered by. `created_at` is the
    long-standing default; `status` orders by workflow stage (the enum's
    declaration order), not alphabetically."""

    CREATED_AT = "created_at"
    APPLIED_AT = "applied_at"
    CANDIDATE_NAME = "candidate_name"
    JOB_TITLE = "job_title"
    STATUS = "status"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class ApplicationCreateRequest(BaseModel):
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    source: ApplicationSource = ApplicationSource.RECRUITER_ADDED


class ApplicationStatusChangeRequest(BaseModel):
    to_status: ApplicationStatus
    reason: str | None = Field(default=None, max_length=1000)


class ApplicationDeleteRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class ApplicationResponse(BaseModel):
    """Includes denormalized `candidate_full_name`/`job_title` — populated
    by the service's join query — so a recruiter list view doesn't need a
    separate lookup per row for what is, in practice, always shown."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_full_name: str
    candidate_email: str
    candidate_phone: str | None = None
    job_id: uuid.UUID
    job_title: str
    campus_drive_id: uuid.UUID | None = None
    status: ApplicationStatus
    source: ApplicationSource
    applied_at: datetime
    created_at: datetime
    updated_at: datetime
    resume_id: uuid.UUID | None = None
    resume_filename: str | None = None
    deleted_at: datetime | None = None


class ApplicationStatusHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    changed_by_user_id: uuid.UUID | None
    reason: str | None
    created_at: datetime

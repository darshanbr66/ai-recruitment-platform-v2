import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.campus_drive import CampusDriveStatus


class CampusDriveCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    job_id: uuid.UUID
    college_name: str = Field(min_length=1, max_length=255)
    batch_year: int | None = Field(default=None, ge=1980, le=2100)
    start_date: date | None = None
    end_date: date | None = None


class CampusDriveUpdateRequest(BaseModel):
    status: CampusDriveStatus | None = None


class CampusDriveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    job_id: uuid.UUID
    job_title: str
    college_name: str
    batch_year: int | None
    start_date: date | None
    end_date: date | None
    status: CampusDriveStatus
    application_count: int
    created_at: datetime

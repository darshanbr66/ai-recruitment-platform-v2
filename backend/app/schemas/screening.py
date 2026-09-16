import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.screening import ScreeningStatus


class ScreeningRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    status: ScreeningStatus
    provider: str
    model: str
    overall_score: int | None
    recommendation: str | None
    summary: str | None
    matching_skills: list[str] | None
    missing_skills: list[str] | None
    strengths: list[str] | None
    concerns: list[str] | None
    experience_assessment: str | None
    education_assessment: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

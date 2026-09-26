import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.application import ApplicationSource, ApplicationStatus
from app.schemas.screening import ScreeningRunResponse


class CandidateApplicationHistory(BaseModel):
    """One job association of a candidate, with every screening run on it
    (newest first). `is_original` marks the candidate's first self-service
    application; `is_self_service` every application they submitted
    themselves (a later one is a reapply). HR_MATCH / RECRUITER_ADDED rows
    were created by staff."""

    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    source: ApplicationSource
    status: ApplicationStatus
    applied_at: datetime
    is_original: bool
    is_self_service: bool = False
    deleted_at: datetime | None = None
    screenings: list[ScreeningRunResponse] = Field(default_factory=list)


class CandidateTimelineEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    actor_name: str | None
    description: str | None
    reason: str | None
    created_at: datetime


class CandidateHistoryResponse(BaseModel):
    """Everything HR needs to audit one candidate's journey: original
    application, HR matches, screening history and the candidate-related
    audit trail (verification, screening outcomes, overrides, matches,
    welcome email, blocked duplicate attempts)."""

    candidate_id: uuid.UUID
    applications: list[CandidateApplicationHistory]
    timeline: list[CandidateTimelineEntry]

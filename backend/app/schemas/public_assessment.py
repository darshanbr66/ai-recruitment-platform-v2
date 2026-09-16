import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.assessment import InvitationStatus, QuestionType


class PublicQuestionOption(BaseModel):
    """Never includes `is_correct` (docs/assessment.md § 2)."""

    id: uuid.UUID
    label: str


class PublicQuestion(BaseModel):
    id: uuid.UUID
    prompt: str
    type: QuestionType
    points: int
    options: list[PublicQuestionOption]


class PublicInvitationView(BaseModel):
    status: InvitationStatus
    assessment_title: str
    instructions: str
    duration_minutes: int
    job_title: str
    organization_name: str
    expires_at: datetime
    started_at: datetime | None
    questions: list[PublicQuestion]


class AnswerSubmission(BaseModel):
    question_id: uuid.UUID
    selected_option_ids: list[uuid.UUID] = Field(default_factory=list)


class SubmitAnswersRequest(BaseModel):
    answers: list[AnswerSubmission]


class PublicSubmissionResult(BaseModel):
    score: int
    max_score: int
    percentage: int
    passed: bool

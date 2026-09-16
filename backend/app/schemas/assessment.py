import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.assessment import InvitationStatus, QuestionType


class QuestionOptionCreate(BaseModel):
    label: str = Field(min_length=1)
    is_correct: bool = False


class QuestionCreate(BaseModel):
    prompt: str = Field(min_length=1)
    type: QuestionType
    points: int = Field(default=1, ge=1)
    options: list[QuestionOptionCreate] = Field(min_length=2)


class AssessmentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    instructions: str = Field(min_length=1)
    duration_minutes: int = Field(default=30, ge=1, le=480)
    pass_score: int = Field(default=60, ge=0, le=100)
    questions: list[QuestionCreate] = Field(min_length=1)


class QuestionOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    is_correct: bool


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prompt: str
    type: QuestionType
    points: int
    options: list[QuestionOptionResponse]


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    instructions: str
    duration_minutes: int
    pass_score: int
    created_at: datetime
    questions: list[QuestionResponse] = []


class AssessmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    duration_minutes: int
    pass_score: int
    question_count: int
    created_at: datetime


class InviteCandidateRequest(BaseModel):
    assessment_id: uuid.UUID
    application_id: uuid.UUID


class AssessmentInvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    assessment_title: str
    application_id: uuid.UUID
    candidate_full_name: str
    status: InvitationStatus
    expires_at: datetime
    started_at: datetime | None
    submitted_at: datetime | None
    result: "AssessmentResultResponse | None" = None
    invitation_link: str | None = None


class AssessmentResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int
    max_score: int
    percentage: int
    passed: bool
    evaluated_at: datetime

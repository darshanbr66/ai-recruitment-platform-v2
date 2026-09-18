import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class ParsedQuestionsResponse(BaseModel):
    """Response for the "Import Questions" preview step — nothing here has
    been persisted yet. `questions` is shaped exactly like
    `AssessmentCreateRequest.questions` so the frontend can preview, edit,
    reorder, and select before sending the final create request unchanged.
    """

    questions: list[QuestionCreate]
    warnings: list[str]


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
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    questions: list[QuestionResponse] = []
    # Computed, not an Assessment column — set by the route/service layer
    # (assessment_service.assessment_has_invitations), never by
    # `.model_validate(assessment)` alone. True once any candidate could
    # have been invited, which is exactly when question-structure edits
    # become locked (see AssessmentUpdateRequest).
    has_invitations: bool = False


class AssessmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    duration_minutes: int
    pass_score: int
    question_count: int
    created_at: datetime


class AssessmentUpdateRequest(BaseModel):
    """All fields optional — a PATCH applies only what the caller sends
    (`exclude_unset=True` at the service layer, mirroring
    `JobUpdateRequest`). `questions`, when provided, *replaces* the entire
    question set — only legal while no `AssessmentInvitation` exists yet for
    this assessment (see assessment_service.update_assessment); once a
    candidate could have been invited, question content is frozen so a
    completed/in-progress attempt is never invalidated retroactively."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    instructions: str | None = Field(default=None, min_length=1)
    duration_minutes: int | None = Field(default=None, ge=1, le=480)
    pass_score: int | None = Field(default=None, ge=0, le=100)
    questions: list[QuestionCreate] | None = Field(default=None, min_length=1)


class AssessmentDeleteRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class InviteCandidateRequest(BaseModel):
    assessment_id: uuid.UUID
    application_id: uuid.UUID


class RetestAssessmentChoice(StrEnum):
    """How a retest picks the assessment for the new attempt (QA § 6) — the
    previous attempt's own assessment/score/answers are never touched
    regardless of which of these is chosen (app/services/
    assessment_service.py::create_retest)."""

    SAME = "SAME"
    EXISTING = "EXISTING"
    NEW = "NEW"


class RetestRequest(BaseModel):
    application_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=1000)
    assessment_choice: RetestAssessmentChoice = RetestAssessmentChoice.SAME
    # Required when assessment_choice == EXISTING.
    assessment_id: uuid.UUID | None = None
    # Required when assessment_choice == NEW — reuses the same
    # create-assessment shape (and question-import workflow feeding it) as
    # a normal assessment creation, per QA § 6 ("do not duplicate code").
    new_assessment: AssessmentCreateRequest | None = None

    @model_validator(mode="after")
    def _validate_choice(self) -> "RetestRequest":
        if self.assessment_choice == RetestAssessmentChoice.EXISTING and self.assessment_id is None:
            raise ValueError("assessment_id is required when assessment_choice is EXISTING.")
        if self.assessment_choice == RetestAssessmentChoice.NEW and self.new_assessment is None:
            raise ValueError("new_assessment is required when assessment_choice is NEW.")
        return self


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
    attempt_number: int
    retest_reason: str | None
    result: "AssessmentResultResponse | None" = None
    invitation_link: str | None = None


class AssessmentResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int
    max_score: int
    percentage: int
    passed: bool
    evaluated_at: datetime

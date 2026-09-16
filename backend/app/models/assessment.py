import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class QuestionType(StrEnum):
    MCQ_SINGLE = "MCQ_SINGLE"
    MCQ_MULTI = "MCQ_MULTI"


class InvitationStatus(StrEnum):
    SENT = "SENT"
    STARTED = "STARTED"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class Assessment(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """An org-owned, reusable assessment definition (docs/assessment.md § 1)
    — independent of why a candidate is invited (normal recruitment or a
    campus drive). MVP scope: MCQ only, matching docs/assessment.md's
    stated initial build."""

    __tablename__ = "assessments"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    pass_score: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    questions: Mapped[list["Question"]] = relationship(
        "Question", lazy="raise", order_by="Question.order_index", viewonly=True
    )


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Belongs to exactly one Assessment — no shared question-bank
    abstraction (docs/assessment.md § 2: adding one prematurely is exactly
    what CLAUDE.md § 5 rules out). Tenancy is derived through
    assessment_id, same indirect-RLS pattern as application_status_history.
    """

    __tablename__ = "questions"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", native_enum=True), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    options: Mapped[list["QuestionOption"]] = relationship(
        "QuestionOption", lazy="raise", order_by="QuestionOption.order_index", viewonly=True
    )


class QuestionOption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "question_options"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    # Never sent to the candidate (docs/assessment.md § 2) — excluded from
    # the public-facing schema in app/schemas/public_assessment.py.
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AssessmentInvitation(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """The secure, single-purpose link from one Application to one
    Assessment (docs/assessment.md § 3-4). Token is shown once and stored
    only as a hash (`app.core.security.hash_opaque_token`) — never in
    plaintext (CLAUDE.md § 4).

    Simplified from docs/assessment.md's full lifecycle: no
    DELIVERED/OPENED webhook states and no `max_attempts` bound (one
    CandidateAttempt per invitation, implicit) — both are real gaps noted
    here rather than silently designed around, not silently dropped.
    One invitation per application (unique on application_id); resending
    reuses this row (new token/expiry), matching docs/campus-hiring.md § 3.
    """

    __tablename__ = "assessment_invitations"
    __table_args__ = ()

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus, name="assessment_invitation_status", native_enum=True),
        nullable=False,
        default=InvitationStatus.SENT,
        server_default=InvitationStatus.SENT.value,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assessment: Mapped["Assessment"] = relationship("Assessment", lazy="raise", viewonly=True)
    result: Mapped["AssessmentResult | None"] = relationship(
        "AssessmentResult", lazy="raise", uselist=False, viewonly=True
    )


class CandidateAnswer(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "candidate_answers"

    invitation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_invitations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    selected_option_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


class AssessmentResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "assessment_results"

    invitation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_invitations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ScreeningStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScreeningDecision(StrEnum):
    """The binary outcome business logic acts on (the submission-time gate
    in app/services/public_application_service.py). The finer-grained
    `recommendation` stays for recruiters."""

    MATCH = "MATCH"
    NOT_MATCH = "NOT_MATCH"


class ScreeningRun(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """One AI-assisted screening attempt for one Application (docs/
    ai-screening.md § 1: "AI != Candidate" — never merged onto Candidate or
    Application). Re-screening creates a new row rather than mutating a
    prior one (docs/ai-screening.md § 4); the "current" result for display
    is simply the most recent COMPLETED run for that application, a derived
    read rather than a stored pointer (see report_service.py-style
    aggregation, computed at query time in screening_service.py).

    Deliberately simplified from docs/ai-screening.md's full ScreeningRun /
    AIRun / RequirementEvaluation / EvaluationEvidence normalization: that
    design assumes a pgvector-backed retrieval pipeline (JobRequirement,
    ResumeChunk, embeddings) which the same doc's § 6 explicitly defers
    ("no provider is chosen yet... deferred to Phase 5"). This MVP sends
    the whole resume + job description to the LLM in one call and stores
    its structured verdict directly — still fully real (no fabricated
    results) and still re-runnable/traceable per-run, just without
    per-requirement evidence citations. Upgrading to the granular model
    later is additive, not a rewrite of this table's consumers.
    """

    __tablename__ = "screening_runs"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL = run automatically by the system when the candidate submitted
    # their application (the submission-time screening gate).
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ScreeningStatus] = mapped_column(
        Enum(ScreeningStatus, name="screening_status", native_enum=True),
        nullable=False,
        default=ScreeningStatus.PENDING,
        server_default=ScreeningStatus.PENDING.value,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    matching_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    missing_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    strengths: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    concerns: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    experience_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    education_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[ScreeningDecision | None] = mapped_column(
        Enum(ScreeningDecision, name="screening_decision", native_enum=True), nullable=True
    )
    # Explicit JD requirements (skills, experience, qualifications,
    # responsibilities) the resume does / does not evidence — broader than
    # the skill-only lists above.
    matched_requirements: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    missing_requirements: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

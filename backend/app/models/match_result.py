import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

#: Shown to every recruiter alongside a match result — the human-in-the-loop
#: requirement (CLAUDE.md § 10 / the brief § 10): AI assists, never decides.
#: Baked into the persisted row (not just UI copy) so it can never be
#: stripped by a client and travels with the data if exported/reported on.
AI_MATCH_DISCLAIMER = (
    "AI-generated assessment. Final hiring decision remains with the recruitment team."
)


class MatchStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MatchResult(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """One candidate<->job match computation from the AI matching/scoring
    engine (app/services/matching/match_engine.py) — the structured,
    explainable result the brief's § 2 requires (overall score, confidence,
    matching/missing signals, evidence, explanation).

    Append-only, same re-run philosophy as `ScreeningRun`
    (app/models/screening.py § docstring): re-matching (e.g. after a resume
    update, or a recruiter asking again) creates a new row rather than
    mutating a prior one, so a match is always reproducible and comparable
    against its own history. "Current" score for display is the most recent
    COMPLETED row for a (candidate_id, job_id) pair — a derived read, not a
    stored pointer.

    Never mutates `Application.status` or any Candidate/Application field —
    purely additive decision support (CLAUDE.md § 10).
    """

    __tablename__ = "match_results"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Nullable: a job-wide "find candidates for this role" match can run
    # before the candidate has an Application for it at all.
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status", native_enum=True),
        nullable=False,
        default=MatchStatus.PENDING,
        server_default=MatchStatus.PENDING.value,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    overall_match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)  # LOW/MEDIUM/HIGH
    matching_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    missing_skills: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    matching_experience: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    matching_education: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    matching_location: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    notice_period_fit: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    role_alignment: Mapped[str | None] = mapped_column(Text, nullable=True)
    potential_concerns: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # Chunk-level citations: [{resume_chunk_id, excerpt, similarity}, ...] —
    # the "store the individual scoring factors" explainability requirement.
    evidence: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The deterministic sub-scores that produced overall_match_score, kept
    # verbatim so "why this number" never depends on re-deriving it later.
    scoring_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

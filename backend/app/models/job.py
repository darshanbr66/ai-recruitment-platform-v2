import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class JobStatus(StrEnum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    ON_HOLD = "ON_HOLD"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"


class Job(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """A hiring opportunity. `JobRequirement` (structured, weighted
    requirements for AI screening) is deliberately not modeled yet — it has
    no consumer until Phase 5/6's retrieval pipeline exists; adding it now
    would be exactly the speculative-for-later-phases modeling
    docs/architecture.md § 14 warns against. `description` free text is
    enough for Phase 3's recruiter-facing CRUD.
    """

    __tablename__ = "jobs"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # UI-visibility only — the JD text is never deleted when hidden (CLAUDE.md
    # § 2: "Workflow state != ad hoc strings" applies equally here: this is a
    # real column, not an ad hoc frontend-only flag). Enforced server-side on
    # the public job-detail endpoint (app/api/v1/public/jobs.py), not just
    # hidden in the UI.
    description_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", native_enum=True),
        nullable=False,
        default=JobStatus.DRAFT,
        server_default=JobStatus.DRAFT.value,
    )
    openings_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Soft delete — same rationale/shape as Candidate's (app/models/candidate.py):
    # a hard DELETE would also be blocked by applications.job_id's ON DELETE
    # RESTRICT the moment the job has any application, so this makes that the
    # deliberate behavior everywhere. Deleted jobs are excluded from
    # `job_service.list_jobs` but every Application/CampusDrive pointing at
    # them stays intact.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deletion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

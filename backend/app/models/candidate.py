import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CandidateSource(StrEnum):
    """How this Candidate record came to exist — see
    docs/recruitment-workflow.md § 4. `PORTAL` (candidate self-registration)
    is unused until Phase 4 builds candidate auth; recruiter-facing creation
    in Phase 3 always uses `RECRUITER_ADDED`.
    """

    PORTAL = "PORTAL"
    RECRUITER_ADDED = "RECRUITER_ADDED"
    CAMPUS_IMPORT = "CAMPUS_IMPORT"
    REFERRAL = "REFERRAL"
    OTHER = "OTHER"


class Candidate(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Reusable candidate profile data — never merged with Application, which
    carries per-opportunity workflow state (CLAUDE.md § 2: "Candidate !=
    Application"). Tenant-scoped: the same person applying to two
    organizations on this platform is two independent Candidate rows (see
    docs/architecture.md § 3.3).

    `hashed_password` stays NULL until the candidate self-registers a portal
    login (Phase 4) — a recruiter-added candidate may never do so.
    """

    __tablename__ = "candidates"
    __table_args__ = (
        Index("uq_candidates_org_email", "organization_id", "email", unique=True),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[CandidateSource] = mapped_column(
        Enum(CandidateSource, name="candidate_source", native_enum=True),
        nullable=False,
        default=CandidateSource.RECRUITER_ADDED,
        server_default=CandidateSource.RECRUITER_ADDED.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # Soft delete (CLAUDE.md § "Reports != hardcoded numbers" sibling rule:
    # never silently destroy recruitment history). A hard DELETE would also
    # be blocked by applications.candidate_id's ON DELETE RESTRICT the
    # moment the candidate has any application — this makes that the
    # deliberate behavior everywhere, not just where the FK happens to
    # enforce it. Deleted candidates are excluded from
    # `candidate_service.list_candidates` but remain reachable by id (e.g.
    # from an Activities log entry) and keep every Application/Note/
    # AssessmentInvitation pointing at them intact.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deletion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

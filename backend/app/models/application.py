import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.resume import Resume


class ApplicationStatus(StrEnum):
    """The full transition table lives in
    app/workflows/application_workflow.py, not here — this enum is only the
    vocabulary (CLAUDE.md § 2: "Workflow state != ad hoc strings").
    """

    APPLIED = "APPLIED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SCREENING = "SCREENING"
    ASSESSMENT_INVITED = "ASSESSMENT_INVITED"
    ASSESSMENT_STARTED = "ASSESSMENT_STARTED"
    ASSESSMENT_COMPLETED = "ASSESSMENT_COMPLETED"
    SHORTLISTED = "SHORTLISTED"
    INTERVIEW = "INTERVIEW"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class ApplicationSource(StrEnum):
    PORTAL = "PORTAL"
    RECRUITER_ADDED = "RECRUITER_ADDED"
    CAMPUS_IMPORT = "CAMPUS_IMPORT"
    REFERRAL = "REFERRAL"
    OTHER = "OTHER"


class Application(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """The relationship between one Candidate and one Job — carries all
    workflow state (CLAUDE.md § 2: "Candidate != Application"). `resume` is
    reached via the Resume model's `application_id` FK (app/models/
    resume.py); `campus_drive_id` links a campus-sourced application to its
    CampusDrive (docs/campus-hiring.md § 2) and is null for ordinary
    recruitment applications.

    Unique on `(candidate_id, job_id)`: one application per candidate per
    job. Re-applying after WITHDRAWN/REJECTED is explicitly an open product
    question per docs/database.md § 3.5 ("not finalized") — not implemented
    here.
    """

    __tablename__ = "applications"
    __table_args__ = (
        Index("uq_applications_candidate_job", "candidate_id", "job_id", unique=True),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    campus_drive_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campus_drives.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status", native_enum=True),
        nullable=False,
        default=ApplicationStatus.APPLIED,
        server_default=ApplicationStatus.APPLIED.value,
    )
    source: Mapped[ApplicationSource] = mapped_column(
        Enum(ApplicationSource, name="application_source", native_enum=True),
        nullable=False,
        default=ApplicationSource.RECRUITER_ADDED,
        server_default=ApplicationSource.RECRUITER_ADDED.value,
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Read-only convenience relationships — populated via eager loading in
    # app/services/application_service.py so list/detail responses can
    # include the candidate's name and the job's title without a separate
    # round trip per row.
    candidate: Mapped[Candidate] = relationship(Candidate, lazy="raise")
    job: Mapped[Job] = relationship(Job, lazy="raise")
    resume: Mapped[Resume | None] = relationship(Resume, lazy="raise", uselist=False, viewonly=True)


class ApplicationStatusHistory(UUIDPrimaryKeyMixin, Base):
    """Append-only audit trail of every status change on an Application — see
    docs/recruitment-workflow.md § 1. No `organization_id` of its own;
    tenancy is derived through `application_id -> applications.organization_id`,
    same indirect-RLS pattern as `user_roles` (see app/db/rls.py).
    """

    __tablename__ = "application_status_history"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        Enum(
            ApplicationStatus, name="application_status", native_enum=True, create_type=False
        ),
        nullable=True,
    )
    to_status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus, name="application_status", native_enum=True, create_type=False
        ),
        nullable=False,
    )
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

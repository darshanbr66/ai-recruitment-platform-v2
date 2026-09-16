import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import Date, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.job import Job


class CampusDriveStatus(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class CampusDrive(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Composes an existing Job with campus-specific scheduling metadata —
    does not duplicate anything Job or Application already model
    (docs/campus-hiring.md § 1). Candidate participation is just
    `Application.campus_drive_id`, not a separate membership table (§ 2).

    Simplified from docs/campus-hiring.md: no `eligibility_criteria` jsonb
    filter and no `candidate_limit` enforcement — both real gaps, noted
    here rather than silently dropped, not blocking the core
    create-drive -> associate-job -> track-applications flow.
    """

    __tablename__ = "campus_drives"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    college_name: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[CampusDriveStatus] = mapped_column(
        Enum(CampusDriveStatus, name="campus_drive_status", native_enum=True),
        nullable=False,
        default=CampusDriveStatus.PLANNED,
        server_default=CampusDriveStatus.PLANNED.value,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    job: Mapped[Job] = relationship(Job, lazy="raise", viewonly=True)

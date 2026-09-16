import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Resume(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """A resume file submitted with one Application. `candidate_id` is
    denormalized (also reachable via `application.candidate_id`) so a
    candidate's resume history can be queried directly, matching the
    denormalization pattern `ApplicationResponse.candidate_full_name`
    already uses for the same reason.

    File bytes live on local disk under `settings.resume_storage_dir`
    (see app/integrations/storage) — this row is metadata only
    (CLAUDE.md § 2: "Resume storage != DB blob"). `storage_path` is never
    returned to clients; downloads go through an authenticated streaming
    endpoint that resolves it server-side.
    """

    __tablename__ = "resumes"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

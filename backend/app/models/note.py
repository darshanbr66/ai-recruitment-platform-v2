import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class NoteVisibility(StrEnum):
    """PRIVATE = only the author can ever see it, regardless of who holds
    `note.read`. SHARED = visible to anyone in the organization with
    `note.read` — the behavior every note had before this field existed, so
    it is the default (existing rows are backfilled to SHARED, preserving
    exactly what they already did)."""

    PRIVATE = "PRIVATE"
    SHARED = "SHARED"


class Note(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """A recruiter's freeform note — originally application-only commentary
    ("this candidate, this opportunity"), now also usable as a standalone
    personal note (the Notes workspace, `/recruiter/notes`) optionally
    linked to a candidate, a job, an application, or nothing at all.

    `application_id`/`candidate_id`/`job_id` are all independently nullable
    and never required together — a note can reference any combination (or
    none). Visibility (`NoteVisibility`) governs *reads* only; only the
    author may ever edit or delete a note, shared or not (CLAUDE.md § 5:
    "Personal notes should not automatically become visible to other
    employees" — enforced in note_service.py, not just implied by a
    default).
    """

    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_org_pinned", "organization_id", "pinned"),)

    # Nullable: a standalone personal note ("Follow up with candidate next
    # Monday") need not be tied to one specific application at all.
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # A free-form color token (e.g. "amber", "#f5a623") the UI renders as a
    # small visual marker — never given meaning server-side.
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    visibility: Mapped[NoteVisibility] = mapped_column(
        Enum(NoteVisibility, name="note_visibility", native_enum=True),
        nullable=False,
        default=NoteVisibility.SHARED,
        server_default=NoteVisibility.SHARED.value,
    )
    # Author-controlled only (same authorization as editing any other note
    # field) — pinned notes sort first in the workspace. `pinned_at` breaks
    # ties among several pinned notes (most-recently-pinned first) and is
    # cleared on unpin, not just flipped alongside the boolean.
    pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped[User] = relationship(User, lazy="raise", viewonly=True)

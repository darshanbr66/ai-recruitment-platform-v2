import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class Note(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """A recruiter's freeform note on one Application — the natural unit
    for "this candidate, this opportunity" commentary (interview
    impressions, follow-ups) without needing a separate note-per-candidate
    vs. note-per-job split."""

    __tablename__ = "notes"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    author: Mapped[User] = relationship(User, lazy="raise", viewonly=True)

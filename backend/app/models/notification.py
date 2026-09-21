import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationType(StrEnum):
    """Explicit event types — the frontend and tests key off these, never off
    the human-readable message text."""

    ASSESSMENT_STARTED = "ASSESSMENT_STARTED"
    ASSESSMENT_SUBMITTED = "ASSESSMENT_SUBMITTED"


class Notification(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """An in-app notification addressed to exactly one staff user (the
    recruiter/admin who sent an assessment invitation). Distinct from
    `notification_service`, which is outbound *email* — this is stored, read
    back by the recipient's own session and acknowledged (`read_at`).

    Once-only per event is a database guarantee, not application logic: the
    unique index on `(assessment_invitation_id, type)` means an invitation can
    produce at most one ASSESSMENT_STARTED and one ASSESSMENT_SUBMITTED row,
    however many requests race to create it (a retest is a new invitation row,
    so it notifies again — correctly).
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "uq_notifications_invitation_type",
            "assessment_invitation_id",
            "type",
            unique=True,
        ),
        # The poller's query: one user's unread rows, newest first.
        Index(
            "ix_notifications_recipient_unread",
            "recipient_user_id",
            "created_at",
            postgresql_where="read_at IS NULL",
        ),
    )

    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", native_enum=True), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_invitation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_invitations.id", ondelete="CASCADE"),
        nullable=True,
    )
    # NULL = not yet acknowledged by the recipient.
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

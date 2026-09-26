import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class AdminConversation(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """"Talk to Admin": one thread per staff member with their organization's
    admins (app/services/admin_messaging_service.py). The admin side is the
    ORG_ADMIN role as a whole, not one named admin — any admin can read and
    reply, and each message records which admin sent it.

    Distinct from the DIRECT_MESSAGE notification (app/models/notification.py),
    which is a one-off, reply-less note from one user to another.
    """

    __tablename__ = "admin_conversations"
    __table_args__ = (
        Index(
            "uq_admin_conversations_org_employee",
            "organization_id",
            "employee_user_id",
            unique=True,
        ),
    )

    employee_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized from the newest message so the admin inbox orders by it
    # without an aggregate over every message.
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    employee: Mapped[User] = relationship(
        User, foreign_keys=[employee_user_id], lazy="raise", viewonly=True
    )


class AdminMessage(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """One message in an AdminConversation. `from_admin` says which side
    wrote it (the recipient is always the other side); `read_at` /
    `read_by_user_id` record when — and, on the admin side, by which admin —
    it was first read."""

    __tablename__ = "admin_messages"
    __table_args__ = (
        Index("ix_admin_messages_conversation_created", "conversation_id", "created_at"),
        # Unread-badge queries: unread messages per conversation and side.
        Index(
            "ix_admin_messages_unread",
            "conversation_id",
            "from_admin",
            postgresql_where="read_at IS NULL",
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    from_admin: Mapped[bool] = mapped_column(Boolean, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    sender: Mapped[User | None] = relationship(
        User, foreign_keys=[sender_user_id], lazy="raise", viewonly=True
    )

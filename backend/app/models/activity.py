import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Activity(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Append-only audit trail for actions that change or remove
    organization data outside of a workflow status transition that already
    has its own history table (ApplicationStatusHistory). Nothing in this
    app ever updates or deletes an Activity row — it is written once by
    `app/services/activity_service.py` and only ever read back.

    `actor_name`/`actor_email` are denormalized snapshots (not just a FK)
    so the audit trail stays legible even if the acting user's own record
    is later renamed or removed — same reasoning as `entity_label` for the
    thing that was acted on.
    """

    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_org_created_at", "organization_id", "created_at"),)

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entity_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

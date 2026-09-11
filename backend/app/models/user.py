import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A staff account (recruiter-side). Distinct from Candidate — see
    CLAUDE.md § 2 and docs/architecture.md § 4.

    `organization_id` is nullable only for SUPER_ADMIN (a platform-level
    account with no single tenant). Every other role requires it.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_org_email",
            "organization_id",
            "email",
            unique=True,
            postgresql_where="organization_id IS NOT NULL",
        ),
        Index(
            "uq_users_platform_email",
            "email",
            unique=True,
            postgresql_where="organization_id IS NULL",
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserRefreshToken(UUIDPrimaryKeyMixin, Base):
    """Opaque refresh token, stored hashed only — see docs/architecture.md
    § 4 and docs/security.md § 1. Rotated on every use (`replaced_by_id`
    linking old -> new); reuse of an already-rotated token is a breach
    signal, handled by revoking every token sharing `family_id`.

    Not tenant-scoped by its own column — tenancy is derived through
    `user_id` -> `users.organization_id`, same pattern as `user_roles`.
    """

    __tablename__ = "user_refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )

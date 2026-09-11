import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

# The five staff roles from docs/architecture.md § 4. Seeded as system rows
# (organization_id IS NULL, is_system=True) by the initial migration.
SYSTEM_ROLES = (
    "SUPER_ADMIN",
    "ORG_ADMIN",
    "RECRUITER",
    "HIRING_MANAGER",
    "INTERVIEWER",
)


class Role(UUIDPrimaryKeyMixin, Base):
    """`organization_id IS NULL` means a system role, available to every
    organization. Kept nullable (rather than omitted) so a future
    org-defined custom role is an additive row, not a schema change.
    """

    __tablename__ = "roles"
    __table_args__ = (
        # Plain unique(organization_id, name) would NOT catch duplicate
        # system-role names, since NULLs are never equal to each other in a
        # standard btree unique index — hence two partial indexes instead.
        Index(
            "uq_roles_org_name",
            "organization_id",
            "name",
            unique=True,
            postgresql_where="organization_id IS NOT NULL",
        ),
        Index(
            "uq_roles_system_name",
            "name",
            unique=True,
            postgresql_where="organization_id IS NULL",
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Permission(UUIDPrimaryKeyMixin, Base):
    """Global reference data — not tenant-owned, no organization_id, no RLS."""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )

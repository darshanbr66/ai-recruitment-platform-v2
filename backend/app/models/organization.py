from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The tenant root. Every tenant-owned table carries an organization_id
    foreign key back to this table (see docs/database.md § 2-3).
    """

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, name="organization_status", native_enum=True),
        nullable=False,
        default=OrganizationStatus.ACTIVE,
        server_default=OrganizationStatus.ACTIVE.value,
    )
    # The recruitment team's public contact address — shown to candidates
    # on the careers site ("need to update your information?"), used as the
    # reply-to of system emails (verification code, welcome). Configured by
    # a platform administrator per organization, never hardcoded. NULL means
    # "not published": candidate-facing copy then omits the address.
    careers_contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

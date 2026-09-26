import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class OrganizationCreateRequest(BaseModel):
    """Creates an Organization and its first ORG_ADMIN user atomically —
    there is no other way to get a usable tenant, since a tenant with zero
    users has nobody able to manage it. Only a platform SUPER_ADMIN can call
    this (see app/api/deps.py::get_current_super_admin).
    """

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=63)
    admin_email: EmailStr
    admin_password: str = Field(min_length=10, max_length=128)
    admin_full_name: str = Field(min_length=1, max_length=255)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not _SLUG_RE.match(value):
            raise ValueError(
                "slug must be lowercase letters, digits, and single hyphens only "
                "(e.g. 'acme-corp')"
            )
        return value


class OrganizationSettingsUpdateRequest(BaseModel):
    """Company-level settings a platform SUPER_ADMIN manages. Only fields
    actually sent are changed (PATCH semantics); sending
    `careers_contact_email: null` (or "") un-publishes the address."""

    careers_contact_email: EmailStr | None = None

    @field_validator("careers_contact_email", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value.lower() if value else None
        return value


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    careers_contact_email: str | None = None
    created_at: datetime

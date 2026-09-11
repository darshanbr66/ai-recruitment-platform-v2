import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AssignableRole(StrEnum):
    """Roles an ORG_ADMIN may grant to a user within their own organization.

    SUPER_ADMIN is deliberately excluded — it is a platform-level role with
    no organization_id, never assignable through a tenant-scoped endpoint
    (see docs/architecture.md § 4).
    """

    ORG_ADMIN = "ORG_ADMIN"
    RECRUITER = "RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    INTERVIEWER = "INTERVIEWER"


class UserCreateRequest(BaseModel):
    """`organization_id` is intentionally absent — it is always derived from
    the authenticated caller, never accepted from the client
    (CLAUDE.md § 2, docs/security.md § 2: "Never trust organization_id
    supplied by clients").
    """

    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: AssignableRole


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    roles: list[str] = Field(default_factory=list)

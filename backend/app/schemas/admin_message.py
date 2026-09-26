import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

#: Hard schema ceiling; the configurable limit (ADMIN_MESSAGE_MAX_LENGTH)
#: is applied by the validator below and may only be lower.
_BODY_CEILING = 10_000


class AdminMessageCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=_BODY_CEILING)

    @field_validator("body")
    @classmethod
    def _clean_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty.")
        limit = get_settings().admin_message_max_length
        if len(value) > limit:
            raise ValueError(f"Message must be at most {limit} characters.")
        return value


class AdminMessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    body: str
    from_admin: bool
    sender_user_id: uuid.UUID | None
    sender_name: str | None
    created_at: datetime
    read_at: datetime | None


class AdminConversationSummary(BaseModel):
    id: uuid.UUID
    employee_user_id: uuid.UUID
    employee_name: str
    employee_email: str
    last_message_at: datetime | None
    last_message_preview: str | None
    last_message_from_admin: bool | None
    unread_count: int


class AdminConversationDetail(BaseModel):
    """`id` is None for a staff member who hasn't written yet."""

    id: uuid.UUID | None
    employee_user_id: uuid.UUID
    employee_name: str
    employee_email: str
    messages: list[AdminMessageResponse]


class AdminMessageUnreadCount(BaseModel):
    unread: int


class AdminMessageReadResult(BaseModel):
    updated: int

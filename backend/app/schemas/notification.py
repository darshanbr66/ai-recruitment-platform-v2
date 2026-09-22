import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationType

# One acknowledgement request never needs more than the poller's page size.
MAX_ACK_IDS = 100
MAX_ANNOUNCEMENT_RECIPIENTS = 200


class NotificationResponse(BaseModel):
    """The full Notification Center shape. `sender_name`/`sender_id` are
    populated by the service layer (joined, not on the ORM row itself) —
    `None` for a system-generated notification (assessment events, calendar
    reminders), shown in the UI as "System"."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    created_at: datetime
    read_at: datetime | None
    sender_id: uuid.UUID | None = None
    sender_name: str | None = None
    related_entity_type: str | None = None
    related_entity_id: uuid.UUID | None = None


class NotificationAcknowledgeRequest(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_ACK_IDS)


class NotificationAcknowledgeResult(BaseModel):
    """Rows newly marked read; ids that were already read, foreign or unknown
    are silently ignored, so acknowledging is safe to repeat."""

    updated: int


class UnreadCountResponse(BaseModel):
    unread: int


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=4000)
    target: Literal["EVERYONE", "DEPARTMENT", "EMPLOYEES"]
    department_id: uuid.UUID | None = None
    user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_ANNOUNCEMENT_RECIPIENTS)


class DirectMessageCreateRequest(BaseModel):
    recipient_user_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=4000)


class AnnouncementResult(BaseModel):
    recipients_notified: int


class SentNotificationResponse(BaseModel):
    """One entry per broadcast (an announcement's whole fan-out counts as
    one) for the Notification Center's "Sent" tab — never one row per
    recipient. See `in_app_notification_service.SentNotificationGroup`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    created_at: datetime
    target_description: str | None = None
    recipient_count: int
    read_count: int
    recipient_name: str | None = None

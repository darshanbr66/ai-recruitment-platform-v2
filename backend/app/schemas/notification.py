import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationType

# One acknowledgement request never needs more than the poller's page size.
MAX_ACK_IDS = 100


class NotificationResponse(BaseModel):
    """Deliberately carries only what the toast shows — the candidate's
    display name and assessment title are already inside `message`; no
    invitation id, token, email or score is exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    created_at: datetime
    read_at: datetime | None


class NotificationAcknowledgeRequest(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_ACK_IDS)


class NotificationAcknowledgeResult(BaseModel):
    """Rows newly marked read; ids that were already read, foreign or unknown
    are silently ignored, so acknowledging is safe to repeat."""

    updated: int

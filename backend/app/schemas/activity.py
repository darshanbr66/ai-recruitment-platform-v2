import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    entity_label: str | None
    description: str | None
    reason: str | None
    created_at: datetime


# Bounded so one request can't be an unbounded IN list; the activities list
# endpoint itself caps at 500 rows, so a selection can never exceed this.
MAX_BULK_DELETE = 500


class ActivityBulkDeleteRequest(BaseModel):
    activity_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_BULK_DELETE)


class ActivityDeleteAllRequest(BaseModel):
    """`confirm` must be true — a guard so an empty/malformed request can
    never be mistaken for "delete everything"."""

    confirm: bool = False


class ActivityDeleteResult(BaseModel):
    deleted: int


class ActivityCountResponse(BaseModel):
    total: int


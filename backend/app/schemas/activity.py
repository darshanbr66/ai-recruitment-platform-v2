import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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

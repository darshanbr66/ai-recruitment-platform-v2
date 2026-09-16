import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class NoteResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime

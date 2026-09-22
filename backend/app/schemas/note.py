import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.note import NoteVisibility

MAX_BODY_CHARS = 5000


class NoteCreateRequest(BaseModel):
    """Used by the application-scoped endpoint
    (`/applications/{id}/notes`) — `application_id` comes from the URL
    path, not the body. Defaults to SHARED, preserving exactly what every
    note on this endpoint already did before visibility existed."""

    body: str = Field(min_length=1, max_length=MAX_BODY_CHARS)
    title: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=30)
    visibility: NoteVisibility = NoteVisibility.SHARED


class StandaloneNoteCreateRequest(BaseModel):
    """Used by the standalone Notes workspace (`/recruiter/notes`) — every
    link is optional and explicit. Defaults to PRIVATE: a personal note a
    recruiter jots down is theirs alone unless they choose to share it."""

    body: str = Field(min_length=1, max_length=MAX_BODY_CHARS)
    title: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=30)
    visibility: NoteVisibility = NoteVisibility.PRIVATE
    application_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None


class NoteUpdateRequest(BaseModel):
    """Every field is optional; a field left out of the request body is
    left unchanged (the route layer uses `model_fields_set` to tell
    "omitted" from "explicitly set to null" for the nullable link fields)."""

    body: str | None = Field(default=None, min_length=1, max_length=MAX_BODY_CHARS)
    title: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=30)
    visibility: NoteVisibility | None = None
    application_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None


class NoteResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID | None
    candidate_id: uuid.UUID | None
    job_id: uuid.UUID | None
    author_id: uuid.UUID
    author_name: str
    title: str | None
    body: str
    category: str | None
    color: str | None
    visibility: NoteVisibility
    created_at: datetime
    updated_at: datetime

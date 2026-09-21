import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

# Limits are part of the public contract (docs/api.md): the frontend mirrors
# MAX_MESSAGE_CHARS, and the history bounds keep token use predictable.
MAX_MESSAGE_CHARS = 1000
MAX_HISTORY_MESSAGES = 10
MAX_HISTORY_MESSAGE_CHARS = 4000

_OrgSlug = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(min_length=1, max_length=MAX_HISTORY_MESSAGE_CHARS)]


class ChatRequest(BaseModel):
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)
    ]
    #: Correlates one conversation across requests (logs only — the server
    #: keeps no conversation state). Generated and returned when omitted.
    conversation_id: uuid.UUID | None = None
    #: The recent turns so the assistant can resolve "which one?". Held by the
    #: client, not stored server-side; only the most recent are used.
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)
    #: The careers site the visitor is on; defaults to the configured one.
    organization_slug: _OrgSlug | None = None


class ChatSource(BaseModel):
    id: str
    title: str
    type: Literal["knowledge", "job"]
    url: str | None = None


class ChatJobCard(BaseModel):
    """A public job Sigvi referred to. Only fields the anonymous careers page
    already exposes."""

    id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    employment_type: str | None
    summary: str | None
    organization_slug: str
    view_path: str
    apply_path: str


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: str
    sources: list[ChatSource] = Field(default_factory=list)
    jobs: list[ChatJobCard] = Field(default_factory=list)

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class AIProviderError(Exception):
    """Base for every AI-screening failure — provider unreachable, rejected
    the request, or returned output that couldn't be parsed as the expected
    structured result. Callers must surface this as a clear error, never
    fall back to a fabricated result (CLAUDE.md § 5: "no fake
    implementations")."""


class AIProviderNotConfiguredError(AIProviderError):
    """Raised instead of fabricating a screening result. Neither
    `ANTHROPIC_API_KEY` nor `OPENAI_API_KEY` is set."""


class ScreeningVerdict(BaseModel):
    """The structured result an `LLMProvider` must produce — persisted
    as-is onto `ScreeningRun` (app/models/screening.py). Presented in the
    UI as an AI-assisted opinion for a recruiter to review, never as an
    automatic decision (CLAUDE.md § 12 / docs/ai-screening.md)."""

    overall_score: int = Field(ge=0, le=100)
    recommendation: str
    summary: str
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    experience_assessment: str = ""
    education_assessment: str = ""


class LLMProvider(ABC):
    #: Short provider identifier persisted onto ScreeningRun.provider.
    name: str
    #: Model identifier persisted onto ScreeningRun.model.
    model: str

    @abstractmethod
    async def screen_candidate(
        self, *, resume_text: str, job_title: str, job_description: str
    ) -> ScreeningVerdict: ...


# --- Conversational (chat) capability ---------------------------------------
# A separate capability interface from `LLMProvider` (screening), sharing the
# same error hierarchy and factory pattern: a vendor that can chat need not be
# able to screen, and the screening providers stay untouched. The errors below
# are *internal* — callers map them to friendly user-facing messages and never
# forward their text (it may carry upstream detail).


class AIProviderAuthError(AIProviderError):
    """The provider rejected our credentials (missing/invalid/revoked key)."""


class AIProviderRateLimitError(AIProviderError):
    """The provider's quota / rate limit was hit."""


class AIProviderTimeoutError(AIProviderError):
    """The provider did not respond within the configured timeout."""


class AIProviderUnavailableError(AIProviderError):
    """The provider is unreachable or returned a server-side / unexpected error."""


class AIProviderEmptyResponseError(AIProviderError):
    """The provider answered successfully but with no usable text."""


class AIProviderBlockedError(AIProviderError):
    """The provider's own safety system declined to answer."""


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


class ChatProvider(ABC):
    #: Short provider identifier, for logs.
    name: str
    #: Model identifier, for logs.
    model: str

    @abstractmethod
    async def generate(
        self, *, system_prompt: str, messages: list[ChatMessage], max_output_tokens: int
    ) -> str:
        """Returns the assistant's reply text for the conversation so far
        (`messages` ends with the user's latest turn). Raises an
        `AIProviderError` subclass on any failure — never fabricates text."""


# --- Embedding capability -----------------------------------------------
# A third, independent capability interface — resume/job-requirement text ->
# vectors for the internal AI matching/RAG pipeline (docs/ai-screening.md
# § 5, § 6: the long-deferred "which embedding provider" decision). Shares
# the same error hierarchy; unrelated to LLMProvider (screening verdicts)
# and ChatProvider (Sigvi) so neither is touched by this addition.

EmbeddingTaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


class EmbeddingProvider(ABC):
    #: Short provider identifier, persisted onto ResumeChunk/MatchResult rows.
    name: str
    #: Model identifier, persisted alongside `name`.
    model: str
    #: Length of every vector this provider returns — must match the
    #: `Vector(N)` column width the schema was created with.
    dimension: int

    @abstractmethod
    async def embed(
        self, texts: list[str], *, task_type: EmbeddingTaskType = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        """Returns one embedding vector per input text, same order, each of
        length `self.dimension`. `task_type` distinguishes text being stored
        for later retrieval (`RETRIEVAL_DOCUMENT`, e.g. a resume chunk) from
        text used to search for it (`RETRIEVAL_QUERY`, e.g. a job
        requirement) — providers that support asymmetric optimization use it
        to improve match quality; providers that don't may ignore it. Raises
        an `AIProviderError` subclass on any failure — never returns a
        fabricated or zero vector."""

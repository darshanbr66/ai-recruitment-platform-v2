from abc import ABC, abstractmethod

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

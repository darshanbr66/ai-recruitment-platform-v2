from app.core.config import get_settings
from app.integrations.ai.anthropic_provider import AnthropicLLMProvider
from app.integrations.ai.base import (
    AIProviderError,
    AIProviderNotConfiguredError,
    LLMProvider,
    ScreeningVerdict,
)
from app.integrations.ai.openai_provider import OpenAILLMProvider

__all__ = [
    "AIProviderError",
    "AIProviderNotConfiguredError",
    "LLMProvider",
    "ScreeningVerdict",
    "AnthropicLLMProvider",
    "OpenAILLMProvider",
    "get_llm_provider",
]


class _UnconfiguredLLMProvider(LLMProvider):
    name = "none"
    model = "none"

    async def screen_candidate(
        self, *, resume_text: str, job_title: str, job_description: str
    ) -> ScreeningVerdict:
        raise AIProviderNotConfiguredError(
            "No AI provider is configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "to enable AI screening (see README)."
        )


def get_llm_provider() -> LLMProvider:
    """Anthropic is preferred when both are set — arbitrary but
    deterministic; an organization only ever configures one in practice."""
    settings = get_settings()
    if settings.anthropic_api_key:
        return AnthropicLLMProvider(api_key=settings.anthropic_api_key)
    if settings.openai_api_key:
        return OpenAILLMProvider(api_key=settings.openai_api_key)
    return _UnconfiguredLLMProvider()

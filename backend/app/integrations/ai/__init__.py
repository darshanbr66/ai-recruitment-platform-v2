from app.core.config import get_settings
from app.integrations.ai.anthropic_provider import AnthropicLLMProvider
from app.integrations.ai.base import (
    AIProviderError,
    AIProviderNotConfiguredError,
    LLMProvider,
    ScreeningVerdict,
)
from app.integrations.ai.ollama_provider import OllamaLLMProvider
from app.integrations.ai.openai_provider import OpenAILLMProvider

__all__ = [
    "AIProviderError",
    "AIProviderNotConfiguredError",
    "LLMProvider",
    "ScreeningVerdict",
    "AnthropicLLMProvider",
    "OpenAILLMProvider",
    "OllamaLLMProvider",
    "get_llm_provider",
]


class _UnconfiguredLLMProvider(LLMProvider):
    name = "none"
    model = "none"

    async def screen_candidate(
        self, *, resume_text: str, job_title: str, job_description: str
    ) -> ScreeningVerdict:
        raise AIProviderNotConfiguredError(
            "AI screening is currently unavailable because no AI provider is configured. "
            "Set OLLAMA_BASE_URL for a free local model, or ANTHROPIC_API_KEY / "
            "OPENAI_API_KEY for a paid provider (see README)."
        )


def get_llm_provider() -> LLMProvider:
    """Free/local Ollama is preferred when explicitly enabled
    (`OLLAMA_BASE_URL` set) — no per-request cost, no API key, nothing
    sent to a third party. Falls back to a paid provider only if the
    caller configured one instead; Anthropic wins if both paid keys are
    set (arbitrary but deterministic — an organization only ever
    configures one in practice)."""
    settings = get_settings()
    if settings.ollama_base_url:
        return OllamaLLMProvider(base_url=settings.ollama_base_url, model=settings.ollama_model)
    if settings.anthropic_api_key:
        return AnthropicLLMProvider(api_key=settings.anthropic_api_key)
    if settings.openai_api_key:
        return OpenAILLMProvider(api_key=settings.openai_api_key)
    return _UnconfiguredLLMProvider()

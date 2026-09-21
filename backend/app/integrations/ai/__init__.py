from app.core.config import get_settings
from app.integrations.ai.anthropic_provider import AnthropicLLMProvider
from app.integrations.ai.base import (
    AIProviderAuthError,
    AIProviderBlockedError,
    AIProviderEmptyResponseError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    ChatMessage,
    ChatProvider,
    LLMProvider,
    ScreeningVerdict,
)
from app.integrations.ai.gemini_provider import GeminiChatProvider
from app.integrations.ai.ollama_provider import OllamaLLMProvider
from app.integrations.ai.openai_provider import OpenAILLMProvider

__all__ = [
    "AIProviderAuthError",
    "AIProviderBlockedError",
    "AIProviderEmptyResponseError",
    "AIProviderError",
    "AIProviderNotConfiguredError",
    "AIProviderRateLimitError",
    "AIProviderTimeoutError",
    "AIProviderUnavailableError",
    "ChatMessage",
    "ChatProvider",
    "GeminiChatProvider",
    "LLMProvider",
    "ScreeningVerdict",
    "AnthropicLLMProvider",
    "OpenAILLMProvider",
    "OllamaLLMProvider",
    "get_chat_provider",
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


class _UnconfiguredChatProvider(ChatProvider):
    name = "none"
    model = "none"

    async def generate(
        self, *, system_prompt: str, messages: list[ChatMessage], max_output_tokens: int
    ) -> str:
        raise AIProviderNotConfiguredError("No chat provider is configured (GEMINI_API_KEY).")


def get_chat_provider() -> ChatProvider:
    """The provider behind Sigvi, the public assistant. Gemini when
    `GEMINI_API_KEY` is set; otherwise a provider that raises — the endpoint
    then reports "temporarily unavailable" instead of inventing an answer.
    To add another vendor, implement `ChatProvider` and select it here."""
    settings = get_settings()
    api_key = settings.gemini_api_key.get_secret_value().strip() if settings.gemini_api_key else ""
    if api_key:
        return GeminiChatProvider(
            api_key=api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.sigvi_request_timeout_seconds,
        )
    return _UnconfiguredChatProvider()

"""AI provider selection: free/local Ollama is preferred when explicitly
enabled; paid providers are only used as a fallback; nothing is ever
fabricated when unreachable/unconfigured (CLAUDE.md § 12)."""

import pytest

import app.integrations.ai as ai_module
from app.core.config import Settings, get_settings
from app.integrations.ai import (
    AnthropicLLMProvider,
    OllamaLLMProvider,
    OpenAILLMProvider,
    get_llm_provider,
)
from app.integrations.ai.base import AIProviderError


@pytest.fixture
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings_with(**overrides) -> Settings:
    base = get_settings()
    return base.model_copy(update=overrides)


async def test_ollama_is_preferred_when_configured(monkeypatch, clear_settings_cache) -> None:
    monkeypatch.setattr(
        "app.integrations.ai.get_settings",
        lambda: _settings_with(
            ollama_base_url="http://localhost:11434",
            anthropic_api_key="sk-test",
            openai_api_key="sk-test",
        ),
    )
    provider = get_llm_provider()
    assert isinstance(provider, OllamaLLMProvider)


async def test_anthropic_used_when_ollama_not_set(monkeypatch, clear_settings_cache) -> None:
    monkeypatch.setattr(
        "app.integrations.ai.get_settings",
        lambda: _settings_with(
            ollama_base_url=None, anthropic_api_key="sk-test", openai_api_key="sk-test"
        ),
    )
    provider = get_llm_provider()
    assert isinstance(provider, AnthropicLLMProvider)


async def test_openai_used_when_only_openai_set(monkeypatch, clear_settings_cache) -> None:
    monkeypatch.setattr(
        "app.integrations.ai.get_settings",
        lambda: _settings_with(ollama_base_url=None, anthropic_api_key=None, openai_api_key="sk-test"),
    )
    provider = get_llm_provider()
    assert isinstance(provider, OpenAILLMProvider)


async def test_unconfigured_when_nothing_set(monkeypatch, clear_settings_cache) -> None:
    monkeypatch.setattr(
        "app.integrations.ai.get_settings",
        lambda: _settings_with(ollama_base_url=None, anthropic_api_key=None, openai_api_key=None),
    )
    provider = get_llm_provider()
    assert isinstance(provider, ai_module._UnconfiguredLLMProvider)


async def test_ollama_connection_failure_raises_not_fabricates() -> None:
    """Points at a port nothing is listening on — must raise, never return
    a fake ScreeningVerdict."""
    provider = OllamaLLMProvider(base_url="http://localhost:1", model="llama3.1")
    with pytest.raises(AIProviderError):
        await provider.screen_candidate(
            resume_text="...", job_title="Engineer", job_description="..."
        )

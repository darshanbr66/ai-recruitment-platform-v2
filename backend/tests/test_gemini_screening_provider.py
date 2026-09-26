"""`GeminiLLMProvider` — resume screening through Gemini's structured-output
API. The HTTP layer is faked with `httpx.MockTransport`: tests never reach
the real Gemini API, and no real key is used.

Covers: the request it sends (shared screening prompt, JSON schema, auth
header), a well-formed verdict, score clamping, malformed/incomplete replies
and upstream errors surfacing as `AIProviderError`s (never a fabricated
verdict), and when `get_llm_provider()` selects it.
"""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

import app.integrations.ai as ai_module
from app.core.config import Settings, get_settings
from app.integrations.ai import (
    AIProviderAuthError,
    AIProviderBlockedError,
    AIProviderEmptyResponseError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AnthropicLLMProvider,
    GeminiLLMProvider,
    ScreeningVerdict,
    get_llm_provider,
)
from app.integrations.ai import internal_ai_reasoning_provider as reasoning_module
from app.integrations.ai.gemini_screening_provider import RESPONSE_SCHEMA
from app.integrations.ai.prompts import SYSTEM_PROMPT

FAKE_KEY = "test-gemini-key-not-real"
_REAL_ASYNC_CLIENT = httpx.AsyncClient

VERDICT: dict[str, Any] = {
    "decision": "MATCH",
    "overall_score": 82,
    "recommendation": "STRONG_MATCH",
    "summary": "Solid backend profile for the role.",
    "matched_requirements": ["Python", "PostgreSQL"],
    "missing_requirements": ["Kubernetes"],
    "matching_skills": ["Python", "FastAPI"],
    "missing_skills": ["Kubernetes"],
    "strengths": ["4 years of backend work"],
    "concerns": ["No container orchestration experience"],
    "experience_assessment": "Meets the experience bar.",
    "education_assessment": "Relevant degree.",
}


def _provider_with(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    thinking_budget: int | None = None,
) -> GeminiLLMProvider:
    def factory(**kwargs: Any) -> httpx.AsyncClient:
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(reasoning_module.httpx, "AsyncClient", factory)
    return GeminiLLMProvider(
        api_key=FAKE_KEY, model="gemini-test", timeout_seconds=5, thinking_budget=thinking_budget
    )


def _replying(payload: Any) -> Callable[[httpx.Request], httpx.Response]:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return lambda _request: httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]},
    )


async def _screen(provider: GeminiLLMProvider) -> ScreeningVerdict:
    return await provider.screen_candidate(
        resume_text="Jane. Python, PostgreSQL, FastAPI. 4 years.",
        job_title="Backend Engineer",
        job_description="Python, PostgreSQL, Kubernetes.",
    )


async def test_sends_the_shared_prompt_with_the_verdict_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return _replying(VERDICT)(request)

    verdict = await _screen(_provider_with(monkeypatch, handler))

    assert seen["url"].endswith("/models/gemini-test:generateContent")
    assert seen["key"] == FAKE_KEY
    assert FAKE_KEY not in seen["url"]  # the key travels in a header, never the URL
    body = seen["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == SYSTEM_PROMPT
    user_text = body["contents"][0]["parts"][0]["text"]
    assert "Backend Engineer" in user_text and "Kubernetes" in user_text and "Jane" in user_text
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseSchema"] == RESPONSE_SCHEMA
    assert config["maxOutputTokens"] == 2048
    assert "thinkingConfig" not in config  # only sent when a budget is configured

    assert verdict.decision == "MATCH"
    assert verdict.overall_score == 82
    assert verdict.matched_requirements == ["Python", "PostgreSQL"]
    assert verdict.missing_requirements == ["Kubernetes"]


async def test_not_match_verdict_is_returned_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = VERDICT | {
        "decision": "NOT_MATCH",
        "overall_score": 14,
        "recommendation": "NOT_A_MATCH",
        "matched_requirements": [],
    }
    verdict = await _screen(_provider_with(monkeypatch, _replying(reply)))
    assert verdict.decision == "NOT_MATCH"
    assert verdict.overall_score == 14
    assert verdict.matched_requirements == []


async def test_missing_decision_is_derived_from_the_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = {k: v for k, v in VERDICT.items() if k != "decision"}
    for recommendation, expected in (("STRONG_MATCH", "MATCH"), ("NOT_A_MATCH", "NOT_MATCH")):
        verdict = await _screen(
            _provider_with(monkeypatch, _replying(reply | {"recommendation": recommendation}))
        )
        assert verdict.decision == expected


@pytest.mark.parametrize(("returned", "stored"), [(140, 100), (-5, 0)])
async def test_out_of_range_score_is_clamped(
    monkeypatch: pytest.MonkeyPatch, returned: int, stored: int
) -> None:
    verdict = await _screen(
        _provider_with(monkeypatch, _replying(VERDICT | {"overall_score": returned}))
    )
    assert verdict.overall_score == stored


async def test_thinking_budget_zero_is_sent_and_the_json_verdict_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """gemini-2.5-flash counts thinking tokens against maxOutputTokens; with
    thinking disabled the full budget goes to the structured verdict."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["config"] = json.loads(request.content)["generationConfig"]
        return _replying(VERDICT)(request)

    verdict = await _screen(_provider_with(monkeypatch, handler, thinking_budget=0))

    assert seen["config"]["thinkingConfig"] == {"thinkingBudget": 0}
    assert seen["config"]["maxOutputTokens"] == 2048
    assert seen["config"]["responseSchema"] == RESPONSE_SCHEMA
    assert verdict.decision == "MATCH"
    assert verdict.matched_requirements == ["Python", "PostgreSQL"]


async def test_reply_truncated_at_the_token_limit_is_an_error_not_a_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    truncated = json.dumps(VERDICT)[:120]
    response = httpx.Response(
        200,
        json={
            "candidates": [
                {"content": {"parts": [{"text": truncated}]}, "finishReason": "MAX_TOKENS"}
            ]
        },
    )
    with pytest.raises(AIProviderEmptyResponseError):
        await _screen(_provider_with(monkeypatch, lambda _request: response, thinking_budget=0))


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        ("this is not json", AIProviderEmptyResponseError),
        ('["a", "list"]', AIProviderEmptyResponseError),
        ({k: v for k, v in VERDICT.items() if k != "summary"}, AIProviderError),
        (VERDICT | {"decision": "MAYBE"}, AIProviderError),
        (VERDICT | {"overall_score": "high"}, AIProviderError),
    ],
    ids=["not-json", "not-an-object", "missing-summary", "invalid-decision", "non-numeric-score"],
)
async def test_malformed_reply_is_an_error_never_a_guessed_verdict(
    monkeypatch: pytest.MonkeyPatch, reply: Any, error: type[AIProviderError]
) -> None:
    with pytest.raises(error):
        await _screen(_provider_with(monkeypatch, _replying(reply)))


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (
            httpx.Response(401, json={"error": {"status": "UNAUTHENTICATED"}}),
            AIProviderAuthError,
        ),
        (
            httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}}),
            AIProviderRateLimitError,
        ),
        (
            httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
            AIProviderBlockedError,
        ),
        (httpx.Response(200, json={"candidates": []}), AIProviderEmptyResponseError),
    ],
    ids=["auth", "rate-limit", "blocked", "empty"],
)
async def test_upstream_failures_surface_as_provider_errors(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response, error: type[AIProviderError]
) -> None:
    with pytest.raises(error):
        await _screen(_provider_with(monkeypatch, lambda _request: response))


async def test_timeout_surfaces_as_provider_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(AIProviderTimeoutError):
        await _screen(_provider_with(monkeypatch, handler))


# --- selection -----------------------------------------------------------------------


@pytest.fixture
def settings_with(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    def apply(**overrides: object) -> None:
        patched: Settings = get_settings().model_copy(update=overrides)
        monkeypatch.setattr(ai_module, "get_settings", lambda: patched)

    return apply


def test_gemini_is_the_fallback_when_only_its_key_is_set(settings_with) -> None:
    settings_with(
        ollama_base_url=None,
        anthropic_api_key=None,
        openai_api_key=None,
        gemini_api_key=SecretStr(FAKE_KEY),
    )
    provider = get_llm_provider()
    assert isinstance(provider, GeminiLLMProvider)
    assert provider.name == "gemini"


def test_a_dedicated_screening_provider_takes_precedence_over_gemini(settings_with) -> None:
    settings_with(
        ollama_base_url=None,
        anthropic_api_key="sk-test",
        openai_api_key=None,
        gemini_api_key=SecretStr(FAKE_KEY),
    )
    assert isinstance(get_llm_provider(), AnthropicLLMProvider)


def test_blank_gemini_key_does_not_select_gemini(settings_with) -> None:
    settings_with(
        ollama_base_url=None,
        anthropic_api_key=None,
        openai_api_key=None,
        gemini_api_key=SecretStr("   "),
    )
    assert isinstance(get_llm_provider(), ai_module._UnconfiguredLLMProvider)


def test_gemini_screening_uses_its_own_model_and_thinking_budget(settings_with) -> None:
    settings_with(
        ollama_base_url=None,
        anthropic_api_key=None,
        openai_api_key=None,
        gemini_api_key=SecretStr(FAKE_KEY),
        gemini_model="sigvi-model",
        gemini_screening_model="screening-model",
        gemini_screening_thinking_budget=0,
    )
    provider = get_llm_provider()
    assert isinstance(provider, GeminiLLMProvider)
    assert provider.model == "screening-model"
    assert provider._thinking_budget == 0


def test_screening_model_defaults_to_gemini_2_5_flash_without_thinking() -> None:
    settings = _bare_settings()
    assert settings.gemini_screening_model == "gemini-2.5-flash"
    assert settings.gemini_screening_thinking_budget == 0


def test_blank_thinking_budget_means_no_thinking_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_SCREENING_THINKING_BUDGET", "")
    assert _bare_settings().gemini_screening_thinking_budget is None


def _bare_settings() -> Settings:
    """Settings from code defaults + process env only (no .env file)."""
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret_key="x" * 32,
    )

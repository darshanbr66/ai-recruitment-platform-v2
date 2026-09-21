"""Google Gemini chat provider — a plain authenticated POST to the
`generateContent` REST endpoint, no SDK dependency (mirrors
anthropic_provider.py / email/resend_provider.py). The API key travels in the
`x-goog-api-key` header, never the URL, so it can't surface in access logs or
httpx error strings."""

from typing import Any

import httpx

from app.core.logging import get_logger
from app.integrations.ai.base import (
    AIProviderAuthError,
    AIProviderBlockedError,
    AIProviderEmptyResponseError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    ChatMessage,
    ChatProvider,
)

logger = get_logger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_BLOCKED_FINISH_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}


class GeminiChatProvider(ChatProvider):
    name = "gemini"

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float = 20.0) -> None:
        self._api_key = api_key
        self.model = model
        self._timeout = timeout_seconds

    async def generate(
        self, *, system_prompt: str, messages: list[ChatMessage], max_output_tokens: int
    ) -> str:
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {
                    "role": "user" if message.role == "user" else "model",
                    "parts": [{"text": message.content}],
                }
                for message in messages
            ],
            "generationConfig": {"maxOutputTokens": max_output_tokens, "temperature": 0.4},
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{_BASE_URL}/{self.model}:generateContent",
                    headers={"x-goog-api-key": self._api_key, "content-type": "application/json"},
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError("Gemini request timed out.") from exc
        except httpx.HTTPError as exc:
            # Only the exception type — its text can echo the request URL.
            raise AIProviderUnavailableError(
                f"Could not reach Gemini ({type(exc).__name__})."
            ) from exc

        if response.status_code >= 400:
            raise _error_for_status(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise AIProviderUnavailableError("Gemini returned a non-JSON response.") from exc
        return _extract_text(payload)


def _upstream_error(response: httpx.Response) -> tuple[str, str]:
    try:
        error = response.json().get("error", {})
        return str(error.get("status", "")), str(error.get("message", ""))[:300]
    except (ValueError, AttributeError):
        return "", ""


def _error_for_status(response: httpx.Response) -> AIProviderError:
    status = response.status_code
    upstream_status, upstream_message = _upstream_error(response)
    # Server-side diagnosis only: status + Gemini's own error status/message
    # (never the request, which holds the conversation, nor the key).
    logger.warning(
        "Gemini request failed",
        extra={
            "extra_fields": {
                "status_code": status,
                "upstream_status": upstream_status,
                "upstream_message": upstream_message,
            }
        },
    )
    key_rejected = "API key" in upstream_message or upstream_status == "UNAUTHENTICATED"
    if status in (401, 403) or key_rejected:
        return AIProviderAuthError(f"Gemini rejected the credentials ({status}).")
    if status == 429:
        return AIProviderRateLimitError("Gemini rate limit or quota reached.")
    return AIProviderUnavailableError(f"Gemini returned an error ({status}).")


def _extract_text(payload: dict[str, Any]) -> str:
    block_reason = (payload.get("promptFeedback") or {}).get("blockReason")
    if block_reason:
        raise AIProviderBlockedError(f"Gemini blocked the prompt ({block_reason}).")

    candidates = payload.get("candidates") or []
    if not candidates:
        raise AIProviderEmptyResponseError("Gemini returned no candidates.")

    candidate = candidates[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if text:
        return text

    if candidate.get("finishReason") in _BLOCKED_FINISH_REASONS:
        raise AIProviderBlockedError(f"Gemini declined to answer ({candidate['finishReason']}).")
    raise AIProviderEmptyResponseError("Gemini returned an empty response.")

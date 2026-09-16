import json

import httpx
from pydantic import ValidationError

from app.integrations.ai.base import AIProviderError, LLMProvider, ScreeningVerdict
from app.integrations.ai.prompts import SYSTEM_PROMPT, build_user_prompt

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_MODEL = "claude-sonnet-4-5"


class AnthropicLLMProvider(LLMProvider):
    """Real integration against Anthropic's Messages API — a plain
    authenticated POST, no SDK dependency (mirrors
    app/integrations/email/resend_provider.py's approach)."""

    name = "anthropic"
    model = _MODEL

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def screen_candidate(
        self, *, resume_text: str, job_title: str, job_description: str
    ) -> ScreeningVerdict:
        user_prompt = build_user_prompt(
            resume_text=resume_text, job_title=job_title, job_description=job_description
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    _API_URL,
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": _API_VERSION,
                        "content-type": "application/json",
                    },
                    json={
                        "model": _MODEL,
                        "max_tokens": 1500,
                        "system": SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
            except httpx.HTTPError as exc:
                raise AIProviderError(f"Could not reach Anthropic: {exc}") from exc

        if response.status_code >= 400:
            raise AIProviderError(
                f"Anthropic rejected the request ({response.status_code}): {response.text}"
            )

        body = response.json()
        try:
            text = "".join(
                block["text"] for block in body["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise AIProviderError("Anthropic returned an unexpected response shape.") from exc

        return _parse_verdict(text)


def _parse_verdict(text: str) -> ScreeningVerdict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
        return ScreeningVerdict.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AIProviderError(
            "Could not parse the AI provider's response as a structured screening result."
        ) from exc

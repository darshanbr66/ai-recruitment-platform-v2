import json

import httpx
from pydantic import ValidationError

from app.integrations.ai.base import AIProviderError, LLMProvider, ScreeningVerdict
from app.integrations.ai.prompts import SYSTEM_PROMPT, build_user_prompt

_API_URL = "https://api.openai.com/v1/chat/completions"
_MODEL = "gpt-4o-mini"


class OpenAILLMProvider(LLMProvider):
    """Real integration against OpenAI's Chat Completions API — a plain
    authenticated POST, no SDK dependency. Used when `OPENAI_API_KEY` is
    set and `ANTHROPIC_API_KEY` is not (see
    app/integrations/ai/__init__.py::get_llm_provider)."""

    name = "openai"
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
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": _MODEL,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
            except httpx.HTTPError as exc:
                raise AIProviderError(f"Could not reach OpenAI: {exc}") from exc

        if response.status_code >= 400:
            raise AIProviderError(
                f"OpenAI rejected the request ({response.status_code}): {response.text}"
            )

        body = response.json()
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("OpenAI returned an unexpected response shape.") from exc

        try:
            data = json.loads(text)
            return ScreeningVerdict.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AIProviderError(
                "Could not parse the AI provider's response as a structured screening result."
            ) from exc

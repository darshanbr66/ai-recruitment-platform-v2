import json

import httpx
from pydantic import ValidationError

from app.integrations.ai.base import AIProviderError, LLMProvider, ScreeningVerdict
from app.integrations.ai.prompts import SYSTEM_PROMPT, build_user_prompt


class OllamaLLMProvider(LLMProvider):
    """Free/local integration against a locally-running Ollama server
    (https://ollama.com) — no API key, no per-request cost. Preferred over
    the paid providers when configured (see
    app/integrations/ai/__init__.py::get_llm_provider), matching the
    project's "prefer free/local models where practical" rule. Requires
    Ollama running locally with the configured model already pulled
    (`ollama pull <model>`) — a connection failure surfaces as a normal
    AIProviderError, not a fabricated result.
    """

    name = "ollama"

    def __init__(self, *, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self.model = model

    async def screen_candidate(
        self, *, resume_text: str, job_title: str, job_description: str
    ) -> ScreeningVerdict:
        user_prompt = build_user_prompt(
            resume_text=resume_text, job_title=job_title, job_description=job_description
        )

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json={
                        "model": self.model,
                        "stream": False,
                        "format": "json",
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
            except httpx.HTTPError as exc:
                raise AIProviderError(
                    f"Could not reach the local Ollama server at {self._base_url}: {exc}"
                ) from exc

        if response.status_code >= 400:
            raise AIProviderError(
                f"Ollama rejected the request ({response.status_code}): {response.text}"
            )

        body = response.json()
        try:
            text = body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise AIProviderError("Ollama returned an unexpected response shape.") from exc

        try:
            data = json.loads(text)
            return ScreeningVerdict.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AIProviderError(
                "Could not parse the local model's response as a structured screening result. "
                "Try a model better suited to JSON output (e.g. llama3.1, qwen2.5)."
            ) from exc

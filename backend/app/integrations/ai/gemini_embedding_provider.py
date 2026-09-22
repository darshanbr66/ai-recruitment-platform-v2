"""Google Gemini embedding provider — a plain authenticated POST to the
`batchEmbedContents` REST endpoint, no SDK dependency (mirrors
gemini_provider.py exactly: same base URL family, same `x-goog-api-key`
header, same error mapping shape). Reuses `GEMINI_API_KEY` — no new secret.

Model: `gemini-embedding-001`, the current generally-available Gemini text
embedding model (successor to `text-embedding-004`; verified against
https://ai.google.dev/gemini-api/docs/embeddings at implementation time).
Its native output is 3072-dimensional, but it uses Matryoshka Representation
Learning, which means the API can truncate to a smaller, still-well-formed
vector via `outputDimensionality` — Google's own docs recommend 768, 1536 or
3072 for "optimal performance"; this integration uses 768 (`gemini_embedding_
dimensions` in Settings) to keep `resume_chunks.embedding` and its similarity
index compact, which matters more than the last few points of retrieval
quality at this stage.
"""

from typing import Any

import httpx

from app.core.logging import get_logger
from app.integrations.ai.base import (
    AIProviderAuthError,
    AIProviderEmptyResponseError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    EmbeddingProvider,
    EmbeddingTaskType,
)

logger = get_logger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
# The API accepts at most 100 requests per batchEmbedContents call.
_MAX_BATCH_SIZE = 100


class GeminiEmbeddingProvider(EmbeddingProvider):
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.dimension = dimension
        self._timeout = timeout_seconds

    async def embed(
        self, texts: list[str], *, task_type: EmbeddingTaskType = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for start in range(0, len(texts), _MAX_BATCH_SIZE):
                batch = texts[start : start + _MAX_BATCH_SIZE]
                vectors.extend(await self._embed_batch(client, batch, task_type=task_type))
        return vectors

    async def _embed_batch(
        self, client: httpx.AsyncClient, batch: list[str], *, task_type: EmbeddingTaskType
    ) -> list[list[float]]:
        body: dict[str, Any] = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": task_type,
                    "outputDimensionality": self.dimension,
                }
                for text in batch
            ]
        }

        try:
            response = await client.post(
                f"{_BASE_URL}/{self.model}:batchEmbedContents",
                headers={"x-goog-api-key": self._api_key, "content-type": "application/json"},
                json=body,
            )
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError("Gemini embedding request timed out.") from exc
        except httpx.HTTPError as exc:
            raise AIProviderUnavailableError(
                f"Could not reach Gemini ({type(exc).__name__})."
            ) from exc

        if response.status_code >= 400:
            raise _error_for_status(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise AIProviderUnavailableError("Gemini returned a non-JSON response.") from exc

        embeddings = payload.get("embeddings") or []
        if len(embeddings) != len(batch):
            raise AIProviderEmptyResponseError(
                "Gemini returned a different number of embeddings than requested."
            )
        vectors: list[list[float]] = []
        for item in embeddings:
            values = (item or {}).get("values")
            if not values:
                raise AIProviderEmptyResponseError("Gemini returned an empty embedding.")
            vectors.append([float(v) for v in values])
        return vectors


def _upstream_error(response: httpx.Response) -> tuple[str, str]:
    try:
        error = response.json().get("error", {})
        return str(error.get("status", "")), str(error.get("message", ""))[:300]
    except (ValueError, AttributeError):
        return "", ""


def _error_for_status(response: httpx.Response) -> AIProviderError:
    status = response.status_code
    upstream_status, upstream_message = _upstream_error(response)
    logger.warning(
        "Gemini embedding request failed",
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

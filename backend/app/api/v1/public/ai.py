"""Sigvi, the public AI assistant. Anonymous by design (visitors to the
careers site have no account); protected instead by input limits and rate
limits, and by what the assistant is able to see at all — see
app/services/sigvi_service.py. The browser only ever talks to this endpoint;
the provider key stays server-side."""

from functools import lru_cache

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import TooManyRequestsError
from app.core.rate_limit import SlidingWindowRateLimiter
from app.db.session import get_db
from app.integrations.ai import ChatProvider, get_chat_provider
from app.schemas.sigvi import ChatRequest, ChatResponse
from app.services import sigvi_service

router = APIRouter(prefix="/ai", tags=["public-ai"])

RATE_LIMITED_MESSAGE = "You're sending messages quickly. Please wait a moment and try again."


class SigviRateLimiters:
    def __init__(self, *, per_client: int, global_limit: int) -> None:
        self.per_client = SlidingWindowRateLimiter(limit=per_client)
        self.everyone = SlidingWindowRateLimiter(limit=global_limit)


@lru_cache
def get_sigvi_rate_limiters() -> SigviRateLimiters:
    settings = get_settings()
    return SigviRateLimiters(
        per_client=settings.sigvi_rate_limit_per_minute,
        global_limit=settings.sigvi_global_rate_limit_per_minute,
    )


def _client_key(request: Request) -> str:
    """Behind Render's proxy `request.client` is the proxy, so the caller's
    address is the first `X-Forwarded-For` entry. That header is
    client-controlled at its left end, so the per-client budget alone can be
    dodged by rotating it — the global budget is the backstop."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    provider: ChatProvider = Depends(get_chat_provider),
    limiters: SigviRateLimiters = Depends(get_sigvi_rate_limiters),
) -> ChatResponse:
    if not limiters.per_client.allow(_client_key(request)) or not limiters.everyone.allow("*"):
        raise TooManyRequestsError(RATE_LIMITED_MESSAGE, code="rate_limited")
    return await sigvi_service.answer_chat(db, provider, payload)

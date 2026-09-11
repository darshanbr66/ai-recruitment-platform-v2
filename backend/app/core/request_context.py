"""Per-request context propagated through logging and (from Phase 2 onward)
tenant-scoped DB sessions.

Kept as a small, dependency-free contextvar module so both the ASGI
middleware and the logging formatter can read/write it without importing
FastAPI-specific types.
"""

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def get_request_id() -> str | None:
    return _request_id.get()

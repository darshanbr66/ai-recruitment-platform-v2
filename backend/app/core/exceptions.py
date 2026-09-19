"""Application exceptions and their FastAPI handlers.

Every error response uses one consistent envelope and never leaks internal
detail (stack traces, SQL/ORM error text, file paths) to the client — those
go to structured logs keyed by request_id instead.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.core.request_context import get_request_id

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for application-raised errors that map to a clean HTTP
    response. Domain/service code should raise a subclass of this rather
    than a bare HTTPException, so the error envelope stays consistent
    regardless of which layer raised it.
    """

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class UnprocessableError(AppError):
    """The request was well-formed but can't be acted on as written (e.g. an
    email that still contains unfilled placeholders)."""

    status_code = 422
    code = "validation_error"


class ServiceUnavailableError(AppError):
    """A required capability isn't configured on this deployment (e.g. no
    SMTP settings) — a server-side condition the caller cannot fix."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"


class BadGatewayError(AppError):
    """An upstream provider (e.g. the SMTP server) failed or refused the
    request."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "bad_gateway"


def _error_body(code: str, message: str, *, details: list[dict[str, str]] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": get_request_id(),
        }
    }
    if details:
        body["error"]["details"] = details
    return body


def _format_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Turns Pydantic's `exc.errors()` into a small, safe, human-readable
    list — field path (e.g. "questions[2].options[1].label") plus message
    (e.g. "String should have at least 1 character"). Pydantic's own `msg`
    text never contains stack traces/SQL/file paths, so it is safe to send
    to the client — this is the one place the UI can show the recruiter
    *what* was wrong instead of a dead-end generic error (CLAUDE.md § 5:
    strong validation, useful errors, not a weaker schema).
    """
    details: list[dict[str, str]] = []
    for err in errors:
        parts: list[str] = []
        for segment in err.get("loc", ()):
            if segment == "body":
                continue
            if isinstance(segment, int):
                parts[-1] = f"{parts[-1]}[{segment}]" if parts else f"[{segment}]"
            else:
                parts.append(str(segment))
        field = ".".join(parts) if parts else "(request)"
        details.append({"field": field, "message": str(err.get("msg", "Invalid value."))})
    return details


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("http_error", detail),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = _format_validation_errors(exc.errors())
        logger.info(
            "Request validation failed", extra={"extra_fields": {"errors": details}}
        )
        summary = "; ".join(f"{d['field']}: {d['message']}" for d in details[:5]) or "Request validation failed."
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("validation_error", summary, details=details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", extra={"extra_fields": {"error": str(exc)}})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "An unexpected error occurred."),
        )

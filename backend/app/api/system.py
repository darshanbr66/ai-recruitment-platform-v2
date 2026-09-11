"""Unversioned/system endpoints: liveness and readiness.

Not audience-partitioned like /api/v1/{public,candidate,recruiter,admin} —
these are infrastructure probes, not product API surface.
"""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import engine
from app.schemas.system import HealthResponse, ReadinessResponse

logger = get_logger(__name__)

router = APIRouter(tags=["system"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness: the process is up. Does not touch the database."""
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(response: Response) -> ReadinessResponse:
    """Readiness: the process is up AND its dependencies (database) are
    reachable. Used by orchestration to decide whether to route traffic.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return ReadinessResponse(status="ok", database="ok")
    except Exception:
        logger.exception("readiness check failed: database unreachable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unavailable", database="unreachable")

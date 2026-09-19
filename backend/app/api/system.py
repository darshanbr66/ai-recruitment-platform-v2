"""Unversioned/system endpoints: liveness and readiness.

Not audience-partitioned like /api/v1/{public,candidate,recruiter,admin} —
these are infrastructure probes, not product API surface.
"""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.mongo import ping_mongo
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
    """Readiness: the process is up AND its dependencies are reachable.
    Used by orchestration to decide whether to route traffic. MongoDB is
    only checked when resume storage actually depends on it — this must
    not ping every request, only readiness probes (which orchestrators
    poll on their own schedule, not per user request).
    """
    database_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("readiness check failed: database unreachable")
        database_ok = False

    mongodb_status: str | None = None
    if get_settings().resume_storage_provider == "mongodb_gridfs":
        mongodb_status = "ok" if await ping_mongo() else "unreachable"

    if not database_ok or mongodb_status == "unreachable":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="unavailable",
            database="ok" if database_ok else "unreachable",
            mongodb=mongodb_status,
        )

    return ReadinessResponse(status="ok", database="ok", mongodb=mongodb_status)

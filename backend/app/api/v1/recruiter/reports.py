"""Recruitment reports — computed from real, tenant-scoped data at request
time (CLAUDE.md § 2). Gated behind `application.read` since a report is
fundamentally a view over application data; no separate `report.read`
permission exists yet because nothing needs one.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import ReportOverview
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["recruiter-reports"])


@router.get("/overview", response_model=ReportOverview)
async def get_overview(
    current_user: User = Depends(require_permission("application.read")),
    db: AsyncSession = Depends(get_db),
) -> ReportOverview:
    assert current_user.organization_id is not None
    return await report_service.get_overview(db, current_user.organization_id)

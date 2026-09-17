"""Admin-only Activity/Audit log (CLAUDE.md § 3: candidate deletion and
other destructive/state-changing actions must never disappear from the
system untraceably). Gated on `activity.read`, granted only to ORG_ADMIN —
deliberately absent from RECRUITER so this never appears in the ordinary
recruiter navigation."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.activity import ActivityResponse
from app.services import activity_service

router = APIRouter(prefix="/activities", tags=["recruiter-activities"])


@router.get("", response_model=list[ActivityResponse])
async def list_activities(
    current_user: User = Depends(require_permission("activity.read")),
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None, max_length=255),
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ActivityResponse]:
    assert current_user.organization_id is not None
    activities = await activity_service.list_activities(
        db,
        current_user.organization_id,
        search=search,
        action=action,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return [ActivityResponse.model_validate(a) for a in activities]

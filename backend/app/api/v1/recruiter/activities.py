"""Admin-only Activity/Audit log (CLAUDE.md § 3: candidate deletion and
other destructive/state-changing actions must never disappear from the
system untraceably). Gated on `activity.read` / `activity.delete`, granted
only to ORG_ADMIN — deliberately absent from RECRUITER so this never
appears in the ordinary recruiter navigation."""

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError, UnprocessableError
from app.db.session import get_db
from app.models.user import User
from app.schemas.activity import (
    ActivityBulkDeleteRequest,
    ActivityCountResponse,
    ActivityDeleteAllRequest,
    ActivityDeleteResult,
    ActivityResponse,
)
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


@router.get("/count", response_model=ActivityCountResponse)
async def count_activities(
    current_user: User = Depends(require_permission("activity.read")),
    db: AsyncSession = Depends(get_db),
) -> ActivityCountResponse:
    """How many entries the caller's organization has in total — what
    "Delete all" would remove (the list endpoint is capped per page)."""
    assert current_user.organization_id is not None
    total = await activity_service.count_activities(db, current_user.organization_id)
    return ActivityCountResponse(total=total)


# The static `/bulk` and `/all` paths are declared before `/{activity_id}` so
# they are never parsed as an id.
@router.delete("/bulk", response_model=ActivityDeleteResult)
async def delete_selected_activities(
    payload: ActivityBulkDeleteRequest,
    current_user: User = Depends(require_permission("activity.delete")),
    db: AsyncSession = Depends(get_db),
) -> ActivityDeleteResult:
    """Deletes the selected entries of the caller's own organization. Ids
    from another tenant or already deleted are ignored, and `deleted` is the
    number of rows actually removed. An empty selection deletes nothing."""
    assert current_user.organization_id is not None
    deleted = await activity_service.delete_activities(
        db,
        organization_id=current_user.organization_id,
        activity_ids=payload.activity_ids,
        actor=current_user,
    )
    return ActivityDeleteResult(deleted=deleted)


@router.delete("/all", response_model=ActivityDeleteResult)
async def delete_all_activities(
    payload: ActivityDeleteAllRequest,
    current_user: User = Depends(require_permission("activity.delete")),
    db: AsyncSession = Depends(get_db),
) -> ActivityDeleteResult:
    """Deletes every entry of the caller's own organization (never another
    tenant's). Requires an explicit `{"confirm": true}`."""
    if not payload.confirm:
        raise UnprocessableError("Deleting all activities requires explicit confirmation.")
    assert current_user.organization_id is not None
    deleted = await activity_service.delete_all_activities(
        db, organization_id=current_user.organization_id, actor=current_user
    )
    return ActivityDeleteResult(deleted=deleted)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    activity_id: uuid.UUID,
    current_user: User = Depends(require_permission("activity.delete")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    assert current_user.organization_id is not None
    deleted = await activity_service.delete_activity(
        db,
        organization_id=current_user.organization_id,
        activity_id=activity_id,
        actor=current_user,
    )
    if not deleted:
        raise NotFoundError("Activity not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

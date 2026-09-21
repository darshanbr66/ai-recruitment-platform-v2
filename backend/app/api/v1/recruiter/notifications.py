"""The signed-in staff user's own in-app notifications. Deliberately not tied
to a role permission: every result is pinned to the caller's own user id (and
their organization, by RLS), so there is nothing broader to grant. A
platform-level SUPER_ADMIN has no organization and therefore no notifications."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationAcknowledgeRequest,
    NotificationAcknowledgeResult,
    NotificationResponse,
)
from app.services import in_app_notification_service

router = APIRouter(prefix="/notifications", tags=["recruiter-notifications"])


async def _current_organization_user(user: User = Depends(get_current_user)) -> User:
    if user.organization_id is None:
        raise ForbiddenError("Notifications are only available to organization accounts.")
    return user


@router.get("", response_model=list[NotificationResponse])
async def list_unread_notifications(
    current_user: User = Depends(_current_organization_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[NotificationResponse]:
    """The caller's unread notifications, newest first. The frontend polls
    this, shows each as a toast, then acknowledges them."""
    notifications = await in_app_notification_service.list_unread(
        db, user=current_user, limit=limit
    )
    return [NotificationResponse.model_validate(n) for n in notifications]


@router.post("/read", response_model=NotificationAcknowledgeResult)
async def acknowledge_notifications(
    payload: NotificationAcknowledgeRequest,
    current_user: User = Depends(_current_organization_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationAcknowledgeResult:
    updated = await in_app_notification_service.mark_read(
        db, user=current_user, notification_ids=payload.ids
    )
    return NotificationAcknowledgeResult(updated=updated)

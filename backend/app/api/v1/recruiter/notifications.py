"""The internal Notification Center: the signed-in staff user's own
notifications (read/list/mark-read — self-scoped, no permission needed
beyond being an organization member), plus admin/staff actions that create
notifications for others (`announce`, `send` — each behind its own
permission). Candidates never appear here; this router is mounted only
under `/api/v1/recruiter/*`.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_permission
from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    AnnouncementCreateRequest,
    AnnouncementResult,
    DirectMessageCreateRequest,
    NotificationAcknowledgeRequest,
    NotificationAcknowledgeResult,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services import in_app_notification_service
from app.services.calendar_reminder_service import process_due_reminders

router = APIRouter(prefix="/notifications", tags=["recruiter-notifications"])


async def _current_organization_user(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> User:
    if user.organization_id is None:
        raise ForbiddenError("Notifications are only available to organization accounts.")
    # Piggybacked here (not a background job) because a Render free-tier web
    # dyno can be idle-stopped: every poll of this user's notifications is
    # itself the opportunity to catch up on any calendar reminder that came
    # due while nothing was running. Cheap (one indexed query, usually zero
    # rows) and safe under concurrency — see calendar_reminder_service.py's
    # module docstring for the idempotency guarantee.
    await process_due_reminders(db, organization_id=user.organization_id)
    return user


def _to_response(notification: Notification) -> NotificationResponse:
    sender = notification.sender
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        created_at=notification.created_at,
        read_at=notification.read_at,
        sender_id=notification.sender_user_id,
        sender_name=sender.full_name if sender is not None else None,
        related_entity_type=notification.related_entity_type,
        related_entity_id=notification.related_entity_id,
    )


@router.get("", response_model=list[NotificationResponse])
async def list_unread_notifications(
    current_user: User = Depends(_current_organization_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[NotificationResponse]:
    """The caller's unread notifications, newest first. The frontend polls
    this for the toast stream — the Notification Center itself uses
    `/notifications/all`, which never auto-consumes anything."""
    notifications = await in_app_notification_service.list_unread(
        db, user=current_user, limit=limit
    )
    return [NotificationResponse.model_validate(n) for n in notifications]


@router.get("/all", response_model=list[NotificationResponse])
async def list_all_notifications(
    current_user: User = Depends(_current_organization_user),
    db: AsyncSession = Depends(get_db),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[NotificationResponse]:
    """The Notification Center's full, paginated history — read and unread,
    never auto-acknowledged just by being listed."""
    notifications = await in_app_notification_service.list_notifications(
        db, user=current_user, unread_only=unread_only, limit=limit, offset=offset
    )
    return [_to_response(n) for n in notifications]


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    current_user: User = Depends(_current_organization_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Backs the nav badge — polled alongside the toast stream."""
    unread = await in_app_notification_service.count_unread(db, user=current_user)
    return UnreadCountResponse(unread=unread)


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


@router.post("/read-all", response_model=NotificationAcknowledgeResult)
async def acknowledge_all_notifications(
    current_user: User = Depends(_current_organization_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationAcknowledgeResult:
    updated = await in_app_notification_service.mark_all_read(db, user=current_user)
    return NotificationAcknowledgeResult(updated=updated)


@router.post("/announce", response_model=AnnouncementResult, status_code=201)
async def send_announcement(
    payload: AnnouncementCreateRequest,
    current_user: User = Depends(require_permission("notification.announce")),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementResult:
    assert current_user.organization_id is not None
    notifications = await in_app_notification_service.create_announcement(
        db,
        organization_id=current_user.organization_id,
        sender=current_user,
        title=payload.title,
        message=payload.message,
        target=payload.target,
        department_id=payload.department_id,
        user_ids=payload.user_ids,
    )
    return AnnouncementResult(recipients_notified=len(notifications))


@router.post("/send", response_model=NotificationResponse, status_code=201)
async def send_direct_message(
    payload: DirectMessageCreateRequest,
    current_user: User = Depends(require_permission("notification.send")),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    assert current_user.organization_id is not None
    notification = await in_app_notification_service.create_direct_message(
        db,
        organization_id=current_user.organization_id,
        sender=current_user,
        recipient_user_id=payload.recipient_user_id,
        title=payload.title,
        message=payload.message,
    )
    # `notification.sender` is `lazy="raise"` and wasn't eager-loaded on this
    # freshly created row — the sender is simply the caller, so build the
    # response from `current_user` directly rather than touching that
    # relationship.
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        created_at=notification.created_at,
        read_at=notification.read_at,
        sender_id=current_user.id,
        sender_name=current_user.full_name,
        related_entity_type=notification.related_entity_type,
        related_entity_id=notification.related_entity_id,
    )

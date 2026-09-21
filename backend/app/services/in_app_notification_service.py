"""In-app notifications (app/models/notification.py) — stored server-side and
read back by the recipient's own session. Not to be confused with
`notification_service`, which sends email.

Every operation here runs under the caller's tenant context (RLS), and reads
are additionally pinned to the recipient's own user id, so a colleague in the
same organization never sees someone else's notifications.
"""

import uuid
from collections.abc import Collection
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.assessment import AssessmentInvitation
from app.models.notification import Notification, NotificationType
from app.models.user import User

logger = get_logger(__name__)

_ASSESSMENT_EVENTS: dict[NotificationType, tuple[str, str]] = {
    NotificationType.ASSESSMENT_STARTED: ("Assessment started", "started"),
    NotificationType.ASSESSMENT_SUBMITTED: ("Assessment submitted", "submitted"),
}


async def notify_inviter_of_assessment_event(
    db: AsyncSession,
    *,
    invitation: AssessmentInvitation,
    notification_type: NotificationType,
    candidate_name: str,
    assessment_title: str,
) -> bool:
    """Tells the user who sent `invitation` that the candidate started or
    submitted it. Returns True only if a new notification was created.

    - Only the inviter is notified — never other recruiters or admins. An
      invitation with no inviter (their account was removed), an inactive
      inviter, or one outside the invitation's organization (e.g. a
      platform-level SUPER_ADMIN) is skipped.
    - Once per invitation and type: the unique index makes a repeat insert a
      no-op (`ON CONFLICT DO NOTHING`), so concurrent or repeated requests
      can't produce a duplicate.
    - Never breaks the candidate's flow: the insert runs in a savepoint and a
      database failure is logged and swallowed — losing a courtesy
      notification must not lose a candidate's submitted answers.
    """
    inviter_id = invitation.invited_by_user_id
    if inviter_id is None:
        return False
    inviter = await db.get(User, inviter_id)
    if (
        inviter is None
        or not inviter.is_active
        or inviter.organization_id != invitation.organization_id
    ):
        return False

    title, verb = _ASSESSMENT_EVENTS[notification_type]
    statement = (
        pg_insert(Notification)
        .values(
            organization_id=invitation.organization_id,
            recipient_user_id=inviter.id,
            type=notification_type,
            title=title,
            message=f"{candidate_name} has {verb} the {assessment_title} assessment.",
            assessment_invitation_id=invitation.id,
        )
        .on_conflict_do_nothing(index_elements=["assessment_invitation_id", "type"])
        .returning(Notification.id)
    )
    try:
        async with db.begin_nested():
            created_id = (await db.execute(statement)).scalar_one_or_none()
    except SQLAlchemyError as exc:
        logger.warning(
            "In-app notification could not be stored",
            extra={"extra_fields": {"error_type": type(exc).__name__}},
        )
        return False
    return created_id is not None


async def list_unread(db: AsyncSession, *, user: User, limit: int) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.recipient_user_id == user.id, Notification.read_at.is_(None))
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_read(
    db: AsyncSession, *, user: User, notification_ids: Collection[uuid.UUID]
) -> int:
    """Acknowledges the given notifications, but only the caller's own that
    are still unread — so it is idempotent and can never touch someone
    else's row. Returns how many were newly marked."""
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id.in_(notification_ids),
            Notification.recipient_user_id == user.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    return cast(CursorResult[Any], result).rowcount

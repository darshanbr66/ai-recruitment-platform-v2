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
from typing import Any, Literal, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError, UnprocessableError
from app.core.logging import get_logger
from app.models.assessment import AssessmentInvitation
from app.models.notification import Notification, NotificationType
from app.models.team_hierarchy import Employee
from app.models.user import User

logger = get_logger(__name__)

AnnouncementTarget = Literal["EVERYONE", "DEPARTMENT", "EMPLOYEES"]

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


async def mark_all_read(db: AsyncSession, *, user: User) -> int:
    """Acknowledges every one of the caller's own still-unread notifications
    in one statement — the Notification Center's "Mark all as read"."""
    result = await db.execute(
        update(Notification)
        .where(Notification.recipient_user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    return cast(CursorResult[Any], result).rowcount


async def count_unread(db: AsyncSession, *, user: User) -> int:
    """Backs the Notification Center's nav badge — a cheap COUNT rather than
    fetching rows."""
    total = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_user_id == user.id, Notification.read_at.is_(None)
        )
    )
    return total or 0


async def list_notifications(
    db: AsyncSession, *, user: User, unread_only: bool = False, limit: int = 50, offset: int = 0
) -> list[Notification]:
    """The Notification Center's full history (unlike `list_unread`, which
    is capped and meant only for the toaster's poll) — newest first, always
    pinned to the caller's own user id."""
    query = (
        select(Notification)
        .where(Notification.recipient_user_id == user.id)
        .options(joinedload(Notification.sender))
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    query = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def _resolve_department_recipients(
    db: AsyncSession, *, organization_id: uuid.UUID, department_id: uuid.UUID
) -> list[uuid.UUID]:
    result = await db.execute(
        select(Employee.user_id).where(
            Employee.organization_id == organization_id,
            Employee.department_id == department_id,
            Employee.deleted_at.is_(None),
            Employee.user_id.is_not(None),
        )
    )
    return [row for row in result.scalars().all() if row is not None]


async def create_announcement(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    sender: User,
    title: str,
    message: str,
    target: AnnouncementTarget,
    department_id: uuid.UUID | None = None,
    user_ids: Collection[uuid.UUID] = (),
    related_entity_type: str | None = None,
    related_entity_id: uuid.UUID | None = None,
) -> list[Notification]:
    """Fans an announcement out to every resolved recipient as its own
    `Notification` row (each independently readable/dismissible — there is
    no "one row, many recipients" shortcut, since read state is per person).
    Recipients are always resolved from the caller's own organization,
    active only, and never include the sender themselves twice by accident
    (they may still address themselves explicitly via `user_ids`).
    """
    if target == "EVERYONE":
        result = await db.execute(
            select(User.id).where(
                User.organization_id == organization_id, User.is_active.is_(True)
            )
        )
        recipient_ids = list(result.scalars().all())
    elif target == "DEPARTMENT":
        if department_id is None:
            raise UnprocessableError("department_id is required when target is DEPARTMENT.")
        recipient_ids = await _resolve_department_recipients(
            db, organization_id=organization_id, department_id=department_id
        )
        if not recipient_ids:
            raise NotFoundError("No portal users are linked to that department.")
    elif target == "EMPLOYEES":
        if not user_ids:
            raise UnprocessableError("user_ids is required when target is EMPLOYEES.")
        result = await db.execute(
            select(User.id).where(
                User.id.in_(user_ids),
                User.organization_id == organization_id,
                User.is_active.is_(True),
            )
        )
        recipient_ids = list(result.scalars().all())
        if not recipient_ids:
            raise NotFoundError("None of the selected employees have an active portal account.")
    else:  # pragma: no cover - Literal exhausts at the type level
        raise UnprocessableError(f"Unknown announcement target: {target!r}")

    notifications = [
        Notification(
            organization_id=organization_id,
            recipient_user_id=recipient_id,
            sender_user_id=sender.id,
            type=NotificationType.ANNOUNCEMENT,
            title=title,
            message=message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        for recipient_id in dict.fromkeys(recipient_ids)  # de-duplicate, keep order
    ]
    db.add_all(notifications)
    await db.flush()
    return notifications


async def create_direct_message(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    sender: User,
    recipient_user_id: uuid.UUID,
    title: str,
    message: str,
) -> Notification:
    """One authorized portal user messaging another — internal portal
    communication, never email. The recipient must be an active user in the
    same organization; anything else (another tenant, a deactivated
    account, a nonexistent id) is indistinguishable from "not found",
    matching how every other cross-entity lookup in this codebase behaves
    under RLS.
    """
    if recipient_user_id == sender.id:
        raise UnprocessableError("You cannot send a message to yourself.")
    recipient = await db.scalar(
        select(User).where(
            User.id == recipient_user_id,
            User.organization_id == organization_id,
            User.is_active.is_(True),
        )
    )
    if recipient is None:
        raise NotFoundError("That employee could not be found.")

    notification = Notification(
        organization_id=organization_id,
        recipient_user_id=recipient.id,
        sender_user_id=sender.id,
        type=NotificationType.DIRECT_MESSAGE,
        title=title,
        message=message,
    )
    db.add(notification)
    await db.flush()
    return notification

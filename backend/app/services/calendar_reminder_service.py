"""Fires calendar-event reminders as in-app notifications — a DB-backed poll,
never a queue worker (no Redis/Celery is provisioned; see docs/
architecture.md § 12 and the free-tier deployment constraint this project
is built under).

Two callers, one idempotent function:

1. `app/core/calendar_reminders.py`'s background loop — runs every ~60s for
   as long as the process is alive, giving good latency while the web
   dyno is warm.
2. Piggybacked on every notification poll (app/api/v1/recruiter/
   notifications.py) — a cheap, org-scoped safety net so a reminder is
   still delivered (just later) even if the process was asleep the whole
   time a Render free-tier dyno can spend idle (it has no guaranteed
   always-on background process).

Idempotency is a single atomic UPDATE ... WHERE reminder_fired_at IS NULL,
not a check-then-set — the same guarantee ON CONFLICT DO NOTHING gives
app/services/in_app_notification_service.py's assessment notifications, just
expressed as an UPDATE instead of an INSERT (there is no unique index to
conflict on here — the guard column itself is the lock).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Interval

from app.core.logging import get_logger
from app.models.calendar_event import CalendarEvent, CalendarEventAttendee, CalendarEventStatus
from app.models.notification import Notification, NotificationType
from app.models.user import User

logger = get_logger(__name__)


def _due_reminders_query(*, organization_id: uuid.UUID | None, now: datetime) -> Select[Any]:
    """`start_at - reminder_minutes_before minutes <= now` — expressed
    without a computed column so the partial index
    (ix_calendar_events_due_reminders) can still be used."""
    due_at = CalendarEvent.start_at - cast(
        func.make_interval(0, 0, 0, 0, 0, CalendarEvent.reminder_minutes_before), Interval
    )
    conditions = [
        CalendarEvent.reminder_minutes_before.is_not(None),
        CalendarEvent.reminder_fired_at.is_(None),
        CalendarEvent.status == CalendarEventStatus.SCHEDULED,
        due_at <= now,
    ]
    if organization_id is not None:
        conditions.append(CalendarEvent.organization_id == organization_id)
    return select(CalendarEvent).where(*conditions)


async def process_due_reminders(
    db: AsyncSession, *, organization_id: uuid.UUID | None = None, now: datetime | None = None
) -> int:
    """Finds every due, unfired reminder (scoped to one organization when
    called from a request; every organization when called from the
    background loop, which runs under `rls_bypass` — see
    app/core/calendar_reminders.py) and, for each, atomically claims it and
    notifies the organizer + attendees. Returns how many reminders fired.

    Never mutates the event's `status` or any candidate/application data —
    purely a notification side effect.

    The organizer is deliberately excluded from the notified recipients by
    default (they scheduled the event; the reminder is aimed at the people
    who might otherwise forget it) — unless they explicitly added
    themselves as an attendee too, which is treated as an explicit opt-in.
    """
    now = now or datetime.now(UTC)
    query = _due_reminders_query(organization_id=organization_id, now=now)
    due_events = (await db.execute(query)).scalars().all()
    if not due_events:
        return 0

    fired = 0
    for event in due_events:
        # Claim it first, atomically — if this UPDATE affects zero rows,
        # another concurrent caller (another user's poll, or the background
        # loop) already claimed it, and we must not notify twice.
        claimed = await db.execute(
            update(CalendarEvent)
            .where(CalendarEvent.id == event.id, CalendarEvent.reminder_fired_at.is_(None))
            .values(reminder_fired_at=now)
            .returning(CalendarEvent.id)
        )
        if claimed.scalar_one_or_none() is None:
            continue

        attendee_query = select(CalendarEventAttendee.user_id).where(
            CalendarEventAttendee.event_id == event.id
        )
        attendee_ids = (await db.execute(attendee_query)).scalars().all()
        # Only attendees by default — the organizer is excluded unless they
        # explicitly added themselves as an attendee too (see the docstring).
        recipient_ids = set(attendee_ids)

        active_recipients = (
            await db.execute(
                select(User.id).where(User.id.in_(recipient_ids), User.is_active.is_(True))
            )
        ).scalars().all()

        when = event.start_at.strftime("%b %d at %H:%M UTC")
        db.add_all(
            Notification(
                organization_id=event.organization_id,
                recipient_user_id=recipient_id,
                type=NotificationType.CALENDAR_REMINDER,
                title=f"Reminder: {event.title}",
                message=f"\"{event.title}\" starts {when}.",
                related_entity_type="CALENDAR_EVENT",
                related_entity_id=event.id,
            )
            for recipient_id in active_recipients
        )
        fired += 1

    await db.flush()
    if fired:
        logger.info("Calendar reminders fired", extra={"extra_fields": {"count": fired}})
    return fired

"""Calendar events — CRUD plus the reminder-poll piggyback (see
calendar_reminder_service.py). Only the organizer may edit or delete an
event, mirroring note_service.py's author-only rule; anyone with
`calendar.read` may view any event in their organization (events are
inherently a shared/team concept, unlike notes, so there is no
private/shared distinction here).
"""

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ForbiddenError, NotFoundError, UnprocessableError
from app.models.application import Application
from app.models.calendar_event import (
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventStatus,
    CalendarEventType,
)
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.user import User

_WITH_ORGANIZER = (joinedload(CalendarEvent.organizer),)


async def _validate_links(
    db: AsyncSession,
    *,
    candidate_id: uuid.UUID | None,
    job_id: uuid.UUID | None,
    application_id: uuid.UUID | None,
) -> None:
    if candidate_id is not None and await db.get(Candidate, candidate_id) is None:
        raise NotFoundError("Candidate not found.")
    if job_id is not None and await db.get(Job, job_id) is None:
        raise NotFoundError("Job not found.")
    if application_id is not None and await db.get(Application, application_id) is None:
        raise NotFoundError("Application not found.")


async def _validate_attendees(
    db: AsyncSession, *, organization_id: uuid.UUID, attendee_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    if not attendee_ids:
        return []
    result = await db.execute(
        select(User.id).where(User.id.in_(attendee_ids), User.organization_id == organization_id)
    )
    valid_ids = list(result.scalars().all())
    if len(valid_ids) != len(set(attendee_ids)):
        raise NotFoundError("One or more attendees could not be found.")
    return valid_ids


async def create_event(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    organizer: User,
    title: str,
    start_at: datetime,
    end_at: datetime,
    timezone: str,
    description: str | None = None,
    event_type: CalendarEventType = CalendarEventType.GENERAL_REMINDER,
    all_day: bool = False,
    candidate_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    application_id: uuid.UUID | None = None,
    reminder_minutes_before: int | None = None,
    attendee_ids: list[uuid.UUID] | None = None,
) -> CalendarEvent:
    if end_at < start_at:
        raise UnprocessableError("An event cannot end before it starts.")
    await _validate_links(
        db, candidate_id=candidate_id, job_id=job_id, application_id=application_id
    )
    valid_attendee_ids = await _validate_attendees(
        db, organization_id=organization_id, attendee_ids=attendee_ids or []
    )

    event = CalendarEvent(
        organization_id=organization_id,
        organizer_user_id=organizer.id,
        title=title,
        description=description,
        event_type=event_type,
        start_at=start_at,
        end_at=end_at,
        all_day=all_day,
        timezone=timezone,
        candidate_id=candidate_id,
        job_id=job_id,
        application_id=application_id,
        reminder_minutes_before=reminder_minutes_before,
    )
    db.add(event)
    await db.flush()

    if valid_attendee_ids:
        db.add_all(
            CalendarEventAttendee(event_id=event.id, user_id=attendee_id)
            for attendee_id in valid_attendee_ids
        )
        await db.flush()

    return await get_event(db, event.id)  # type: ignore[return-value]


async def get_event(db: AsyncSession, event_id: uuid.UUID) -> CalendarEvent | None:
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id).options(*_WITH_ORGANIZER)
    )
    return result.unique().scalar_one_or_none()


async def list_attendee_ids(db: AsyncSession, event_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(CalendarEventAttendee.user_id).where(CalendarEventAttendee.event_id == event_id)
    )
    return list(result.scalars().all())


async def list_events(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    range_start: datetime,
    range_end: datetime,
    candidate_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
) -> list[CalendarEvent]:
    """Every event overlapping `[range_start, range_end)` — the calendar
    grid's query, regardless of whether the caller is asking for a month, a
    week, or a day (the range is computed by the API layer)."""
    conditions = [
        CalendarEvent.organization_id == organization_id,
        CalendarEvent.start_at < range_end,
        CalendarEvent.end_at >= range_start,
    ]
    if candidate_id is not None:
        conditions.append(CalendarEvent.candidate_id == candidate_id)
    if job_id is not None:
        conditions.append(CalendarEvent.job_id == job_id)

    result = await db.execute(
        select(CalendarEvent).where(*conditions).options(*_WITH_ORGANIZER).order_by(CalendarEvent.start_at.asc())
    )
    return list(result.unique().scalars().all())


def _require_organizer(event: CalendarEvent, user_id: uuid.UUID) -> None:
    if event.organizer_user_id != user_id:
        raise ForbiddenError("Only the organizer can edit or delete this event.")


async def update_event(
    db: AsyncSession,
    event: CalendarEvent,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    title: str | None = None,
    description: str | None | Literal["__unset__"] = "__unset__",
    event_type: CalendarEventType | None = None,
    status: CalendarEventStatus | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    all_day: bool | None = None,
    timezone: str | None = None,
    candidate_id: uuid.UUID | None | Literal["__unset__"] = "__unset__",
    job_id: uuid.UUID | None | Literal["__unset__"] = "__unset__",
    application_id: uuid.UUID | None | Literal["__unset__"] = "__unset__",
    reminder_minutes_before: int | None | Literal["__unset__"] = "__unset__",
    attendee_ids: list[uuid.UUID] | None = None,
) -> CalendarEvent:
    _require_organizer(event, user_id)

    new_start = start_at if start_at is not None else event.start_at
    new_end = end_at if end_at is not None else event.end_at
    if new_end < new_start:
        raise UnprocessableError("An event cannot end before it starts.")

    await _validate_links(
        db,
        candidate_id=candidate_id if candidate_id != "__unset__" else None,
        job_id=job_id if job_id != "__unset__" else None,
        application_id=application_id if application_id != "__unset__" else None,
    )

    if title is not None:
        event.title = title
    if description != "__unset__":
        event.description = description
    if event_type is not None:
        event.event_type = event_type
    if status is not None:
        event.status = status
    if start_at is not None:
        event.start_at = start_at
        # A moved start time invalidates any reminder already fired for the
        # old time — re-arm it so the recipient is reminded about the new one.
        event.reminder_fired_at = None
    if end_at is not None:
        event.end_at = end_at
    if all_day is not None:
        event.all_day = all_day
    if timezone is not None:
        event.timezone = timezone
    if candidate_id != "__unset__":
        event.candidate_id = candidate_id
    if job_id != "__unset__":
        event.job_id = job_id
    if application_id != "__unset__":
        event.application_id = application_id
    if reminder_minutes_before != "__unset__":
        event.reminder_minutes_before = reminder_minutes_before
        event.reminder_fired_at = None

    if attendee_ids is not None:
        valid_attendee_ids = await _validate_attendees(
            db, organization_id=organization_id, attendee_ids=attendee_ids
        )
        await db.execute(
            delete(CalendarEventAttendee).where(CalendarEventAttendee.event_id == event.id)
        )
        if valid_attendee_ids:
            db.add_all(
                CalendarEventAttendee(event_id=event.id, user_id=attendee_id)
                for attendee_id in valid_attendee_ids
            )

    await db.flush()
    reloaded = await get_event(db, event.id)
    assert reloaded is not None
    return reloaded


async def delete_event(db: AsyncSession, event: CalendarEvent, *, user_id: uuid.UUID) -> None:
    _require_organizer(event, user_id)
    await db.delete(event)
    await db.flush()

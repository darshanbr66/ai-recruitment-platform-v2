"""Internal recruitment calendar — interviews, meetings, deadlines,
follow-ups. Every read/write is scoped to the caller's organization;
`calendar.manage` (create/edit/delete) is separate from `calendar.read`
(view), mirroring every other permission-code pair in this codebase.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.calendar_event import CalendarEvent
from app.models.user import User
from app.schemas.calendar_event import (
    CalendarEventCreateRequest,
    CalendarEventResponse,
    CalendarEventUpdateRequest,
)
from app.services import calendar_service

router = APIRouter(prefix="/calendar", tags=["recruiter-calendar"])


async def _to_response(db: AsyncSession, event: CalendarEvent) -> CalendarEventResponse:
    attendee_ids = await calendar_service.list_attendee_ids(db, event.id)
    return CalendarEventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        status=event.status,
        start_at=event.start_at,
        end_at=event.end_at,
        all_day=event.all_day,
        timezone=event.timezone,
        organizer_id=event.organizer_user_id,
        organizer_name=event.organizer.full_name,
        candidate_id=event.candidate_id,
        job_id=event.job_id,
        application_id=event.application_id,
        reminder_minutes_before=event.reminder_minutes_before,
        reminder_fired_at=event.reminder_fired_at,
        attendee_ids=attendee_ids,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


@router.get("/events", response_model=list[CalendarEventResponse])
async def list_events(
    start: datetime = Query(..., description="Range start (inclusive), ISO 8601."),
    end: datetime = Query(..., description="Range end (exclusive), ISO 8601."),
    candidate_id: uuid.UUID | None = Query(default=None),
    job_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    current_user: User = Depends(require_permission("calendar.read")),
    db: AsyncSession = Depends(get_db),
) -> list[CalendarEventResponse]:
    assert current_user.organization_id is not None
    events = await calendar_service.list_events(
        db,
        current_user.organization_id,
        range_start=start,
        range_end=end,
        candidate_id=candidate_id,
        job_id=job_id,
        search=search,
    )
    return [await _to_response(db, event) for event in events]


@router.post("/events", response_model=CalendarEventResponse, status_code=201)
async def create_event(
    payload: CalendarEventCreateRequest,
    current_user: User = Depends(require_permission("calendar.manage")),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventResponse:
    assert current_user.organization_id is not None
    event = await calendar_service.create_event(
        db,
        organization_id=current_user.organization_id,
        organizer=current_user,
        title=payload.title,
        description=payload.description,
        event_type=payload.event_type,
        start_at=payload.start_at,
        end_at=payload.end_at,
        all_day=payload.all_day,
        timezone=payload.timezone,
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        application_id=payload.application_id,
        reminder_minutes_before=payload.reminder_minutes_before,
        attendee_ids=payload.attendee_ids,
    )
    return await _to_response(db, event)


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_event(
    event_id: uuid.UUID,
    _: User = Depends(require_permission("calendar.read")),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventResponse:
    event = await calendar_service.get_event(db, event_id)
    if event is None:
        raise NotFoundError("Event not found.")
    return await _to_response(db, event)


@router.patch("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: uuid.UUID,
    payload: CalendarEventUpdateRequest,
    current_user: User = Depends(require_permission("calendar.manage")),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventResponse:
    assert current_user.organization_id is not None
    event = await calendar_service.get_event(db, event_id)
    if event is None:
        raise NotFoundError("Event not found.")

    fields = payload.model_fields_set
    updated = await calendar_service.update_event(
        db,
        event,
        actor=current_user,
        organization_id=current_user.organization_id,
        title=payload.title,
        description=payload.description if "description" in fields else "__unset__",
        event_type=payload.event_type,
        status=payload.status,
        start_at=payload.start_at,
        end_at=payload.end_at,
        all_day=payload.all_day,
        timezone=payload.timezone,
        candidate_id=payload.candidate_id if "candidate_id" in fields else "__unset__",
        job_id=payload.job_id if "job_id" in fields else "__unset__",
        application_id=payload.application_id if "application_id" in fields else "__unset__",
        reminder_minutes_before=(
            payload.reminder_minutes_before if "reminder_minutes_before" in fields else "__unset__"
        ),
        attendee_ids=payload.attendee_ids,
    )
    return await _to_response(db, updated)


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    current_user: User = Depends(require_permission("calendar.manage")),
    db: AsyncSession = Depends(get_db),
) -> None:
    event = await calendar_service.get_event(db, event_id)
    if event is None:
        raise NotFoundError("Event not found.")
    await calendar_service.delete_event(db, event, actor=current_user)

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.calendar_event import CalendarEventStatus, CalendarEventType

MAX_ATTENDEES = 50


class CalendarAttendeeOption(BaseModel):
    """One selectable attendee for the event form — the caller's own
    organization only. Deliberately narrower than UserResponse (no roles, no
    organization_id): picking a meeting attendee is not user administration,
    so it sits behind `calendar.read` rather than `user.read`.
    """

    id: uuid.UUID
    full_name: str
    email: str


class CalendarEventCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    event_type: CalendarEventType = CalendarEventType.GENERAL_REMINDER
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    # IANA zone name (e.g. "Asia/Kolkata") the client's browser resolved —
    # display-only; start_at/end_at already carry an unambiguous UTC instant.
    timezone: str = Field(min_length=1, max_length=64)
    candidate_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    # Minutes before start_at to send a reminder notification; None = no reminder.
    reminder_minutes_before: int | None = Field(default=None, ge=0, le=10080)
    attendee_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_ATTENDEES)


class CalendarEventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    event_type: CalendarEventType | None = None
    status: CalendarEventStatus | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    candidate_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    reminder_minutes_before: int | None = Field(default=None, ge=0, le=10080)
    attendee_ids: list[uuid.UUID] | None = Field(default=None, max_length=MAX_ATTENDEES)


class CalendarEventResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    event_type: CalendarEventType
    status: CalendarEventStatus
    start_at: datetime
    end_at: datetime
    all_day: bool
    timezone: str
    organizer_id: uuid.UUID
    organizer_name: str
    candidate_id: uuid.UUID | None
    job_id: uuid.UUID | None
    application_id: uuid.UUID | None
    reminder_minutes_before: int | None
    reminder_fired_at: datetime | None
    attendee_ids: list[uuid.UUID]
    created_at: datetime
    updated_at: datetime

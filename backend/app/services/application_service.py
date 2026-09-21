import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import ColumnElement, SQLColumnExpression, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.application import Application, ApplicationSource, ApplicationStatus
from app.models.candidate import Candidate, CandidateType
from app.models.job import Job
from app.models.user import User
from app.schemas.application import ApplicationSortField, SortDirection
from app.services import activity_service
from app.workflows import application_workflow

_WITH_CANDIDATE_AND_JOB = (
    joinedload(Application.candidate),
    joinedload(Application.job),
    joinedload(Application.resume),
)


async def create_application(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    candidate_id: uuid.UUID,
    job_id: uuid.UUID,
    source: ApplicationSource,
    actor_user_id: uuid.UUID | None,
    campus_drive_id: uuid.UUID | None = None,
) -> Application:
    # RLS already scopes db.get() to the caller's own tenant (see
    # docs/security.md § 2) — a cross-tenant id is indistinguishable from a
    # nonexistent one, which is exactly the 404 this raises.
    if await db.get(Candidate, candidate_id) is None:
        raise NotFoundError("Candidate not found.")
    if await db.get(Job, job_id) is None:
        raise NotFoundError("Job not found.")

    application = Application(
        organization_id=organization_id,
        candidate_id=candidate_id,
        job_id=job_id,
        status=ApplicationStatus.APPLIED,
        source=source,
        campus_drive_id=campus_drive_id,
    )
    db.add(application)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("This candidate has already applied to this job.") from exc

    await application_workflow.record_initial_status(db, application, actor_user_id=actor_user_id)

    reloaded = await get_application(db, application.id)
    assert reloaded is not None

    actor = await db.get(User, actor_user_id) if actor_user_id is not None else None
    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="APPLICATION_CREATED",
        entity_type="application",
        entity_id=application.id,
        entity_label=f"{reloaded.candidate.full_name} — {reloaded.job.title}",
        description=f"Application from {reloaded.candidate.full_name} for \"{reloaded.job.title}\" was created.",
    )
    return reloaded


# A search box is typed by a person: cap how many words are honored so a
# pasted paragraph can't build an enormous query.
_MAX_SEARCH_TERMS = 5


@dataclass(frozen=True)
class ApplicationFilters:
    """Everything the Applications list can be narrowed by. Every field is
    optional and they combine with AND. Text fields match as a
    case-insensitive "contains"; `search` additionally matches each of its
    words against the candidate's name/email/phone and the job title.

    Invalid combinations (an inverted range, a negative bound) are rejected
    here, once, so every caller gets the same 422.
    """

    job_id: uuid.UUID | None = None
    candidate_id: uuid.UUID | None = None
    status: ApplicationStatus | None = None
    campus_drive_id: uuid.UUID | None = None
    source: ApplicationSource | None = None
    search: str | None = None
    candidate_type: CandidateType | None = None
    current_title: str | None = None
    current_company: str | None = None
    location: str | None = None
    preferred_location: str | None = None
    qualification: str | None = None
    min_experience: int | None = None
    max_experience: int | None = None
    max_notice_period_days: int | None = None
    immediate_joiner: bool | None = None
    applied_from: date | None = None
    applied_to: date | None = None

    def __post_init__(self) -> None:
        if (
            self.min_experience is not None
            and self.max_experience is not None
            and self.min_experience > self.max_experience
        ):
            raise UnprocessableError(
                "Minimum experience cannot be greater than maximum experience."
            )
        if (
            self.applied_from is not None
            and self.applied_to is not None
            and self.applied_from > self.applied_to
        ):
            raise UnprocessableError(
                "The 'applied from' date cannot be after the 'applied to' date."
            )
        for value in (self.min_experience, self.max_experience, self.max_notice_period_days):
            if value is not None and value < 0:
                raise UnprocessableError("Experience and notice period cannot be negative.")


def _escape_like(term: str) -> str:
    """`%`, `_` and the escape character are literal characters in what a
    person types, not wildcards."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _contains(column: SQLColumnExpression[Any], term: str) -> ColumnElement[bool]:
    return column.ilike(f"%{_escape_like(term)}%", escape="\\")


def _search_word_clause(word: str) -> ColumnElement[bool]:
    clauses = [
        _contains(Candidate.full_name, word),
        _contains(Candidate.email, word),
        _contains(Candidate.phone, word),
        _contains(Job.title, word),
    ]
    # Phone numbers are stored as typed ("+91 98765-43210") but searched by
    # digits: compare digits against the phone's digits, so spacing and
    # punctuation on either side don't matter.
    digits = re.sub(r"\D", "", word)
    if len(digits) >= 3:
        clauses.append(func.regexp_replace(Candidate.phone, "[^0-9]", "", "g").like(f"%{digits}%"))
    return or_(*clauses)


def _clean(value: str | None) -> str | None:
    value = value.strip() if value else None
    return value or None


def _filter_conditions(
    organization_id: uuid.UUID, filters: ApplicationFilters
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [
        Application.organization_id == organization_id,
        Application.deleted_at.is_(None),
    ]
    if filters.job_id is not None:
        conditions.append(Application.job_id == filters.job_id)
    if filters.candidate_id is not None:
        conditions.append(Application.candidate_id == filters.candidate_id)
    if filters.status is not None:
        conditions.append(Application.status == filters.status)
    if filters.campus_drive_id is not None:
        conditions.append(Application.campus_drive_id == filters.campus_drive_id)
    if filters.source is not None:
        conditions.append(Application.source == filters.source)
    if filters.candidate_type is not None:
        conditions.append(Candidate.candidate_type == filters.candidate_type)
    if filters.min_experience is not None:
        conditions.append(Candidate.years_experience >= filters.min_experience)
    if filters.max_experience is not None:
        conditions.append(Candidate.years_experience <= filters.max_experience)
    if filters.max_notice_period_days is not None:
        conditions.append(Candidate.notice_period_days <= filters.max_notice_period_days)
    if filters.immediate_joiner is not None:
        conditions.append(Candidate.immediate_joiner.is_(filters.immediate_joiner))
    # Whole calendar days, in UTC, both ends inclusive.
    if filters.applied_from is not None:
        conditions.append(
            Application.applied_at >= datetime.combine(filters.applied_from, time.min, tzinfo=UTC)
        )
    if filters.applied_to is not None:
        conditions.append(
            Application.applied_at
            < datetime.combine(filters.applied_to + timedelta(days=1), time.min, tzinfo=UTC)
        )
    for column, value in (
        (Candidate.current_title, filters.current_title),
        (Candidate.current_company, filters.current_company),
        (Candidate.location, filters.location),
        (Candidate.preferred_location, filters.preferred_location),
        (Candidate.qualification, filters.qualification),
    ):
        cleaned = _clean(value)
        if cleaned is not None:
            conditions.append(_contains(column, cleaned))
    # Every word must match somewhere ("jane example.com" finds Jane at
    # example.com), each word against name, email, phone or job title.
    words = (_clean(filters.search) or "").split()[:_MAX_SEARCH_TERMS]
    conditions.extend(_search_word_clause(word) for word in words)
    return conditions


_SORT_COLUMNS: dict[ApplicationSortField, SQLColumnExpression[Any]] = {
    ApplicationSortField.CREATED_AT: Application.created_at,
    ApplicationSortField.APPLIED_AT: Application.applied_at,
    ApplicationSortField.CANDIDATE_NAME: func.lower(Candidate.full_name),
    ApplicationSortField.JOB_TITLE: func.lower(Job.title),
    ApplicationSortField.STATUS: Application.status,
}


async def list_applications(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    filters: ApplicationFilters | None = None,
    sort_by: ApplicationSortField = ApplicationSortField.CREATED_AT,
    sort_direction: SortDirection = SortDirection.DESC,
    limit: int | None = None,
    offset: int = 0,
) -> list[Application]:
    """One joined query: filtering, ordering and paging all happen in the
    database (paging is applied *after* the filters), and the candidate and
    job come back in the same statement — no per-row lookups. With `limit`
    unset every match is returned, which is what internal callers such as
    reports rely on."""
    sort_column = _SORT_COLUMNS[sort_by]
    ordering = sort_column.desc() if sort_direction == SortDirection.DESC else sort_column.asc()
    query = (
        select(Application)
        .join(Application.candidate)
        .join(Application.job)
        .where(*_filter_conditions(organization_id, filters or ApplicationFilters()))
        .options(
            contains_eager(Application.candidate),
            contains_eager(Application.job),
            joinedload(Application.resume),
        )
        # `id` makes the order total, so pages never repeat or skip rows
        # when many applications share a timestamp or status.
        .order_by(ordering, Application.id.asc())
    )
    if limit is not None:
        query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def count_applications(
    db: AsyncSession, organization_id: uuid.UUID, filters: ApplicationFilters | None = None
) -> int:
    """How many applications match `filters`, ignoring paging — the number
    the list header shows and the pager is built from."""
    query = (
        select(func.count(Application.id))
        .select_from(Application)
        .join(Application.candidate)
        .join(Application.job)
        .where(*_filter_conditions(organization_id, filters or ApplicationFilters()))
    )
    return int(await db.scalar(query) or 0)


async def get_application(db: AsyncSession, application_id: uuid.UUID) -> Application | None:
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(*_WITH_CANDIDATE_AND_JOB)
    )
    return result.unique().scalar_one_or_none()


async def change_status(
    db: AsyncSession,
    application: Application,
    *,
    to_status: ApplicationStatus,
    actor_user_id: uuid.UUID | None,
    reason: str | None = None,
) -> Application:
    return await application_workflow.transition(
        db, application, to_status=to_status, actor_user_id=actor_user_id, reason=reason
    )


async def delete_application(
    db: AsyncSession, application: Application, *, actor: User, reason: str
) -> Application:
    """Soft-deletes/archives: keeps the row (and every AssessmentInvitation/
    Note/ApplicationStatusHistory/ScreeningRun pointing at it) but removes
    it from `list_applications` and records an Activity (CLAUDE.md § 3)."""
    if application.deleted_at is not None:
        raise ConflictError("This application has already been deleted.")

    application.deleted_at = datetime.now(UTC)
    application.deleted_by_user_id = actor.id
    application.deletion_reason = reason
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=application.organization_id,
        actor=actor,
        action="APPLICATION_DELETED",
        entity_type="application",
        entity_id=application.id,
        entity_label=f"{application.candidate.full_name} — {application.job.title}",
        description=f"Application from {application.candidate.full_name} for \"{application.job.title}\" was deleted.",
        reason=reason,
    )
    return application

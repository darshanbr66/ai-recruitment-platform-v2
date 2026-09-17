import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ConflictError, NotFoundError
from app.models.application import Application, ApplicationSource, ApplicationStatus
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.user import User
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


async def list_applications(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    job_id: uuid.UUID | None = None,
    candidate_id: uuid.UUID | None = None,
    status: ApplicationStatus | None = None,
    campus_drive_id: uuid.UUID | None = None,
) -> list[Application]:
    query = (
        select(Application)
        .where(Application.organization_id == organization_id, Application.deleted_at.is_(None))
        .options(*_WITH_CANDIDATE_AND_JOB)
        .order_by(Application.created_at.desc())
    )
    if job_id is not None:
        query = query.where(Application.job_id == job_id)
    if candidate_id is not None:
        query = query.where(Application.candidate_id == candidate_id)
    if status is not None:
        query = query.where(Application.status == status)
    if campus_drive_id is not None:
        query = query.where(Application.campus_drive_id == campus_drive_id)

    result = await db.execute(query)
    return list(result.unique().scalars().all())


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

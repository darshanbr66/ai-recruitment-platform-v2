import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.job import Job, JobStatus
from app.models.user import User
from app.schemas.job import JobCreateRequest, JobUpdateRequest
from app.services import activity_service


async def create_job(
    db: AsyncSession,
    *,
    actor: User,
    payload: JobCreateRequest,
) -> Job:
    assert actor.organization_id is not None
    job = Job(
        organization_id=actor.organization_id,
        created_by=actor.id,
        title=payload.title,
        department=payload.department,
        location=payload.location,
        employment_type=payload.employment_type,
        description=payload.description,
        description_visible=payload.description_visible,
        openings_count=payload.openings_count,
    )
    db.add(job)
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=job.organization_id,
        actor=actor,
        action="JOB_CREATED",
        entity_type="job",
        entity_id=job.id,
        entity_label=job.title,
        description=f"Job \"{job.title}\" was created.",
    )
    return job


async def list_jobs(
    db: AsyncSession, organization_id: uuid.UUID, *, status: JobStatus | None = None
) -> list[Job]:
    query = (
        select(Job)
        .where(Job.organization_id == organization_id, Job.deleted_at.is_(None))
        .order_by(Job.created_at.desc())
    )
    if status is not None:
        query = query.where(Job.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    """RLS scopes this to the caller's own tenant — a cross-tenant id
    returns None exactly as if the row didn't exist (docs/security.md § 2)."""
    return await db.get(Job, job_id)


def _job_change_action(job: Job, updates: dict[str, Any]) -> tuple[str, str]:
    """Picks the most specific activity action/description for a job
    update — a plain field edit is JOB_UPDATED, but a status change gets
    its own more legible action name (QA § 5)."""
    new_status = updates.get("status")
    if new_status is not None and new_status != job.status:
        if new_status == JobStatus.CLOSED:
            return "JOB_CLOSED", f"Job \"{job.title}\" was closed."
        if new_status == JobStatus.OPEN and job.status in (JobStatus.CLOSED, JobStatus.ON_HOLD):
            return "JOB_REOPENED", f"Job \"{job.title}\" was reopened."
        return (
            "JOB_STATUS_CHANGED",
            f"Job \"{job.title}\" status changed from {job.status.value} to {new_status.value}.",
        )

    changed_fields = [field for field in updates if field != "status"]
    if changed_fields:
        details = ", ".join(sorted(changed_fields))
        return "JOB_UPDATED", f"Job \"{job.title}\" was updated ({details})."
    return "JOB_UPDATED", f"Job \"{job.title}\" was updated."


async def update_job(
    db: AsyncSession, job: Job, payload: JobUpdateRequest, *, actor: User
) -> Job:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return job

    action, description = _job_change_action(job, updates)
    for field, value in updates.items():
        setattr(job, field, value)
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=job.organization_id,
        actor=actor,
        action=action,
        entity_type="job",
        entity_id=job.id,
        entity_label=job.title,
        description=description,
    )
    return job


async def delete_job(db: AsyncSession, job: Job, *, actor: User, reason: str) -> Job:
    """Soft-deletes/archives: keeps the row (and every Application/
    CampusDrive pointing at it) but removes it from `list_jobs` and records
    an Activity (CLAUDE.md § 3: never silently destroy recruitment history)."""
    if job.deleted_at is not None:
        raise ConflictError("This job has already been deleted.")

    job.deleted_at = datetime.now(UTC)
    job.deleted_by_user_id = actor.id
    job.deletion_reason = reason
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=job.organization_id,
        actor=actor,
        action="JOB_DELETED",
        entity_type="job",
        entity_id=job.id,
        entity_label=job.title,
        description=f"Job \"{job.title}\" was deleted.",
        reason=reason,
    )
    return job

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.schemas.job import JobCreateRequest, JobUpdateRequest


async def create_job(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    created_by: uuid.UUID,
    payload: JobCreateRequest,
) -> Job:
    job = Job(
        organization_id=organization_id,
        created_by=created_by,
        title=payload.title,
        department=payload.department,
        location=payload.location,
        employment_type=payload.employment_type,
        description=payload.description,
        openings_count=payload.openings_count,
    )
    db.add(job)
    await db.flush()
    return job


async def list_jobs(
    db: AsyncSession, organization_id: uuid.UUID, *, status: JobStatus | None = None
) -> list[Job]:
    query = (
        select(Job).where(Job.organization_id == organization_id).order_by(Job.created_at.desc())
    )
    if status is not None:
        query = query.where(Job.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    """RLS scopes this to the caller's own tenant — a cross-tenant id
    returns None exactly as if the row didn't exist (docs/security.md § 2)."""
    return await db.get(Job, job_id)


async def update_job(db: AsyncSession, job: Job, payload: JobUpdateRequest) -> Job:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    await db.flush()
    return job

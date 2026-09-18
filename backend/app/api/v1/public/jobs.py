"""Anonymous career-site endpoints: browse a tenant's open jobs by
organization slug. No authentication, no permission checks — tenant scoping
comes from resolving the slug (app/services/organization_service.py::
get_organization_by_slug) and setting RLS tenant context explicitly before
any Job query, and only OPEN jobs are ever visible here regardless of
caller.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.rls import set_tenant_context
from app.db.session import get_db
from app.models.job import Job, JobStatus
from app.schemas.public import PublicJobDetail, PublicJobSummary, PublicOrganizationSummary
from app.services import job_service, organization_service

router = APIRouter(prefix="/organizations/{slug}/jobs", tags=["public-jobs"])


async def _resolve_organization(db: AsyncSession, slug: str):
    organization = await organization_service.get_organization_by_slug(db, slug)
    if organization is None:
        raise NotFoundError("Organization not found.")
    await set_tenant_context(db, organization.id)
    return organization


@router.get("", response_model=list[PublicJobSummary])
async def list_open_jobs(slug: str, db: AsyncSession = Depends(get_db)) -> list[PublicJobSummary]:
    organization = await _resolve_organization(db, slug)
    jobs = await job_service.list_jobs(db, organization.id, status=JobStatus.OPEN)
    return [PublicJobSummary.model_validate(job) for job in jobs]


@router.get("/{job_id}", response_model=PublicJobDetail)
async def get_open_job(
    slug: str, job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> PublicJobDetail:
    organization = await _resolve_organization(db, slug)
    job: Job | None = await job_service.get_job(db, job_id)
    if job is None or job.status != JobStatus.OPEN:
        raise NotFoundError("Job not found.")
    return PublicJobDetail(
        id=job.id,
        title=job.title,
        department=job.department,
        location=job.location,
        employment_type=job.employment_type,
        openings_count=job.openings_count,
        created_at=job.created_at,
        description=job.description if job.description_visible else None,
        organization=PublicOrganizationSummary.model_validate(organization),
    )

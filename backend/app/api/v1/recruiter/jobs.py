"""Recruiter-facing Job CRUD. `organization_id` is always taken from the
authenticated caller, never from the request (docs/security.md § 2)."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.job import JobStatus
from app.models.user import User
from app.schemas.job import JobCreateRequest, JobResponse, JobUpdateRequest
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["recruiter-jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreateRequest,
    current_user: User = Depends(require_permission("job.create")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    assert current_user.organization_id is not None
    job = await job_service.create_job(
        db,
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        payload=payload,
    )
    return JobResponse.model_validate(job)


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    job_status: JobStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(require_permission("job.read")),
    db: AsyncSession = Depends(get_db),
) -> list[JobResponse]:
    assert current_user.organization_id is not None
    jobs = await job_service.list_jobs(db, current_user.organization_id, status=job_status)
    return [JobResponse.model_validate(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    _: User = Depends(require_permission("job.read")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job not found.")
    return JobResponse.model_validate(job)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: uuid.UUID,
    payload: JobUpdateRequest,
    _: User = Depends(require_permission("job.update")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job not found.")
    updated = await job_service.update_job(db, job, payload)
    return JobResponse.model_validate(updated)

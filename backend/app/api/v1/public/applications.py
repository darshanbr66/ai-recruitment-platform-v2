"""Anonymous job application submission — the candidate-facing entry point
into the recruiting pipeline (CLAUDE.md § 1: "public career site... entry
point into candidate apply flow"). Resume upload is required; the file is
actually validated and persisted (app/services/resume_service.py), never
faked.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.rls import set_tenant_context
from app.db.session import get_db
from app.integrations.storage import LocalResumeStorage, ResumeStorage
from app.schemas.public import PublicApplicationResult
from app.services import organization_service, public_application_service

router = APIRouter(prefix="/organizations/{slug}/jobs", tags=["public-applications"])


def _get_resume_storage() -> ResumeStorage:
    return LocalResumeStorage()


@router.post("/{job_id}/apply", response_model=PublicApplicationResult, status_code=201)
async def apply_to_job(
    slug: str,
    job_id: uuid.UUID,
    full_name: str = Form(..., min_length=1, max_length=255),
    email: str = Form(...),
    phone: str | None = Form(default=None, max_length=32),
    resume: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    storage: ResumeStorage = Depends(_get_resume_storage),
) -> PublicApplicationResult:
    organization = await organization_service.get_organization_by_slug(db, slug)
    if organization is None:
        raise NotFoundError("Organization not found.")
    await set_tenant_context(db, organization.id)

    resume_bytes = await resume.read()
    application = await public_application_service.apply_to_job(
        db,
        storage,
        organization_id=organization.id,
        job_id=job_id,
        full_name=full_name,
        email=email,
        phone=phone,
        resume_filename=resume.filename or "resume",
        resume_content_type=resume.content_type or "application/octet-stream",
        resume_bytes=resume_bytes,
    )

    return PublicApplicationResult(
        id=application.id,
        job_title=application.job.title,
        candidate_email=application.candidate.email,
        status=application.status.value,
        submitted_at=application.applied_at,
    )

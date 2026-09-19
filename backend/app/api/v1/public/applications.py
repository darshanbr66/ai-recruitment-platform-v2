"""Anonymous job application submission — the candidate-facing entry point
into the recruiting pipeline (CLAUDE.md § 1: "public career site... entry
point into candidate apply flow"). Resume upload is required; the file is
actually validated and persisted (app/services/resume_service.py), never
faked.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.rls import set_tenant_context
from app.db.session import get_db
from app.integrations.storage import ResumeStorage, get_resume_storage
from app.models.candidate import CandidateType
from app.schemas.candidate import PublicApplicantProfile
from app.schemas.public import PublicApplicationResult
from app.services import organization_service, public_application_service

# The schema's `location` is the form's `current_location`.
_FIELD_ALIASES = {"location": "current_location"}

def _as_request_errors(exc: ValidationError) -> list[Any]:
    """Re-shapes a schema ValidationError as body-field errors, renaming the
    schema's `location` back to the form's `current_location`."""
    return [
        {**error, "loc": ("body", *(_FIELD_ALIASES.get(str(part), part) for part in error["loc"]))}
        for error in exc.errors(include_url=False, include_context=False, include_input=False)
    ]


router = APIRouter(prefix="/organizations/{slug}/jobs", tags=["public-applications"])


@router.post("/{job_id}/apply", response_model=PublicApplicationResult, status_code=201)
async def apply_to_job(
    slug: str,
    job_id: uuid.UUID,
    full_name: str = Form(..., min_length=1, max_length=255),
    email: str = Form(...),
    phone: str | None = Form(default=None, max_length=32),
    candidate_type: CandidateType | None = Form(default=None),
    years_experience: int | None = Form(default=None, ge=0, le=80),
    notice_period_days: int | None = Form(default=None, ge=0, le=365),
    immediate_joiner: bool | None = Form(default=None),
    current_title: str | None = Form(default=None, max_length=255),
    current_company: str | None = Form(default=None, max_length=255),
    current_location: str | None = Form(default=None, max_length=255),
    preferred_location: str | None = Form(default=None, max_length=255),
    qualification: str | None = Form(default=None, max_length=255),
    linkedin_url: str | None = Form(default=None, max_length=500),
    github_url: str | None = Form(default=None, max_length=500),
    resume: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    storage: ResumeStorage = Depends(get_resume_storage),
) -> PublicApplicationResult:
    organization = await organization_service.get_organization_by_slug(db, slug)
    if organization is None:
        raise NotFoundError("Organization not found.")
    await set_tenant_context(db, organization.id)

    # Cross-field rules (EXPERIENCED needs experience + notice period, URL
    # host checks) live on the schema; surface failures through the same
    # 422 envelope FastAPI's own form validation uses.
    try:
        profile = PublicApplicantProfile(
            candidate_type=candidate_type,
            years_experience=years_experience,
            notice_period_days=notice_period_days,
            immediate_joiner=immediate_joiner,
            current_title=current_title,
            current_company=current_company,
            location=current_location,
            preferred_location=preferred_location,
            qualification=qualification,
            linkedin_url=linkedin_url,
            github_url=github_url,
        )
    except ValidationError as exc:
        raise RequestValidationError(_as_request_errors(exc)) from exc

    resume_bytes = await resume.read()
    application = await public_application_service.apply_to_job(
        db,
        storage,
        organization_id=organization.id,
        job_id=job_id,
        full_name=full_name,
        email=email,
        phone=phone,
        profile=profile,
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

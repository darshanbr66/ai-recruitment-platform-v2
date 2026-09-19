"""Orchestrates the candidate-facing apply flow: resolve tenant -> upsert
Candidate -> create Application -> store the resume. This is the one place
that composes candidate_service + application_service + resume_service for
an anonymous caller (see app/api/v1/public/applications.py) — kept separate
from application_service itself, which stays a plain CRUD module used by
both the public and recruiter routers.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.integrations.storage import ResumeStorage
from app.models.application import Application, ApplicationSource
from app.models.campus_drive import CampusDrive, CampusDriveStatus
from app.models.candidate import Candidate, CandidateSource
from app.models.job import Job, JobStatus
from app.schemas.candidate import CandidateProfileFields, PublicApplicantProfile
from app.services import (
    application_service,
    candidate_service,
    resume_service,
)


async def apply_to_job(
    db: AsyncSession,
    storage: ResumeStorage,
    *,
    organization_id: uuid.UUID,
    job_id: uuid.UUID,
    full_name: str,
    email: str,
    phone: str | None,
    profile: PublicApplicantProfile | None = None,
    resume_filename: str,
    resume_content_type: str,
    resume_bytes: bytes,
) -> Application:
    job = await db.get(Job, job_id)
    if job is None or job.status != JobStatus.OPEN:
        raise NotFoundError("This job is not accepting applications.")

    profile_values = (
        profile.model_dump(include=set(CandidateProfileFields.model_fields)) if profile else {}
    )

    candidate = await candidate_service.get_candidate_by_email(
        db, organization_id=organization_id, email=email
    )
    if candidate is None:
        candidate = Candidate(
            organization_id=organization_id,
            email=email,
            full_name=full_name,
            phone=phone,
            source=CandidateSource.PORTAL,
            **profile_values,
        )
        db.add(candidate)
        await db.flush()
    else:
        # An existing candidate (same email in this organization) is only
        # ever *filled in*, never overwritten: this endpoint is anonymous,
        # so anyone who knows an email must not be able to rewrite what a
        # recruiter or the real candidate already recorded.
        for field, value in profile_values.items():
            if value is not None and getattr(candidate, field) is None:
                setattr(candidate, field, value)
        await db.flush()

    # A job with an ACTIVE campus drive gets the application associated
    # automatically (docs/campus-hiring.md § 2: "Public portal association").
    active_drive = await db.scalar(
        select(CampusDrive).where(
            CampusDrive.job_id == job_id, CampusDrive.status == CampusDriveStatus.ACTIVE
        )
    )

    try:
        application = await application_service.create_application(
            db,
            organization_id=organization_id,
            candidate_id=candidate.id,
            job_id=job_id,
            source=ApplicationSource.PORTAL,
            actor_user_id=None,
            campus_drive_id=active_drive.id if active_drive else None,
        )
    except AppError:
        raise

    await resume_service.save_resume(
        db,
        storage,
        organization_id=organization_id,
        candidate_id=candidate.id,
        application_id=application.id,
        original_filename=resume_filename,
        content_type=resume_content_type,
        content=resume_bytes,
    )

    reloaded = await application_service.get_application(db, application.id)
    assert reloaded is not None

    # No email is sent here. Candidate email is manual-only: a recruiter
    # reviews the application and sends "Application received" (or any other
    # template) from the application page.
    return reloaded

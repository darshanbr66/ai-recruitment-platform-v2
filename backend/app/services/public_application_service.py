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
from app.models.organization import Organization
from app.services import application_service, candidate_service, notification_service, resume_service


async def apply_to_job(
    db: AsyncSession,
    storage: ResumeStorage,
    *,
    organization_id: uuid.UUID,
    job_id: uuid.UUID,
    full_name: str,
    email: str,
    phone: str | None,
    resume_filename: str,
    resume_content_type: str,
    resume_bytes: bytes,
) -> Application:
    job = await db.get(Job, job_id)
    if job is None or job.status != JobStatus.OPEN:
        raise NotFoundError("This job is not accepting applications.")

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
        )
        db.add(candidate)
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

    # Best-effort: a failed/unconfigured email provider must never fail the
    # application itself (CLAUDE.md § 2: "Email provider != business logic").
    organization = await db.get(Organization, organization_id)
    if organization is not None:
        await notification_service.send_application_confirmation(
            to=reloaded.candidate.email,
            candidate_name=reloaded.candidate.full_name,
            job_title=reloaded.job.title,
            organization_name=organization.name,
        )

    return reloaded

"""HR adding a resume + applying role for a candidate they manage — the
staff-side entry into the normal application / AI screening pipeline.

It composes the existing pieces rather than duplicating them: the
application comes from `application_service.create_application` (source
RECRUITER_ADDED, never self-service, so the candidate's reapply window is
untouched), the file goes through `resume_service.save_resume` (the same
validation and storage abstraction as every other resume), and screening
goes through the same gate as a self-service submission
(`public_application_service.screen_new_application`): MATCH stays APPLIED
for review, NOT_MATCH becomes AI_SCREENED_OUT (advisory, HR can override),
and an AI failure leaves the application in APPLIED untouched.

No candidate OTP is involved: HR is authenticated staff acting on a
candidate in their own organization. The candidate's email/mobile
uniqueness is enforced where the candidate itself is created or edited.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.rls import set_tenant_context
from app.integrations.storage import ResumeStorage
from app.models.application import Application, ApplicationSource, ApplicationStatus
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.screening import ScreeningRun
from app.models.user import User
from app.services import (
    activity_service,
    application_service,
    public_application_service,
    resume_service,
    screening_service,
)


@dataclass(frozen=True)
class HrApplicationResult:
    application: Application
    #: Newest screening run for the application (None = screening not run).
    screening: ScreeningRun | None
    #: True when the resume was attached to an already-existing application
    #: for this role that had none, rather than a new application created.
    attached_to_existing: bool


async def add_resume_for_role(
    db: AsyncSession,
    storage: ResumeStorage,
    *,
    organization_id: uuid.UUID,
    candidate_id: uuid.UUID,
    job_id: uuid.UUID,
    actor: User,
    resume_filename: str,
    resume_content_type: str,
    resume_bytes: bytes,
    run_screening: bool,
) -> HrApplicationResult:
    """Creates the candidate's application for `job_id` with this resume (or
    attaches the resume to their existing, resume-less application for that
    role), commits it, then optionally screens it. The application is
    durable before the AI call, so a slow or failing model can never lose
    or corrupt it. Every id is re-checked against `organization_id`."""
    candidate = await db.get(Candidate, candidate_id)
    if (
        candidate is None
        or candidate.deleted_at is not None
        or candidate.organization_id != organization_id
    ):
        raise NotFoundError("Candidate not found.")
    job = await db.get(Job, job_id)
    if job is None or job.deleted_at is not None or job.organization_id != organization_id:
        raise NotFoundError("Job not found.")
    if job.status not in application_service.MATCHABLE_JOB_STATUSES:
        raise ConflictError("This job is closed; a candidate can't be added to it.")
    # Cheap checks first: a bad file never creates an application.
    resume_service.validate_resume_upload(filename=resume_filename, content=resume_bytes)

    existing = await db.scalar(
        select(Application).where(
            Application.organization_id == organization_id,
            Application.candidate_id == candidate_id,
            Application.job_id == job_id,
        )
    )
    if existing is not None:
        existing = await application_service.get_application(db, existing.id)
        assert existing is not None
        if existing.deleted_at is not None:
            raise ConflictError(
                "This candidate's application for this role was archived; it can't be reused."
            )
        if existing.resume is not None:
            raise ConflictError(
                "This candidate already has an application with a resume for this role."
            )
        application = existing
    else:
        application = await application_service.create_application(
            db,
            organization_id=organization_id,
            candidate_id=candidate_id,
            job_id=job_id,
            source=ApplicationSource.RECRUITER_ADDED,
            actor_user_id=actor.id,
        )

    await resume_service.save_resume(
        db,
        storage,
        organization_id=organization_id,
        candidate_id=candidate_id,
        application_id=application.id,
        original_filename=resume_filename,
        content_type=resume_content_type,
        content=resume_bytes,
        uploaded_by_user_id=actor.id,
    )
    await db.refresh(application, attribute_names=["resume"])
    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="CANDIDATE_RESUME_ADDED",
        entity_type="application",
        entity_id=application.id,
        entity_label=f"{candidate.full_name} — {job.title}",
        description=(
            f'HR added a resume ("{resume_filename}") for {candidate.full_name} for '
            f'"{job.title}".'
        ),
    )
    # Durable before the AI call; RLS tenant context is transaction-scoped,
    # so it is re-applied after every commit.
    await db.commit()
    await set_tenant_context(db, organization_id)

    if run_screening:
        if application.status == ApplicationStatus.APPLIED:
            await public_application_service.screen_new_application(
                db,
                organization_id=organization_id,
                application=application,
                requested_by_user_id=actor.id,
            )
        else:
            # Past APPLIED the gate no longer applies (HR already moved it
            # on): the screening is recorded as advisory evidence only.
            await screening_service.run_screening(
                db,
                organization_id=organization_id,
                application_id=application.id,
                requested_by_user_id=actor.id,
            )
        await db.commit()
        await set_tenant_context(db, organization_id)

    reloaded = await application_service.get_application(db, application.id)
    assert reloaded is not None
    runs = await screening_service.list_screening_runs(db, application.id)
    return HrApplicationResult(
        application=reloaded,
        screening=runs[0] if runs else None,
        attached_to_existing=existing is not None,
    )

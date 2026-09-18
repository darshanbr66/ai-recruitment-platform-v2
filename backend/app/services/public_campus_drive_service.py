"""Candidate-facing campus drive access by opaque link token — no login
required (docs/campus-hiring.md § 3). Same RLS-bootstrap pattern as
app/services/assessment_public_service.py: resolve the drive's tenant via
`rls_bypass` (the token is looked up before any org is known), then set
tenant context so the rest of the request runs under ordinary RLS.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import AppError, NotFoundError
from app.core.security import hash_opaque_token
from app.db.rls import rls_bypass, set_tenant_context
from app.integrations.storage import ResumeStorage
from app.models.application import ApplicationSource, ApplicationStatus
from app.models.campus_drive import CampusDrive, CampusDriveStatus
from app.models.candidate import Candidate, CandidateSource
from app.models.organization import Organization
from app.services import (
    application_service,
    assessment_service,
    candidate_service,
    notification_service,
    resume_service,
)

_INVALID_MESSAGE = "This campus drive link is no longer valid."


async def get_drive_by_token(db: AsyncSession, token: str) -> CampusDrive:
    """A soft-deleted drive (`deleted_at` set) is excluded here — it must
    behave exactly like an invalid/unknown token to a public caller
    (SIGVITAS platform overhaul § 16), never fall through to the CLOSED
    branch's slightly more specific messaging."""
    token_hash = hash_opaque_token(token)
    async with rls_bypass(db):
        result = await db.execute(
            select(CampusDrive)
            .where(CampusDrive.link_token_hash == token_hash, CampusDrive.deleted_at.is_(None))
            .options(joinedload(CampusDrive.job), joinedload(CampusDrive.default_assessment))
        )
        drive = result.unique().scalar_one_or_none()

    if drive is None or drive.status == CampusDriveStatus.DRAFT:
        raise NotFoundError(_INVALID_MESSAGE)

    await set_tenant_context(db, drive.organization_id)
    return drive


async def apply_to_drive(
    db: AsyncSession,
    storage: ResumeStorage,
    *,
    token: str,
    full_name: str,
    email: str,
    phone: str | None,
    resume_filename: str,
    resume_content_type: str,
    resume_bytes: bytes,
) -> tuple:
    drive = await get_drive_by_token(db, token)
    if drive.status != CampusDriveStatus.ACTIVE:
        raise AppError(
            "This campus drive is not currently accepting applications.",
            code="drive_not_active",
        )

    candidate = await candidate_service.get_candidate_by_email(
        db, organization_id=drive.organization_id, email=email
    )
    if candidate is None:
        candidate = Candidate(
            organization_id=drive.organization_id,
            email=email,
            full_name=full_name,
            phone=phone,
            source=CandidateSource.CAMPUS_IMPORT,
        )
        db.add(candidate)
        await db.flush()

    application = await application_service.create_application(
        db,
        organization_id=drive.organization_id,
        candidate_id=candidate.id,
        job_id=drive.job_id,
        source=ApplicationSource.CAMPUS_IMPORT,
        actor_user_id=None,
        campus_drive_id=drive.id,
    )

    await resume_service.save_resume(
        db,
        storage,
        organization_id=drive.organization_id,
        candidate_id=candidate.id,
        application_id=application.id,
        original_filename=resume_filename,
        content_type=resume_content_type,
        content=resume_bytes,
    )

    invitation_link: str | None = None
    if drive.default_assessment_id is not None:
        # Fast-track through the ordinary application workflow so a
        # campus-drive application with a default assessment still goes
        # through the same legal transitions as any other application
        # (docs/recruitment-workflow.md) — just automatically, since the
        # candidate applied specifically to take it.
        await application_service.change_status(
            db, application, to_status=ApplicationStatus.UNDER_REVIEW, actor_user_id=None
        )
        await application_service.change_status(
            db, application, to_status=ApplicationStatus.SCREENING, actor_user_id=None
        )
        _invitation, raw_token = await assessment_service.invite_candidate(
            db,
            organization_id=drive.organization_id,
            assessment_id=drive.default_assessment_id,
            application_id=application.id,
            invited_by_user_id=drive.created_by,
        )
        invitation_link = f"/assessment/{raw_token}"

    reloaded = await application_service.get_application(db, application.id)
    assert reloaded is not None

    organization = await db.get(Organization, drive.organization_id)
    if organization is not None:
        await notification_service.send_application_confirmation(
            to=reloaded.candidate.email,
            candidate_name=reloaded.candidate.full_name,
            job_title=reloaded.job.title,
            organization_name=organization.name,
        )

    return reloaded, invitation_link

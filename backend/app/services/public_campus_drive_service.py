"""Candidate-facing campus drive access by opaque link token — no login
required (docs/campus-hiring.md § 3). Same RLS-bootstrap pattern as
app/services/assessment_public_service.py: resolve the drive's tenant via
`rls_bypass` (the token is looked up before any org is known), then set
tenant context so the rest of the request runs under ordinary RLS.

Applying through a drive link follows exactly the same candidate identity
rules as the careers site — email verified by one-time code, unique
normalized mobile, unique email, one self-service application per person,
AI screening against the drive's job, automatic welcome email — because it
*is* the same flow (public_application_service.submit_application). The
only campus-specific step is the default-assessment fast-track below.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import AppError, NotFoundError
from app.core.security import hash_opaque_token
from app.db.rls import rls_bypass, set_tenant_context
from app.integrations.storage import ResumeStorage
from app.models.application import ApplicationStatus
from app.models.campus_drive import CampusDrive, CampusDriveStatus
from app.models.organization import Organization
from app.schemas.candidate import PublicApplicantProfile
from app.schemas.public import PublicApplicationOutcome
from app.services import (
    application_service,
    assessment_service,
    email_verification_service,
    public_application_service,
)
from app.services.email_verification_service import CodeSent, IssuedToken

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


async def get_organization(db: AsyncSession, drive: CampusDrive) -> Organization:
    organization = await db.get(Organization, drive.organization_id)
    if organization is None:  # FK RESTRICT makes this unreachable in practice
        raise NotFoundError(_INVALID_MESSAGE)
    return organization


def _require_active(drive: CampusDrive) -> None:
    if drive.status != CampusDriveStatus.ACTIVE:
        raise AppError(
            "This campus drive is not currently accepting applications.",
            code="drive_not_active",
        )


async def request_email_code(
    db: AsyncSession, *, token: str, email: str
) -> CodeSent:
    """Same one-time-code flow (and the same per-email limits) as the careers
    site, scoped to the drive's organization."""
    drive = await get_drive_by_token(db, token)
    _require_active(drive)
    organization = await get_organization(db, drive)
    return await email_verification_service.request_code(
        db, organization=organization, email=email
    )


async def verify_email_code(
    db: AsyncSession, *, token: str, email: str, code: str
) -> IssuedToken:
    drive = await get_drive_by_token(db, token)
    _require_active(drive)
    organization = await get_organization(db, drive)
    return await public_application_service.verify_applicant_email(
        db, organization=organization, email=email, code=code
    )


@dataclass(frozen=True)
class DriveSubmissionResult:
    submission: public_application_service.SubmissionResult
    organization: Organization
    assessment_invitation_link: str | None


async def apply_to_drive(
    db: AsyncSession,
    storage: ResumeStorage,
    *,
    token: str,
    email: str,
    verification_token: str | None,
    profile: PublicApplicantProfile,
    resume_filename: str,
    resume_bytes: bytes,
) -> DriveSubmissionResult:
    drive = await get_drive_by_token(db, token)
    _require_active(drive)
    organization = await get_organization(db, drive)

    submission = await public_application_service.submit_application(
        db,
        storage,
        organization=organization,
        job_id=drive.job_id,
        email=email,
        verification_token=verification_token,
        profile=profile,
        resume_filename=resume_filename,
        resume_content_type="application/pdf",
        resume_bytes=resume_bytes,
        campus_drive=drive,
    )

    invitation_link: str | None = None
    # Only an application that entered the pipeline is fast-tracked into
    # the drive's assessment. An AI-screened-out one waits for HR, who can
    # override the screening and invite the candidate manually.
    if (
        drive.default_assessment_id is not None
        and submission.outcome == PublicApplicationOutcome.RECEIVED
    ):
        application = submission.application
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

    return DriveSubmissionResult(
        submission=submission,
        organization=organization,
        assessment_invitation_link=invitation_link,
    )

"""Orchestrates the candidate-facing (self-service) apply flow — the one
place that composes email verification + candidate_service +
application_service + resume_service + screening for an anonymous caller.
Both self-service entry points use it, so they follow exactly the same
identity rules: the careers site (app/api/v1/public/applications.py) and a
campus drive's public link (app/services/public_campus_drive_service.py,
which adds the drive's default-assessment fast-track on top).

Flow (first HR meeting requirements, docs/recruitment-workflow.md § 6):

    verified email (token) -> identity check (email/mobile: one profile per
    person; a returning candidate reuses their profile, at most one
    self-service application per reapply window — app/services/
    reapply_service.py) -> Candidate + Application + resume saved and
    COMMITTED -> AI screening against the job's JD ->
    NOT_MATCH: AI_SCREENED_OUT (retained, visible to HR, overridable)
    MATCH / AI unavailable: stays APPLIED for recruiter review
    -> automatic welcome email, for both outcomes (the screened-out version
    tells the candidate they are not eligible for this particular role).

The application is committed *before* the AI call and before any email:
neither a slow/failed model nor a failed email can lose it.
"""

import uuid
from dataclasses import dataclass
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.db.rls import set_tenant_context
from app.email_templates.system import render_welcome_email
from app.integrations.email import EmailError
from app.integrations.storage import ResumeStorage
from app.models.application import Application, ApplicationSource, ApplicationStatus
from app.models.campus_drive import CampusDrive, CampusDriveStatus
from app.models.candidate import Candidate, CandidateSource
from app.models.email_verification import EmailVerification
from app.models.job import Job, JobStatus
from app.models.organization import Organization
from app.models.screening import ScreeningDecision, ScreeningRun, ScreeningStatus
from app.schemas.candidate import PublicApplicantProfile
from app.schemas.public import PublicApplicationOutcome
from app.services import (
    activity_service,
    application_service,
    candidate_service,
    email_verification_service,
    notification_service,
    reapply_service,
    resume_service,
    screening_service,
)
from app.services.email_verification_service import IssuedToken

logger = get_logger(__name__)

AI_SCREENED_OUT_REASON = (
    "Automatic AI screening: the resume did not sufficiently match this job's requirements. "
    "Advisory only — HR can override."
)


def already_registered_message(contact_email: str | None) -> str:
    """Deliberately says nothing about *which* detail matched or what the
    existing profile contains — safe to show an unauthenticated caller."""
    contact = (
        f"please contact our recruitment team at {contact_email}"
        if contact_email
        else "please contact our recruitment team"
    )
    return (
        "An application has already been submitted with the details provided. Our "
        "recruitment team considers your profile for other suitable roles. If you need to "
        f"update your information, {contact}."
    )


@dataclass(frozen=True)
class SubmissionResult:
    application: Application
    outcome: PublicApplicationOutcome
    confirmation_email_sent: bool


async def verify_applicant_email(
    db: AsyncSession, *, organization: Organization, email: str, code: str
) -> IssuedToken:
    """Verifies the code, then stops a returning candidate who may not
    self-apply yet from continuing into a form they can't submit. Revealing
    their own application dates is safe at this point: the caller has just
    proven they own the address. A returning candidate who *may* reapply
    (window passed, HR grant, or no self-service history — e.g. a candidate
    HR created) continues normally."""
    issued = await email_verification_service.verify_code(
        db, organization_id=organization.id, email=email, code=code
    )
    existing, _ = await candidate_service.find_identity_matches(
        db, organization_id=organization.id, email=email, phone=None
    )
    if existing is not None:
        if existing.deleted_at is not None:
            raise ConflictError(
                already_registered_message(organization.careers_contact_email),
                code="already_registered",
            )
        eligibility = await reapply_service.check_eligibility(
            db, organization_id=organization.id, candidate_id=existing.id
        )
        if not eligibility.allowed:
            raise reapply_service.reapply_locked_error(
                eligibility, organization.careers_contact_email
            )
    return issued


async def _load_job(
    db: AsyncSession, job_id: uuid.UUID, *, campus_drive: CampusDrive | None
) -> Job:
    """A careers-site application needs an OPEN job. A campus drive link is
    governed by the drive's own status instead (the caller has already
    checked it is ACTIVE), exactly as before this flow existed — the drive's
    job only has to still exist."""
    job = await db.get(Job, job_id)
    if job is None or job.deleted_at is not None:
        raise NotFoundError("This job is not accepting applications.")
    if campus_drive is None and job.status != JobStatus.OPEN:
        raise NotFoundError("This job is not accepting applications.")
    return job


async def _block_duplicate(
    db: AsyncSession,
    *,
    organization: Organization,
    existing: Candidate,
    job: Job,
    verification: EmailVerification,
) -> NoReturn:
    """Records the blocked attempt for HR (on the existing profile — it can
    be a legitimate "please update my details" signal), burns the
    verification token so it can't be replayed to probe other mobile
    numbers, commits both, then refuses."""
    await email_verification_service.consume(db, verification)
    await activity_service.record_activity(
        db,
        organization_id=organization.id,
        actor=None,
        action="DUPLICATE_APPLICATION_BLOCKED",
        entity_type="candidate",
        entity_id=existing.id,
        entity_label=f"{existing.full_name} ({existing.email})",
        description=(
            f'A new self-service application for "{job.title}" was blocked: its email or '
            "mobile number belongs to this existing candidate profile, and the submission "
            "could not be matched to it as the same person."
        ),
    )
    await db.commit()
    raise ConflictError(
        already_registered_message(organization.careers_contact_email),
        code="already_registered",
    )


async def _block_reapply(
    db: AsyncSession,
    *,
    organization: Organization,
    existing: Candidate,
    job: Job,
    verification: EmailVerification,
    eligibility: reapply_service.ReapplyEligibility,
) -> NoReturn:
    """The verified owner of an existing profile applying again inside the
    reapply window: recorded for HR (who can grant an early reapply), token
    burned, committed, then refused with the date they may apply again."""
    await email_verification_service.consume(db, verification)
    await activity_service.record_activity(
        db,
        organization_id=organization.id,
        actor=None,
        action="SELF_REAPPLY_BLOCKED",
        entity_type="candidate",
        entity_id=existing.id,
        entity_label=f"{existing.full_name} ({existing.email})",
        description=(
            f'{existing.full_name} tried to apply for "{job.title}" before the reapply window '
            "ended."
        ),
    )
    await db.commit()
    raise reapply_service.reapply_locked_error(eligibility, organization.careers_contact_email)


async def _identify_applicant(
    db: AsyncSession,
    *,
    organization: Organization,
    email: str,
    profile: PublicApplicantProfile,
    job: Job,
    verification: EmailVerification,
) -> Candidate | None:
    """The existing profile this verified submission belongs to (None = a
    new person). The email is the identity key — its owner just proved
    control of it. A mobile number already held by a *different* profile,
    or a soft-deleted profile, is refused exactly as before, revealing
    nothing about that profile."""
    by_email, by_phone = await candidate_service.find_identity_matches(
        db, organization_id=organization.id, email=email, phone=profile.phone
    )
    if by_phone is not None and (by_email is None or by_phone.id != by_email.id):
        await _block_duplicate(
            db, organization=organization, existing=by_phone, job=job, verification=verification
        )
    if by_email is None:
        return None
    if by_email.deleted_at is not None:
        await _block_duplicate(
            db, organization=organization, existing=by_email, job=job, verification=verification
        )

    # Serializes concurrent submissions for the same person, so two tabs
    # can't both pass the window check.
    await db.refresh(by_email, with_for_update=True)
    eligibility = await reapply_service.check_eligibility(
        db, organization_id=organization.id, candidate_id=by_email.id
    )
    if not eligibility.allowed:
        await _block_reapply(
            db,
            organization=organization,
            existing=by_email,
            job=job,
            verification=verification,
            eligibility=eligibility,
        )
    already_for_job = await db.scalar(
        select(Application.id).where(
            Application.organization_id == organization.id,
            Application.candidate_id == by_email.id,
            Application.job_id == job.id,
        )
    )
    if already_for_job is not None:
        # One application per candidate per job (uq_applications_candidate_job);
        # the token stays valid so they can choose another role.
        raise ConflictError(
            "You have already applied for this role. You're welcome to apply for another "
            "open role instead.",
            code="already_applied_to_job",
        )
    return by_email


async def _refresh_returning_profile(
    db: AsyncSession,
    *,
    organization: Organization,
    candidate: Candidate,
    profile: PublicApplicantProfile,
    verification: EmailVerification,
    campus_drive: CampusDrive | None,
) -> None:
    """A returning candidate keeps the same profile; the details they just
    submitted (with a freshly verified email) are their current ones, so
    they replace the stored values. Source, history and every earlier
    application stay untouched."""
    for field, value in profile.model_dump().items():
        setattr(candidate, field, value)
    candidate.email_verified_at = verification.verified_at
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        # The mobile number was taken by another profile concurrently.
        raise ConflictError(
            already_registered_message(organization.careers_contact_email),
            code="already_registered",
        ) from exc

    label = f"{candidate.full_name} ({candidate.email})"
    await activity_service.record_activity(
        db,
        organization_id=organization.id,
        actor=None,
        action="CANDIDATE_REAPPLIED",
        entity_type="candidate",
        entity_id=candidate.id,
        entity_label=label,
        description=(
            f'{candidate.full_name} applied again through the campus drive "{campus_drive.name}"; '
            "their profile details were updated from the new submission."
            if campus_drive
            else f"{candidate.full_name} applied again through the careers site; their profile "
            "details were updated from the new submission."
        ),
    )
    await activity_service.record_activity(
        db,
        organization_id=organization.id,
        actor=None,
        action="CANDIDATE_EMAIL_VERIFIED",
        entity_type="candidate",
        entity_id=candidate.id,
        entity_label=label,
        description=f"{candidate.email} was verified with a one-time code.",
    )


async def _create_new_profile(
    db: AsyncSession,
    *,
    organization: Organization,
    email: str,
    profile: PublicApplicantProfile,
    verification: EmailVerification,
    campus_drive: CampusDrive | None,
) -> Candidate:
    candidate = Candidate(
        organization_id=organization.id,
        email=email,
        source=CandidateSource.CAMPUS_IMPORT if campus_drive else CandidateSource.PORTAL,
        email_verified_at=verification.verified_at,
        **profile.model_dump(),
    )
    db.add(candidate)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        # Lost a race with a concurrent submission for the same person.
        raise ConflictError(
            already_registered_message(organization.careers_contact_email),
            code="already_registered",
        ) from exc

    label = f"{candidate.full_name} ({candidate.email})"
    await activity_service.record_activity(
        db,
        organization_id=organization.id,
        actor=None,
        action="CANDIDATE_REGISTERED",
        entity_type="candidate",
        entity_id=candidate.id,
        entity_label=label,
        description=(
            f"{candidate.full_name} created a profile through the campus drive "
            f'"{campus_drive.name}".'
            if campus_drive
            else f"{candidate.full_name} created a profile through the careers site."
        ),
    )
    await activity_service.record_activity(
        db,
        organization_id=organization.id,
        actor=None,
        action="CANDIDATE_EMAIL_VERIFIED",
        entity_type="candidate",
        entity_id=candidate.id,
        entity_label=label,
        description=f"{candidate.email} was verified with a one-time code.",
    )
    return candidate


async def submit_application(
    db: AsyncSession,
    storage: ResumeStorage,
    *,
    organization: Organization,
    job_id: uuid.UUID,
    email: str,
    verification_token: str | None,
    profile: PublicApplicantProfile,
    resume_filename: str,
    resume_content_type: str,
    resume_bytes: bytes,
    campus_drive: CampusDrive | None = None,
) -> SubmissionResult:
    """`campus_drive` set = the candidate came in through that drive's public
    link: the application is tied to that drive and recorded with the
    campus sources; every identity rule, the screening and the welcome
    email are identical to the careers site."""
    job = await _load_job(db, job_id, campus_drive=campus_drive)
    # Cheap checks first, so a bad file never spends the verification token.
    resume_service.validate_resume_upload(
        filename=resume_filename, content=resume_bytes, pdf_only=True
    )
    email = email_verification_service.normalize_email(email)
    verification = await email_verification_service.require_verified_token(
        db, organization_id=organization.id, email=email, token=verification_token
    )

    existing = await _identify_applicant(
        db,
        organization=organization,
        email=email,
        profile=profile,
        job=job,
        verification=verification,
    )
    if existing is not None:
        candidate = existing
        await _refresh_returning_profile(
            db,
            organization=organization,
            candidate=candidate,
            profile=profile,
            verification=verification,
            campus_drive=campus_drive,
        )
    else:
        candidate = await _create_new_profile(
            db,
            organization=organization,
            email=email,
            profile=profile,
            verification=verification,
            campus_drive=campus_drive,
        )

    if campus_drive is None:
        # A job with an ACTIVE campus drive gets a careers-site application
        # associated automatically (docs/campus-hiring.md § 2: "Public portal
        # association").
        campus_drive_id = await db.scalar(
            select(CampusDrive.id).where(
                CampusDrive.job_id == job.id, CampusDrive.status == CampusDriveStatus.ACTIVE
            )
        )
    else:
        campus_drive_id = campus_drive.id
    application = await application_service.create_application(
        db,
        organization_id=organization.id,
        candidate_id=candidate.id,
        job_id=job.id,
        source=ApplicationSource.CAMPUS_IMPORT if campus_drive else ApplicationSource.PORTAL,
        actor_user_id=None,
        campus_drive_id=campus_drive_id,
        is_self_service=True,
    )
    if existing is not None:
        await reapply_service.consume_open_grant(
            db, organization_id=organization.id, candidate=candidate, application_id=application.id
        )
    await resume_service.save_resume(
        db,
        storage,
        organization_id=organization.id,
        candidate_id=candidate.id,
        application_id=application.id,
        original_filename=resume_filename,
        content_type=resume_content_type,
        content=resume_bytes,
        pdf_only=True,
    )
    # `application` was loaded (resume: none yet) before the resume existed;
    # refresh it so screening below sees the file just stored.
    await db.refresh(application, attribute_names=["resume"])
    await email_verification_service.consume(db, verification)

    # Durable from here on: the AI call below can take tens of seconds and
    # may fail; the application must survive either. RLS tenant context is
    # transaction-scoped, so it is re-applied after every commit.
    await db.commit()
    await set_tenant_context(db, organization.id)

    outcome = await screen_new_application(
        db, organization_id=organization.id, application=application
    )
    await db.commit()
    await set_tenant_context(db, organization.id)

    email_sent = await _send_welcome_email(
        db,
        organization=organization,
        candidate=candidate,
        job=job,
        application=application,
        eligible_for_role=outcome == PublicApplicationOutcome.RECEIVED,
    )

    reloaded = await application_service.get_application(db, application.id)
    assert reloaded is not None
    return SubmissionResult(
        application=reloaded, outcome=outcome, confirmation_email_sent=email_sent
    )


async def screen_new_application(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    application: Application,
    requested_by_user_id: uuid.UUID | None = None,
) -> PublicApplicationOutcome:
    """Runs the AI screening against the job's JD and applies the gate. Any
    failure — provider down, unreadable PDF, or an unexpected error — leaves
    the application in APPLIED for a recruiter: the AI only ever screens
    *out* on an explicit, successful NOT_MATCH verdict.

    Also the gate for an application HR creates with a resume
    (app/services/hr_candidate_intake_service.py), where
    `requested_by_user_id` is that HR user; the AI_SCREENED_OUT status
    change itself is always the system's, never the person's. The caller
    must have committed the application first — a crash here rolls back."""
    label = f"{application.candidate.full_name} — {application.job.title}"
    run: ScreeningRun | None
    try:
        run = await screening_service.run_screening(
            db,
            organization_id=organization_id,
            application_id=application.id,
            requested_by_user_id=requested_by_user_id,
        )
    except Exception:  # never lose or block the application over screening
        logger.exception(
            "Submission-time AI screening crashed",
            extra={"extra_fields": {"application_id": str(application.id)}},
        )
        await db.rollback()
        await set_tenant_context(db, organization_id)
        run = None

    if run is None or run.status != ScreeningStatus.COMPLETED:
        await activity_service.record_activity(
            db,
            organization_id=organization_id,
            actor=None,
            action="AI_SCREENING_FAILED",
            entity_type="application",
            entity_id=application.id,
            entity_label=label,
            description=(
                "Automatic AI screening could not be completed; the application is waiting "
                "for manual recruiter review."
            ),
        )
        return PublicApplicationOutcome.RECEIVED

    if run.decision == ScreeningDecision.NOT_MATCH:
        await application_service.change_status(
            db,
            application,
            to_status=ApplicationStatus.AI_SCREENED_OUT,
            actor_user_id=None,
            reason=AI_SCREENED_OUT_REASON,
        )
        await activity_service.record_activity(
            db,
            organization_id=organization_id,
            actor=None,
            action="AI_SCREENED_OUT",
            entity_type="application",
            entity_id=application.id,
            entity_label=label,
            description=(
                "Automatic AI screening judged the resume a NOT_MATCH for this job. The "
                "profile is retained and HR can override the decision."
            ),
        )
        return PublicApplicationOutcome.NOT_SHORTLISTED_FOR_ROLE

    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=None,
        action="AI_SCREENING_COMPLETED",
        entity_type="application",
        entity_id=application.id,
        entity_label=label,
        description="Automatic AI screening judged the resume a MATCH for this job.",
    )
    return PublicApplicationOutcome.RECEIVED


async def _send_welcome_email(
    db: AsyncSession,
    *,
    organization: Organization,
    candidate: Candidate,
    job: Job,
    application: Application,
    eligible_for_role: bool,
) -> bool:
    """Sent after every successful verified submission, whatever the
    screening decided (`eligible_for_role=False` = the screened-out version).
    Best-effort by design: the application is already committed, so a
    delivery failure is logged and audited — and reported as "not sent" to
    the candidate — but never undoes or fails the submission."""
    rendered = render_welcome_email(
        company_name=organization.name,
        candidate_name=candidate.full_name,
        job_title=job.title,
        contact_email=organization.careers_contact_email,
        eligible_for_role=eligible_for_role,
    )
    label = f"{candidate.full_name} — {job.title}"
    try:
        await notification_service.send_email(
            to=[candidate.email],
            subject=rendered.subject,
            html=rendered.html,
            text=rendered.text,
            reply_to=organization.careers_contact_email,
            kind="candidate_welcome",
        )
    except EmailError as exc:
        await activity_service.record_activity(
            db,
            organization_id=organization.id,
            actor=None,
            action="CANDIDATE_WELCOME_EMAIL_FAILED",
            entity_type="application",
            entity_id=application.id,
            entity_label=label,
            description=f"The automatic welcome email to {candidate.full_name} could not be sent.",
            reason=str(exc)[:500],
        )
        return False

    await activity_service.record_activity(
        db,
        organization_id=organization.id,
        actor=None,
        action="CANDIDATE_WELCOME_EMAIL_SENT",
        entity_type="application",
        entity_id=application.id,
        entity_label=label,
        description=f'Welcome email sent to {candidate.full_name} ("{rendered.subject}").',
    )
    return True

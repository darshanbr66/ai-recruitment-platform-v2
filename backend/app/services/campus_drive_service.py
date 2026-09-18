import uuid
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_opaque_token, hash_opaque_token
from app.models.application import Application, ApplicationStatus
from app.models.assessment import Assessment, AssessmentInvitation, AssessmentResult
from app.models.campus_drive import CAMPUS_DRIVE_TRANSITIONS, CampusDrive, CampusDriveStatus
from app.models.user import User
from app.schemas.campus_drive import (
    CampusDriveCreateRequest,
    CampusDriveFunnelCounts,
    CampusDriveUpdateRequest,
)
from app.schemas.job import JobCreateRequest
from app.services import activity_service, job_service

_STATUS_ACTIONS = {
    CampusDriveStatus.ACTIVE: "CAMPUS_DRIVE_ACTIVATED",
    CampusDriveStatus.PAUSED: "CAMPUS_DRIVE_PAUSED",
    CampusDriveStatus.CLOSED: "CAMPUS_DRIVE_CLOSED",
}


async def _resolve_job_id(
    db: AsyncSession, *, actor: User, payload: CampusDriveCreateRequest
) -> uuid.UUID:
    if payload.job_id is not None:
        job = await job_service.get_job(db, payload.job_id)
        if job is None:
            raise NotFoundError("Job not found.")
        return job.id

    assert payload.new_job_title is not None and payload.new_job_description is not None
    job = await job_service.create_job(
        db,
        actor=actor,
        payload=JobCreateRequest(title=payload.new_job_title, description=payload.new_job_description),
    )
    return job.id


async def create_campus_drive(
    db: AsyncSession, *, actor: User, payload: CampusDriveCreateRequest
) -> tuple[CampusDrive, str]:
    """Returns the drive and its raw public application-link token — shown
    once, like an assessment invitation link (only the hash is persisted)."""
    assert actor.organization_id is not None
    if payload.default_assessment_id is not None:
        assessment = await db.get(Assessment, payload.default_assessment_id)
        if assessment is None:
            raise NotFoundError("Assessment not found.")

    job_id = await _resolve_job_id(db, actor=actor, payload=payload)

    raw_token = generate_opaque_token()
    drive = CampusDrive(
        organization_id=actor.organization_id,
        created_by=actor.id,
        name=payload.name,
        job_id=job_id,
        college_name=payload.college_name,
        description=payload.description,
        batch_year=payload.batch_year,
        start_date=payload.start_date,
        end_date=payload.end_date,
        registration_deadline=payload.registration_deadline,
        default_assessment_id=payload.default_assessment_id,
        link_token_hash=hash_opaque_token(raw_token),
    )
    db.add(drive)
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=drive.organization_id,
        actor=actor,
        action="CAMPUS_DRIVE_CREATED",
        entity_type="campus_drive",
        entity_id=drive.id,
        entity_label=drive.name,
        description=f"Campus drive \"{drive.name}\" was created.",
    )

    reloaded = await get_campus_drive(db, drive.id)
    assert reloaded is not None
    return reloaded, raw_token


async def list_campus_drives(db: AsyncSession, organization_id: uuid.UUID) -> list[CampusDrive]:
    result = await db.execute(
        select(CampusDrive)
        .where(CampusDrive.organization_id == organization_id, CampusDrive.deleted_at.is_(None))
        .options(joinedload(CampusDrive.job), joinedload(CampusDrive.default_assessment))
        .order_by(CampusDrive.created_at.desc())
    )
    return list(result.unique().scalars().all())


async def get_campus_drive(db: AsyncSession, drive_id: uuid.UUID) -> CampusDrive | None:
    result = await db.execute(
        select(CampusDrive)
        .where(CampusDrive.id == drive_id)
        .options(joinedload(CampusDrive.job), joinedload(CampusDrive.default_assessment))
    )
    return result.unique().scalar_one_or_none()


async def update_campus_drive(
    db: AsyncSession, drive: CampusDrive, payload: CampusDriveUpdateRequest, *, actor: User
) -> CampusDrive:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return drive

    activities: list[tuple[str, str]] = []
    from_status = drive.status

    new_status = updates.pop("status", None)
    if new_status is not None and new_status != drive.status:
        allowed = CAMPUS_DRIVE_TRANSITIONS[drive.status]
        if new_status not in allowed:
            raise ConflictError(
                f"Cannot move a campus drive from {drive.status.value} to {new_status.value}."
            )
        drive.status = new_status
        if new_status == CampusDriveStatus.ACTIVE and from_status == CampusDriveStatus.CLOSED:
            activities.append(
                ("CAMPUS_DRIVE_REOPENED", f"Campus drive \"{drive.name}\" was reopened.")
            )
        else:
            action = _STATUS_ACTIONS.get(new_status, "CAMPUS_DRIVE_UPDATED")
            activities.append(
                (action, f"Campus drive \"{drive.name}\" status changed to {new_status.value}.")
            )

    if "default_assessment_id" in updates and updates["default_assessment_id"] is not None:
        assessment = await db.get(Assessment, updates["default_assessment_id"])
        if assessment is None:
            raise NotFoundError("Assessment not found.")

    assessment_mode_changed = (
        "default_assessment_id" in updates
        and updates["default_assessment_id"] != drive.default_assessment_id
    )
    if assessment_mode_changed:
        activities.append(
            (
                "CAMPUS_DRIVE_ASSESSMENT_MODE_CHANGED",
                f"Campus drive \"{drive.name}\" default assessment was changed.",
            )
        )

    other_fields = [f for f in updates if f not in ("default_assessment_id",)]
    if not activities and other_fields:
        activities.append(("CAMPUS_DRIVE_UPDATED", f"Campus drive \"{drive.name}\" was updated."))

    for field, value in updates.items():
        setattr(drive, field, value)

    await db.flush()

    for action, description in activities:
        await activity_service.record_activity(
            db,
            organization_id=drive.organization_id,
            actor=actor,
            action=action,
            entity_type="campus_drive",
            entity_id=drive.id,
            entity_label=drive.name,
            description=description,
        )

    reloaded = await get_campus_drive(db, drive.id)
    assert reloaded is not None
    return reloaded


async def delete_campus_drive(
    db: AsyncSession, drive: CampusDrive, *, actor: User, reason: str
) -> CampusDrive:
    """Soft-deletes/archives: keeps the row (and every Application sourced
    from it via `Application.campus_drive_id`) but removes it from
    `list_campus_drives` and records an Activity."""
    if drive.deleted_at is not None:
        raise ConflictError("This campus drive has already been deleted.")

    drive.deleted_at = datetime.now(UTC)
    drive.deleted_by_user_id = actor.id
    drive.deletion_reason = reason
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=drive.organization_id,
        actor=actor,
        action="CAMPUS_DRIVE_DELETED",
        entity_type="campus_drive",
        entity_id=drive.id,
        entity_label=drive.name,
        description=f"Campus drive \"{drive.name}\" was deleted.",
        reason=reason,
    )
    return drive


async def regenerate_link(db: AsyncSession, drive: CampusDrive, *, actor: User) -> str:
    raw_token = generate_opaque_token()
    drive.link_token_hash = hash_opaque_token(raw_token)
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=drive.organization_id,
        actor=actor,
        action="CAMPUS_DRIVE_LINK_REGENERATED",
        entity_type="campus_drive",
        entity_id=drive.id,
        entity_label=drive.name,
        description=f"Public application link regenerated for \"{drive.name}\".",
    )
    return raw_token


async def application_counts(
    db: AsyncSession, organization_id: uuid.UUID
) -> dict[uuid.UUID, int]:
    result = await db.execute(
        select(Application.campus_drive_id, func.count(Application.id))
        .where(
            Application.organization_id == organization_id,
            Application.campus_drive_id.is_not(None),
        )
        .group_by(Application.campus_drive_id)
    )
    return {drive_id: count for drive_id, count in result.all()}


_SCREENING_STATUSES = {ApplicationStatus.SCREENING}
_ASSESSMENT_INVITED_STATUSES = {
    ApplicationStatus.ASSESSMENT_INVITED,
    ApplicationStatus.ASSESSMENT_STARTED,
}
_ASSESSMENT_COMPLETED_STATUSES = {ApplicationStatus.ASSESSMENT_COMPLETED}


async def get_funnel_counts(db: AsyncSession, drive_id: uuid.UUID) -> CampusDriveFunnelCounts:
    """Every count is a live GROUP BY over real Application/AssessmentResult
    rows for this drive — never a fabricated/hardcoded metric (CLAUDE.md § 2)."""
    result = await db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.campus_drive_id == drive_id)
        .group_by(Application.status)
    )
    counts = Counter({status: count for status, count in result.all()})

    pass_fail_result = await db.execute(
        select(AssessmentResult.passed, func.count(AssessmentResult.id))
        .join(AssessmentInvitation, AssessmentInvitation.id == AssessmentResult.invitation_id)
        .join(Application, Application.id == AssessmentInvitation.application_id)
        .where(Application.campus_drive_id == drive_id)
        .group_by(AssessmentResult.passed)
    )
    pass_fail_counts = Counter({passed: count for passed, count in pass_fail_result.all()})

    return CampusDriveFunnelCounts(
        registered=sum(counts.values()),
        screening=sum(counts[s] for s in _SCREENING_STATUSES),
        assessment_invited=sum(counts[s] for s in _ASSESSMENT_INVITED_STATUSES),
        assessment_completed=sum(counts[s] for s in _ASSESSMENT_COMPLETED_STATUSES),
        assessment_passed=pass_fail_counts[True],
        assessment_failed=pass_fail_counts[False],
        shortlisted=counts[ApplicationStatus.SHORTLISTED],
        interview=counts[ApplicationStatus.INTERVIEW],
        selected=counts[ApplicationStatus.SELECTED],
        rejected=counts[ApplicationStatus.REJECTED],
        hired=counts[ApplicationStatus.HIRED],
    )

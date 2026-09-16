import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_opaque_token, hash_opaque_token
from app.models.application import Application, ApplicationStatus
from app.models.assessment import Assessment
from app.models.campus_drive import CAMPUS_DRIVE_TRANSITIONS, CampusDrive, CampusDriveStatus
from app.schemas.campus_drive import (
    CampusDriveCreateRequest,
    CampusDriveFunnelCounts,
    CampusDriveUpdateRequest,
)
from app.schemas.job import JobCreateRequest
from app.services import job_service


async def _resolve_job_id(
    db: AsyncSession, *, organization_id: uuid.UUID, created_by: uuid.UUID, payload: CampusDriveCreateRequest
) -> uuid.UUID:
    if payload.job_id is not None:
        job = await job_service.get_job(db, payload.job_id)
        if job is None:
            raise NotFoundError("Job not found.")
        return job.id

    assert payload.new_job_title is not None and payload.new_job_description is not None
    job = await job_service.create_job(
        db,
        organization_id=organization_id,
        created_by=created_by,
        payload=JobCreateRequest(title=payload.new_job_title, description=payload.new_job_description),
    )
    return job.id


async def create_campus_drive(
    db: AsyncSession, *, organization_id: uuid.UUID, created_by: uuid.UUID, payload: CampusDriveCreateRequest
) -> tuple[CampusDrive, str]:
    """Returns the drive and its raw public application-link token — shown
    once, like an assessment invitation link (only the hash is persisted)."""
    if payload.default_assessment_id is not None:
        assessment = await db.get(Assessment, payload.default_assessment_id)
        if assessment is None:
            raise NotFoundError("Assessment not found.")

    job_id = await _resolve_job_id(
        db, organization_id=organization_id, created_by=created_by, payload=payload
    )

    raw_token = generate_opaque_token()
    drive = CampusDrive(
        organization_id=organization_id,
        created_by=created_by,
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
    reloaded = await get_campus_drive(db, drive.id)
    assert reloaded is not None
    return reloaded, raw_token


async def list_campus_drives(db: AsyncSession, organization_id: uuid.UUID) -> list[CampusDrive]:
    result = await db.execute(
        select(CampusDrive)
        .where(CampusDrive.organization_id == organization_id)
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
    db: AsyncSession, drive: CampusDrive, payload: CampusDriveUpdateRequest
) -> CampusDrive:
    updates = payload.model_dump(exclude_unset=True)

    new_status = updates.pop("status", None)
    if new_status is not None and new_status != drive.status:
        allowed = CAMPUS_DRIVE_TRANSITIONS[drive.status]
        if new_status not in allowed:
            raise ConflictError(
                f"Cannot move a campus drive from {drive.status.value} to {new_status.value}."
            )
        drive.status = new_status

    if "default_assessment_id" in updates and updates["default_assessment_id"] is not None:
        assessment = await db.get(Assessment, updates["default_assessment_id"])
        if assessment is None:
            raise NotFoundError("Assessment not found.")

    for field, value in updates.items():
        setattr(drive, field, value)

    await db.flush()
    reloaded = await get_campus_drive(db, drive.id)
    assert reloaded is not None
    return reloaded


async def regenerate_link(db: AsyncSession, drive: CampusDrive) -> str:
    raw_token = generate_opaque_token()
    drive.link_token_hash = hash_opaque_token(raw_token)
    await db.flush()
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
    """Every count is a live GROUP BY over real Application rows for this
    drive — never a fabricated/hardcoded metric (CLAUDE.md § 2)."""
    result = await db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.campus_drive_id == drive_id)
        .group_by(Application.status)
    )
    counts = Counter({status: count for status, count in result.all()})

    return CampusDriveFunnelCounts(
        registered=sum(counts.values()),
        screening=sum(counts[s] for s in _SCREENING_STATUSES),
        assessment_invited=sum(counts[s] for s in _ASSESSMENT_INVITED_STATUSES),
        assessment_completed=sum(counts[s] for s in _ASSESSMENT_COMPLETED_STATUSES),
        shortlisted=counts[ApplicationStatus.SHORTLISTED],
        interview=counts[ApplicationStatus.INTERVIEW],
        selected=counts[ApplicationStatus.SELECTED],
        rejected=counts[ApplicationStatus.REJECTED],
        withdrawn=counts[ApplicationStatus.WITHDRAWN],
    )

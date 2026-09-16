import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.application import Application
from app.models.campus_drive import CampusDrive
from app.schemas.campus_drive import CampusDriveCreateRequest, CampusDriveUpdateRequest


async def create_campus_drive(
    db: AsyncSession, *, organization_id: uuid.UUID, created_by: uuid.UUID, payload: CampusDriveCreateRequest
) -> CampusDrive:
    drive = CampusDrive(
        organization_id=organization_id,
        created_by=created_by,
        name=payload.name,
        job_id=payload.job_id,
        college_name=payload.college_name,
        batch_year=payload.batch_year,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(drive)
    await db.flush()
    reloaded = await get_campus_drive(db, drive.id)
    assert reloaded is not None
    return reloaded


async def list_campus_drives(db: AsyncSession, organization_id: uuid.UUID) -> list[CampusDrive]:
    result = await db.execute(
        select(CampusDrive)
        .where(CampusDrive.organization_id == organization_id)
        .options(joinedload(CampusDrive.job))
        .order_by(CampusDrive.created_at.desc())
    )
    return list(result.unique().scalars().all())


async def get_campus_drive(db: AsyncSession, drive_id: uuid.UUID) -> CampusDrive | None:
    result = await db.execute(
        select(CampusDrive).where(CampusDrive.id == drive_id).options(joinedload(CampusDrive.job))
    )
    return result.unique().scalar_one_or_none()


async def update_campus_drive(
    db: AsyncSession, drive: CampusDrive, payload: CampusDriveUpdateRequest
) -> CampusDrive:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(drive, field, value)
    await db.flush()
    return drive


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

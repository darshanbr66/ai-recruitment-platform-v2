"""Recruiter-facing Campus Drive management (docs/campus-hiring.md)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.campus_drive import CampusDrive
from app.models.user import User
from app.schemas.campus_drive import (
    CampusDriveCreateRequest,
    CampusDriveResponse,
    CampusDriveUpdateRequest,
)
from app.services import campus_drive_service

router = APIRouter(prefix="/campus-drives", tags=["recruiter-campus-drives"])


def _to_response(drive: CampusDrive, application_count: int) -> CampusDriveResponse:
    return CampusDriveResponse(
        id=drive.id,
        name=drive.name,
        job_id=drive.job_id,
        job_title=drive.job.title,
        college_name=drive.college_name,
        batch_year=drive.batch_year,
        start_date=drive.start_date,
        end_date=drive.end_date,
        status=drive.status,
        application_count=application_count,
        created_at=drive.created_at,
    )


@router.post("", response_model=CampusDriveResponse, status_code=status.HTTP_201_CREATED)
async def create_campus_drive(
    payload: CampusDriveCreateRequest,
    current_user: User = Depends(require_permission("campus_drive.manage")),
    db: AsyncSession = Depends(get_db),
) -> CampusDriveResponse:
    assert current_user.organization_id is not None
    drive = await campus_drive_service.create_campus_drive(
        db, organization_id=current_user.organization_id, created_by=current_user.id, payload=payload
    )
    return _to_response(drive, 0)


@router.get("", response_model=list[CampusDriveResponse])
async def list_campus_drives(
    current_user: User = Depends(require_permission("campus_drive.read")),
    db: AsyncSession = Depends(get_db),
) -> list[CampusDriveResponse]:
    assert current_user.organization_id is not None
    drives = await campus_drive_service.list_campus_drives(db, current_user.organization_id)
    counts = await campus_drive_service.application_counts(db, current_user.organization_id)
    return [_to_response(drive, counts.get(drive.id, 0)) for drive in drives]


@router.get("/{drive_id}", response_model=CampusDriveResponse)
async def get_campus_drive(
    drive_id: uuid.UUID,
    current_user: User = Depends(require_permission("campus_drive.read")),
    db: AsyncSession = Depends(get_db),
) -> CampusDriveResponse:
    assert current_user.organization_id is not None
    drive = await campus_drive_service.get_campus_drive(db, drive_id)
    if drive is None:
        raise NotFoundError("Campus drive not found.")
    counts = await campus_drive_service.application_counts(db, current_user.organization_id)
    return _to_response(drive, counts.get(drive.id, 0))


@router.patch("/{drive_id}", response_model=CampusDriveResponse)
async def update_campus_drive(
    drive_id: uuid.UUID,
    payload: CampusDriveUpdateRequest,
    current_user: User = Depends(require_permission("campus_drive.manage")),
    db: AsyncSession = Depends(get_db),
) -> CampusDriveResponse:
    assert current_user.organization_id is not None
    drive = await campus_drive_service.get_campus_drive(db, drive_id)
    if drive is None:
        raise NotFoundError("Campus drive not found.")
    updated = await campus_drive_service.update_campus_drive(db, drive, payload)
    counts = await campus_drive_service.application_counts(db, current_user.organization_id)
    return _to_response(updated, counts.get(updated.id, 0))

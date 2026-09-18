"""Recruiter-facing Campus Drive management (docs/campus-hiring.md)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.campus_drive import CampusDrive
from app.models.user import User
from app.schemas.campus_drive import (
    CampusDriveCreateRequest,
    CampusDriveDeleteRequest,
    CampusDriveFunnelCounts,
    CampusDriveResponse,
    CampusDriveUpdateRequest,
)
from app.services import campus_drive_service

router = APIRouter(prefix="/campus-drives", tags=["recruiter-campus-drives"])


def _application_link(raw_token: str) -> str:
    # The candidate-facing app's own origin — the link a recruiter
    # copies/shares points at the frontend route that resolves the token,
    # not the API itself (settings.frontend_base_url, env-configurable).
    return f"{get_settings().frontend_base_url}/campus-drive/{raw_token}"


def _to_response(
    drive: CampusDrive, application_count: int, *, link: str | None = None
) -> CampusDriveResponse:
    return CampusDriveResponse(
        id=drive.id,
        name=drive.name,
        job_id=drive.job_id,
        job_title=drive.job.title,
        college_name=drive.college_name,
        description=drive.description,
        batch_year=drive.batch_year,
        start_date=drive.start_date,
        end_date=drive.end_date,
        registration_deadline=drive.registration_deadline,
        default_assessment_id=drive.default_assessment_id,
        default_assessment_title=drive.default_assessment.title if drive.default_assessment else None,
        status=drive.status,
        application_count=application_count,
        deleted_at=drive.deleted_at,
        created_at=drive.created_at,
        application_link=link,
    )


@router.post("", response_model=CampusDriveResponse, status_code=status.HTTP_201_CREATED)
async def create_campus_drive(
    payload: CampusDriveCreateRequest,
    current_user: User = Depends(require_permission("campus_drive.manage")),
    db: AsyncSession = Depends(get_db),
) -> CampusDriveResponse:
    assert current_user.organization_id is not None
    drive, raw_token = await campus_drive_service.create_campus_drive(
        db, actor=current_user, payload=payload
    )
    return _to_response(drive, 0, link=_application_link(raw_token))


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


@router.get("/{drive_id}/funnel", response_model=CampusDriveFunnelCounts)
async def get_campus_drive_funnel(
    drive_id: uuid.UUID,
    _: User = Depends(require_permission("campus_drive.read")),
    db: AsyncSession = Depends(get_db),
) -> CampusDriveFunnelCounts:
    drive = await campus_drive_service.get_campus_drive(db, drive_id)
    if drive is None:
        raise NotFoundError("Campus drive not found.")
    return await campus_drive_service.get_funnel_counts(db, drive_id)


@router.patch("/{drive_id}", response_model=CampusDriveResponse)
async def update_campus_drive(
    drive_id: uuid.UUID,
    payload: CampusDriveUpdateRequest,
    current_user: User = Depends(require_permission("campus_drive.manage")),
    db: AsyncSession = Depends(get_db),
) -> CampusDriveResponse:
    assert current_user.organization_id is not None
    drive = await campus_drive_service.get_campus_drive(db, drive_id)
    if drive is None or drive.deleted_at is not None:
        raise NotFoundError("Campus drive not found.")
    updated = await campus_drive_service.update_campus_drive(db, drive, payload, actor=current_user)
    counts = await campus_drive_service.application_counts(db, current_user.organization_id)
    return _to_response(updated, counts.get(updated.id, 0))


@router.post("/{drive_id}/regenerate-link", response_model=CampusDriveResponse)
async def regenerate_campus_drive_link(
    drive_id: uuid.UUID,
    current_user: User = Depends(require_permission("campus_drive.manage")),
    db: AsyncSession = Depends(get_db),
) -> CampusDriveResponse:
    assert current_user.organization_id is not None
    drive = await campus_drive_service.get_campus_drive(db, drive_id)
    if drive is None or drive.deleted_at is not None:
        raise NotFoundError("Campus drive not found.")
    raw_token = await campus_drive_service.regenerate_link(db, drive, actor=current_user)
    counts = await campus_drive_service.application_counts(db, current_user.organization_id)
    return _to_response(drive, counts.get(drive.id, 0), link=_application_link(raw_token))


@router.post("/{drive_id}/delete", response_model=CampusDriveResponse)
async def delete_campus_drive(
    drive_id: uuid.UUID,
    payload: CampusDriveDeleteRequest,
    current_user: User = Depends(require_permission("campus_drive.delete")),
    db: AsyncSession = Depends(get_db),
) -> CampusDriveResponse:
    assert current_user.organization_id is not None
    drive = await campus_drive_service.get_campus_drive(db, drive_id)
    if drive is None:
        raise NotFoundError("Campus drive not found.")
    deleted = await campus_drive_service.delete_campus_drive(
        db, drive, actor=current_user, reason=payload.reason
    )
    counts = await campus_drive_service.application_counts(db, current_user.organization_id)
    return _to_response(deleted, counts.get(deleted.id, 0))

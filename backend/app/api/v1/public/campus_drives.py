"""Candidate-facing campus drive access by opaque link token — no
authentication (docs/campus-hiring.md § 3)."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.integrations.storage import ResumeStorage, get_resume_storage
from app.models.campus_drive import CampusDriveStatus
from app.models.organization import Organization
from app.schemas.public_campus_drive import (
    PublicCampusDriveApplicationResult,
    PublicCampusDriveUnavailable,
    PublicCampusDriveView,
)
from app.services import public_campus_drive_service

router = APIRouter(prefix="/campus-drive", tags=["public-campus-drive"])


@router.get("/{token}", response_model=PublicCampusDriveView | PublicCampusDriveUnavailable)
async def get_campus_drive(
    token: str, db: AsyncSession = Depends(get_db)
) -> PublicCampusDriveView | PublicCampusDriveUnavailable:
    drive = await public_campus_drive_service.get_drive_by_token(db, token)
    if drive.status == CampusDriveStatus.CLOSED:
        return PublicCampusDriveUnavailable()

    organization = await db.get(Organization, drive.organization_id)
    return PublicCampusDriveView(
        name=drive.name,
        college_name=drive.college_name,
        description=drive.description,
        job_title=drive.job.title,
        job_description=drive.job.description,
        organization_name=organization.name if organization else "",
        registration_deadline=drive.registration_deadline,
        status=drive.status,
        has_assessment=drive.default_assessment_id is not None,
    )


@router.post("/{token}/apply", response_model=PublicCampusDriveApplicationResult, status_code=201)
async def apply_to_campus_drive(
    token: str,
    full_name: str = Form(..., min_length=1, max_length=255),
    email: str = Form(...),
    phone: str | None = Form(default=None, max_length=32),
    resume: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    storage: ResumeStorage = Depends(get_resume_storage),
) -> PublicCampusDriveApplicationResult:
    resume_bytes = await resume.read()
    application, invitation_link = await public_campus_drive_service.apply_to_drive(
        db,
        storage,
        token=token,
        full_name=full_name,
        email=email,
        phone=phone,
        resume_filename=resume.filename or "resume",
        resume_content_type=resume.content_type or "application/octet-stream",
        resume_bytes=resume_bytes,
    )
    return PublicCampusDriveApplicationResult(
        application_id=str(application.id),
        job_title=application.job.title,
        candidate_email=application.candidate.email,
        status=application.status.value,
        assessment_invitation_link=invitation_link,
    )

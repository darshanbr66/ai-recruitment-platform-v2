"""Recruiter-facing Application CRUD + status workflow. `organization_id` is
always taken from the authenticated caller, never from the request
(docs/security.md § 2). Status changes go through
app/workflows/application_workflow.py exclusively — see
docs/recruitment-workflow.md."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.integrations.storage import LocalResumeStorage, ResumeStorage, StorageError
from app.models.application import Application, ApplicationStatus
from app.models.organization import Organization
from app.models.user import User
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationDeleteRequest,
    ApplicationResponse,
    ApplicationStatusChangeRequest,
)
from app.schemas.assessment import AssessmentInvitationResponse, AssessmentResultResponse
from app.services import application_service, assessment_service, notification_service

router = APIRouter(prefix="/applications", tags=["recruiter-applications"])


def _get_resume_storage() -> ResumeStorage:
    return LocalResumeStorage()


def _to_response(application: Application) -> ApplicationResponse:
    return ApplicationResponse(
        id=application.id,
        organization_id=application.organization_id,
        candidate_id=application.candidate_id,
        candidate_full_name=application.candidate.full_name,
        job_id=application.job_id,
        job_title=application.job.title,
        campus_drive_id=application.campus_drive_id,
        status=application.status,
        source=application.source,
        applied_at=application.applied_at,
        created_at=application.created_at,
        updated_at=application.updated_at,
        resume_id=application.resume.id if application.resume else None,
        resume_filename=application.resume.original_filename if application.resume else None,
        deleted_at=application.deleted_at,
    )


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreateRequest,
    current_user: User = Depends(require_permission("application.create")),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    assert current_user.organization_id is not None
    application = await application_service.create_application(
        db,
        organization_id=current_user.organization_id,
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        source=payload.source,
        actor_user_id=current_user.id,
    )
    return _to_response(application)


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    job_id: uuid.UUID | None = Query(default=None),
    candidate_id: uuid.UUID | None = Query(default=None),
    application_status: ApplicationStatus | None = Query(default=None, alias="status"),
    campus_drive_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_permission("application.read")),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationResponse]:
    assert current_user.organization_id is not None
    applications = await application_service.list_applications(
        db,
        current_user.organization_id,
        job_id=job_id,
        candidate_id=candidate_id,
        status=application_status,
        campus_drive_id=campus_drive_id,
    )
    return [_to_response(application) for application in applications]


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID,
    _: User = Depends(require_permission("application.read")),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    application = await application_service.get_application(db, application_id)
    if application is None:
        raise NotFoundError("Application not found.")
    return _to_response(application)


@router.post("/{application_id}/delete", response_model=ApplicationResponse)
async def delete_application(
    application_id: uuid.UUID,
    payload: ApplicationDeleteRequest,
    current_user: User = Depends(require_permission("application.delete")),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    application = await application_service.get_application(db, application_id)
    if application is None:
        raise NotFoundError("Application not found.")
    deleted = await application_service.delete_application(
        db, application, actor=current_user, reason=payload.reason
    )
    return _to_response(deleted)


@router.get("/{application_id}/resume")
async def download_resume(
    application_id: uuid.UUID,
    _: User = Depends(require_permission("application.read")),
    db: AsyncSession = Depends(get_db),
    storage: ResumeStorage = Depends(_get_resume_storage),
) -> Response:
    application = await application_service.get_application(db, application_id)
    if application is None or application.resume is None:
        raise NotFoundError("No resume found for this application.")

    resume = application.resume
    try:
        content = await storage.read(resume.storage_path)
    except StorageError as exc:
        raise NotFoundError("The resume file could not be found in storage.") from exc

    safe_name = resume.original_filename.replace('"', "")
    return Response(
        content=content,
        media_type=resume.content_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


def _invitation_to_response(
    invitation, candidate_full_name: str
) -> AssessmentInvitationResponse:
    return AssessmentInvitationResponse(
        id=invitation.id,
        assessment_id=invitation.assessment_id,
        assessment_title=invitation.assessment.title,
        application_id=invitation.application_id,
        candidate_full_name=candidate_full_name,
        status=invitation.status,
        expires_at=invitation.expires_at,
        started_at=invitation.started_at,
        submitted_at=invitation.submitted_at,
        attempt_number=invitation.attempt_number,
        retest_reason=invitation.retest_reason,
        result=AssessmentResultResponse.model_validate(invitation.result) if invitation.result else None,
    )


@router.get("/{application_id}/assessment", response_model=AssessmentInvitationResponse | None)
async def get_application_assessment(
    application_id: uuid.UUID,
    _: User = Depends(require_permission("assessment.read")),
    db: AsyncSession = Depends(get_db),
) -> AssessmentInvitationResponse | None:
    invitation = await assessment_service.get_invitation_for_application(db, application_id)
    if invitation is None:
        return None
    application = await application_service.get_application(db, application_id)
    return _invitation_to_response(invitation, application.candidate.full_name if application else "")


@router.get("/{application_id}/assessment/attempts", response_model=list[AssessmentInvitationResponse])
async def list_application_assessment_attempts(
    application_id: uuid.UUID,
    _: User = Depends(require_permission("assessment.read")),
    db: AsyncSession = Depends(get_db),
) -> list[AssessmentInvitationResponse]:
    """Full retest history for this application, oldest attempt first —
    the original attempt is never overwritten or removed (CLAUDE.md § 3)."""
    application = await application_service.get_application(db, application_id)
    attempts = await assessment_service.list_attempts_for_application(db, application_id)
    candidate_name = application.candidate.full_name if application else ""
    return [_invitation_to_response(a, candidate_name) for a in attempts]


@router.post("/{application_id}/status", response_model=ApplicationResponse)
async def change_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusChangeRequest,
    current_user: User = Depends(require_permission("application.status.change")),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    application = await application_service.get_application(db, application_id)
    if application is None:
        raise NotFoundError("Application not found.")
    updated = await application_service.change_status(
        db,
        application,
        to_status=payload.to_status,
        actor_user_id=current_user.id,
        reason=payload.reason,
    )

    # Best-effort candidate notification — must never fail the status
    # change itself (CLAUDE.md § 2: "Email provider != business logic").
    organization = await db.get(Organization, current_user.organization_id)
    if organization is not None:
        await notification_service.send_status_update(
            to=updated.candidate.email,
            candidate_name=updated.candidate.full_name,
            job_title=updated.job.title,
            organization_name=organization.name,
            status=updated.status.value,
        )

    return _to_response(updated)

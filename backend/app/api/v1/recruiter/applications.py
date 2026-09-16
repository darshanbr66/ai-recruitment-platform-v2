"""Recruiter-facing Application CRUD + status workflow. `organization_id` is
always taken from the authenticated caller, never from the request
(docs/security.md § 2). Status changes go through
app/workflows/application_workflow.py exclusively — see
docs/recruitment-workflow.md."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.application import Application, ApplicationStatus
from app.models.user import User
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationResponse,
    ApplicationStatusChangeRequest,
)
from app.services import application_service

router = APIRouter(prefix="/applications", tags=["recruiter-applications"])


def _to_response(application: Application) -> ApplicationResponse:
    return ApplicationResponse(
        id=application.id,
        organization_id=application.organization_id,
        candidate_id=application.candidate_id,
        candidate_full_name=application.candidate.full_name,
        job_id=application.job_id,
        job_title=application.job.title,
        status=application.status,
        source=application.source,
        applied_at=application.applied_at,
        created_at=application.created_at,
        updated_at=application.updated_at,
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
    return _to_response(updated)

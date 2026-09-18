"""Recruiter-facing Assessment management + candidate invitations
(docs/assessment.md). `organization_id` always comes from the authenticated
caller, never the request."""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.assessment import Assessment, AssessmentInvitation
from app.models.user import User
from app.schemas.assessment import (
    AssessmentCreateRequest,
    AssessmentDeleteRequest,
    AssessmentInvitationResponse,
    AssessmentResponse,
    AssessmentResultResponse,
    AssessmentSummary,
    AssessmentUpdateRequest,
    InviteCandidateRequest,
    ParsedQuestionsResponse,
    RetestRequest,
)
from app.services import application_service, assessment_service

router = APIRouter(prefix="/assessments", tags=["recruiter-assessments"])


async def _assessment_response(db: AsyncSession, assessment: Assessment) -> AssessmentResponse:
    response = AssessmentResponse.model_validate(assessment)
    response.has_invitations = await assessment_service.assessment_has_invitations(db, assessment.id)
    return response


async def _invitation_response(
    db: AsyncSession, invitation: AssessmentInvitation, *, invitation_link: str | None = None
) -> AssessmentInvitationResponse:
    application = await application_service.get_application(db, invitation.application_id)
    return AssessmentInvitationResponse(
        id=invitation.id,
        assessment_id=invitation.assessment_id,
        assessment_title=invitation.assessment.title,
        application_id=invitation.application_id,
        candidate_full_name=application.candidate.full_name if application else "",
        status=invitation.status,
        expires_at=invitation.expires_at,
        started_at=invitation.started_at,
        submitted_at=invitation.submitted_at,
        attempt_number=invitation.attempt_number,
        retest_reason=invitation.retest_reason,
        result=AssessmentResultResponse.model_validate(invitation.result) if invitation.result else None,
        invitation_link=invitation_link,
    )


@router.post("/parse-questions", response_model=ParsedQuestionsResponse)
async def parse_import_questions(
    file: UploadFile = File(...),
    _: User = Depends(require_permission("assessment.manage")),
) -> ParsedQuestionsResponse:
    content = await file.read()
    return assessment_service.parse_import_file(content=content, filename=file.filename or "")


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    payload: AssessmentCreateRequest,
    current_user: User = Depends(require_permission("assessment.manage")),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    assert current_user.organization_id is not None
    assessment = await assessment_service.create_assessment(
        db,
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        payload=payload,
        actor=current_user,
    )
    return await _assessment_response(db, assessment)


@router.post("/{assessment_id}/delete", response_model=AssessmentResponse)
async def delete_assessment(
    assessment_id: uuid.UUID,
    payload: AssessmentDeleteRequest,
    current_user: User = Depends(require_permission("assessment.delete")),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    assessment = await assessment_service.get_assessment(db, assessment_id)
    if assessment is None:
        raise NotFoundError("Assessment not found.")
    deleted = await assessment_service.delete_assessment(
        db, assessment, actor=current_user, reason=payload.reason
    )
    return await _assessment_response(db, deleted)


@router.get("", response_model=list[AssessmentSummary])
async def list_assessments(
    current_user: User = Depends(require_permission("assessment.read")),
    db: AsyncSession = Depends(get_db),
) -> list[AssessmentSummary]:
    assert current_user.organization_id is not None
    assessments = await assessment_service.list_assessments(db, current_user.organization_id)
    return [
        AssessmentSummary(
            id=a.id,
            title=a.title,
            duration_minutes=a.duration_minutes,
            pass_score=a.pass_score,
            question_count=len(a.questions),
            created_at=a.created_at,
        )
        for a in assessments
    ]


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: uuid.UUID,
    _: User = Depends(require_permission("assessment.read")),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    assessment: Assessment | None = await assessment_service.get_assessment(db, assessment_id)
    if assessment is None:
        raise NotFoundError("Assessment not found.")
    return await _assessment_response(db, assessment)


@router.patch("/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(
    assessment_id: uuid.UUID,
    payload: AssessmentUpdateRequest,
    current_user: User = Depends(require_permission("assessment.manage")),
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    assessment = await assessment_service.get_assessment(db, assessment_id)
    if assessment is None or assessment.deleted_at is not None:
        raise NotFoundError("Assessment not found.")
    updated = await assessment_service.update_assessment(db, assessment, payload, actor=current_user)
    return await _assessment_response(db, updated)


@router.post("/invite", response_model=AssessmentInvitationResponse, status_code=status.HTTP_201_CREATED)
async def invite_candidate(
    payload: InviteCandidateRequest,
    current_user: User = Depends(require_permission("assessment.manage")),
    db: AsyncSession = Depends(get_db),
) -> AssessmentInvitationResponse:
    assert current_user.organization_id is not None
    invitation, raw_token = await assessment_service.invite_candidate(
        db,
        organization_id=current_user.organization_id,
        assessment_id=payload.assessment_id,
        application_id=payload.application_id,
        invited_by_user_id=current_user.id,
    )
    # Surfaced so a recruiter can copy the link directly when no email
    # provider is configured locally (see app/integrations/email) — this is
    # the one response that ever carries it, matching the "shown once"
    # handling of the underlying raw token.
    link = f"http://localhost:5173/assessment/{raw_token}"
    return await _invitation_response(db, invitation, invitation_link=link)


@router.post("/retest", response_model=AssessmentInvitationResponse, status_code=status.HTTP_201_CREATED)
async def retest_candidate(
    payload: RetestRequest,
    current_user: User = Depends(require_permission("assessment.manage")),
    db: AsyncSession = Depends(get_db),
) -> AssessmentInvitationResponse:
    assert current_user.organization_id is not None
    invitation, raw_token = await assessment_service.create_retest(
        db,
        organization_id=current_user.organization_id,
        application_id=payload.application_id,
        authorized_by=current_user,
        reason=payload.reason,
        assessment_choice=payload.assessment_choice,
        assessment_id=payload.assessment_id,
        new_assessment=payload.new_assessment,
    )
    link = f"http://localhost:5173/assessment/{raw_token}"
    return await _invitation_response(db, invitation, invitation_link=link)

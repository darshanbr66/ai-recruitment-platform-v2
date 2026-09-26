"""Recruiter-facing Candidate CRUD. `organization_id` is always taken from
the authenticated caller, never from the request (docs/security.md § 2)."""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.api.v1.recruiter.applications import to_response as application_response
from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.db.session import get_db
from app.integrations.storage import ResumeStorage, get_resume_storage
from app.models.candidate_reapply_grant import CandidateReapplyGrant
from app.models.user import User
from app.schemas.application import (
    ApplicationResponse,
    CandidateJobMatchRequest,
    HrApplicationWithResumeResponse,
)
from app.schemas.candidate import (
    CandidateCreateRequest,
    CandidateDeleteRequest,
    CandidateResponse,
    CandidateUpdateRequest,
    ReapplyGrantRequest,
    ReapplyGrantResponse,
    ReapplyStatusResponse,
)
from app.schemas.candidate_history import CandidateHistoryResponse
from app.schemas.screening import ScreeningRunResponse
from app.services import (
    application_service,
    candidate_service,
    hr_candidate_intake_service,
    reapply_service,
)

router = APIRouter(prefix="/candidates", tags=["recruiter-candidates"])


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    payload: CandidateCreateRequest,
    current_user: User = Depends(require_permission("candidate.create")),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    assert current_user.organization_id is not None
    candidate = await candidate_service.create_candidate(
        db, organization_id=current_user.organization_id, payload=payload, actor=current_user
    )
    return CandidateResponse.model_validate(candidate)


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(
    current_user: User = Depends(require_permission("candidate.read")),
    db: AsyncSession = Depends(get_db),
) -> list[CandidateResponse]:
    assert current_user.organization_id is not None
    candidates = await candidate_service.list_candidates(db, current_user.organization_id)
    return [CandidateResponse.model_validate(candidate) for candidate in candidates]


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: uuid.UUID,
    _: User = Depends(require_permission("candidate.read")),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    candidate = await candidate_service.get_candidate(db, candidate_id)
    if candidate is None:
        raise NotFoundError("Candidate not found.")
    return CandidateResponse.model_validate(candidate)


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: uuid.UUID,
    payload: CandidateUpdateRequest,
    current_user: User = Depends(require_permission("candidate.update")),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    candidate = await candidate_service.get_candidate(db, candidate_id)
    if candidate is None:
        raise NotFoundError("Candidate not found.")
    updated = await candidate_service.update_candidate(db, candidate, payload, actor=current_user)
    return CandidateResponse.model_validate(updated)


@router.post("/{candidate_id}/delete", response_model=CandidateResponse)
async def delete_candidate(
    candidate_id: uuid.UUID,
    payload: CandidateDeleteRequest,
    current_user: User = Depends(require_permission("candidate.delete")),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    candidate = await candidate_service.get_candidate(db, candidate_id)
    if candidate is None:
        raise NotFoundError("Candidate not found.")
    deleted = await candidate_service.delete_candidate(
        db, candidate, actor=current_user, reason=payload.reason
    )
    return CandidateResponse.model_validate(deleted)


@router.get("/{candidate_id}/history", response_model=CandidateHistoryResponse)
async def get_candidate_history(
    candidate_id: uuid.UUID,
    _: User = Depends(require_permission("candidate.read")),
    __: User = Depends(require_permission("screening.read")),
    db: AsyncSession = Depends(get_db),
) -> CandidateHistoryResponse:
    """Original application, HR job matches, every AI screening run
    (internal evidence — staff only) and the candidate-journey audit trail."""
    candidate = await candidate_service.get_candidate(db, candidate_id)
    if candidate is None:
        raise NotFoundError("Candidate not found.")
    return await candidate_service.get_candidate_history(db, candidate)


@router.post(
    "/{candidate_id}/job-matches",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def match_candidate_to_job(
    candidate_id: uuid.UUID,
    payload: CandidateJobMatchRequest,
    current_user: User = Depends(require_permission("application.create")),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """HR matches an existing candidate to another job (regardless of the AI
    screening outcome). Creates a new HR_MATCH application on the same
    candidate profile; the original application is untouched."""
    assert current_user.organization_id is not None
    application = await application_service.match_candidate_to_job(
        db,
        organization_id=current_user.organization_id,
        candidate_id=candidate_id,
        job_id=payload.job_id,
        actor=current_user,
        reason=payload.reason,
    )
    return application_response(application)


async def _grant_response(db: AsyncSession, grant: CandidateReapplyGrant) -> ReapplyGrantResponse:
    granted_by = (
        await db.get(User, grant.granted_by_user_id) if grant.granted_by_user_id else None
    )
    response = ReapplyGrantResponse.model_validate(grant)
    response.granted_by_name = granted_by.full_name if granted_by else None
    return response


@router.get("/{candidate_id}/reapply-status", response_model=ReapplyStatusResponse)
async def get_reapply_status(
    candidate_id: uuid.UUID,
    current_user: User = Depends(require_permission("candidate.read")),
    db: AsyncSession = Depends(get_db),
) -> ReapplyStatusResponse:
    """When the candidate may self-apply again, and any open HR grant."""
    assert current_user.organization_id is not None
    candidate = await candidate_service.get_candidate(db, candidate_id)
    if candidate is None or candidate.organization_id != current_user.organization_id:
        raise NotFoundError("Candidate not found.")
    eligibility = await reapply_service.check_eligibility(
        db, organization_id=current_user.organization_id, candidate_id=candidate.id
    )
    return ReapplyStatusResponse(
        candidate_id=candidate.id,
        cooldown_months=get_settings().candidate_reapply_cooldown_months,
        last_self_applied_at=eligibility.last_self_applied_at,
        eligible_from=eligibility.eligible_from,
        can_self_apply_now=eligibility.allowed,
        open_grant=(
            await _grant_response(db, eligibility.grant) if eligibility.grant else None
        ),
    )


@router.post(
    "/{candidate_id}/reapply-grants",
    response_model=ReapplyGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_early_reapply(
    candidate_id: uuid.UUID,
    payload: ReapplyGrantRequest,
    current_user: User = Depends(require_permission("candidate.reapply.grant")),
    db: AsyncSession = Depends(get_db),
) -> ReapplyGrantResponse:
    """HR "Allow Reapply": the candidate may self-apply once more before the
    reapply window ends. The reason is required and audited."""
    assert current_user.organization_id is not None
    grant = await reapply_service.grant_early_reapply(
        db,
        organization_id=current_user.organization_id,
        candidate_id=candidate_id,
        actor=current_user,
        reason=payload.reason,
    )
    return await _grant_response(db, grant)


@router.post(
    "/{candidate_id}/applications",
    response_model=HrApplicationWithResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_application_with_resume(
    candidate_id: uuid.UUID,
    job_id: uuid.UUID = Form(...),
    run_screening: bool = Form(default=True),
    resume: UploadFile = File(...),
    current_user: User = Depends(require_permission("application.create")),
    db: AsyncSession = Depends(get_db),
    storage: ResumeStorage = Depends(get_resume_storage),
) -> HrApplicationWithResumeResponse:
    """HR adds a resume and applying role for a candidate: creates the
    RECRUITER_ADDED application (or fills the resume in on their existing,
    resume-less application for that role) and, by default, runs the same
    AI screening gate as a self-service submission. No candidate OTP."""
    assert current_user.organization_id is not None
    # Read at most one byte past the limit, like the public upload.
    max_bytes = get_settings().max_resume_size_mb * 1024 * 1024
    resume_bytes = await resume.read(max_bytes + 1)
    if len(resume_bytes) > max_bytes:
        raise AppError(
            f"Resume must be smaller than {get_settings().max_resume_size_mb}MB.",
            code="file_too_large",
        )
    result = await hr_candidate_intake_service.add_resume_for_role(
        db,
        storage,
        organization_id=current_user.organization_id,
        candidate_id=candidate_id,
        job_id=job_id,
        actor=current_user,
        resume_filename=resume.filename or "resume",
        resume_content_type=resume.content_type or "application/octet-stream",
        resume_bytes=resume_bytes,
        run_screening=run_screening,
    )
    return HrApplicationWithResumeResponse(
        application=application_response(result.application),
        screening=(
            ScreeningRunResponse.model_validate(result.screening) if result.screening else None
        ),
        attached_to_existing=result.attached_to_existing,
    )

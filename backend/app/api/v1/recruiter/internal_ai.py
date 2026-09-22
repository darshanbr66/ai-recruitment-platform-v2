"""Internal AI ("Recruitment Intelligence") — natural-language questions
about candidates/applications/jobs, and explicit candidate<->job matching,
for authenticated recruiter/admin staff only (`internal_ai.use`). Never
mounted under `/public/*`; never reachable without a valid recruiter JWT and
that permission (CLAUDE.md § 9).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.match_result import MatchResult
from app.models.user import User
from app.schemas.internal_ai import (
    InternalAIQueryRequest,
    InternalAIQueryResponse,
    JobMatchRequest,
    MatchRequest,
    MatchResponse,
)
from app.services import application_service
from app.services.application_service import ApplicationFilters
from app.services.internal_ai import internal_ai_service
from app.services.matching import match_engine

router = APIRouter(prefix="/ai", tags=["recruiter-internal-ai"])


def _to_match_response(run: MatchResult) -> MatchResponse:
    return MatchResponse(
        id=run.id,
        candidate_id=run.candidate_id,
        job_id=run.job_id,
        application_id=run.application_id,
        status=run.status.value,
        provider=run.provider,
        model=run.model,
        overall_match_score=run.overall_match_score,
        confidence=run.confidence,
        matching_skills=run.matching_skills or [],
        missing_skills=run.missing_skills or [],
        matching_experience=run.matching_experience,
        matching_education=run.matching_education,
        matching_location=run.matching_location,
        notice_period_fit=run.notice_period_fit,
        role_alignment=run.role_alignment,
        potential_concerns=run.potential_concerns or [],
        evidence=run.evidence or [],
        explanation=run.explanation,
        scoring_breakdown=run.scoring_breakdown,
        error_message=run.error_message,
        created_at=run.created_at,
    )


@router.post("/query", response_model=InternalAIQueryResponse)
async def query(
    payload: InternalAIQueryRequest,
    current_user: User = Depends(require_permission("internal_ai.use")),
    db: AsyncSession = Depends(get_db),
) -> InternalAIQueryResponse:
    assert current_user.organization_id is not None
    return await internal_ai_service.answer_query(
        db, organization_id=current_user.organization_id, user_id=current_user.id, request=payload
    )


@router.post("/match", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def compute_match(
    payload: MatchRequest,
    current_user: User = Depends(require_permission("internal_ai.use")),
    db: AsyncSession = Depends(get_db),
) -> MatchResponse:
    assert current_user.organization_id is not None
    run = await match_engine.run_match(
        db,
        organization_id=current_user.organization_id,
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        application_id=payload.application_id,
        requested_by_user_id=current_user.id,
    )
    return _to_match_response(run)


@router.get("/match/{candidate_id}/{job_id}", response_model=MatchResponse | None)
async def get_match(
    candidate_id: uuid.UUID,
    job_id: uuid.UUID,
    _: User = Depends(require_permission("internal_ai.use")),
    db: AsyncSession = Depends(get_db),
) -> MatchResponse | None:
    run = await match_engine.get_latest_match(db, candidate_id=candidate_id, job_id=job_id)
    return _to_match_response(run) if run is not None else None


@router.post("/match/job", response_model=list[MatchResponse])
async def compute_job_matches(
    payload: JobMatchRequest,
    current_user: User = Depends(require_permission("internal_ai.use")),
    db: AsyncSession = Depends(get_db),
) -> list[MatchResponse]:
    """Ranks every applicant to `job_id` — the "find candidates suitable for
    this role" / "which candidates match this job" family of questions, as a
    direct action rather than a free-text query."""
    assert current_user.organization_id is not None
    applications = await application_service.list_applications(
        db,
        current_user.organization_id,
        filters=ApplicationFilters(job_id=payload.job_id),
        limit=payload.limit,
    )
    runs = [
        await match_engine.run_match(
            db,
            organization_id=current_user.organization_id,
            candidate_id=application.candidate_id,
            job_id=payload.job_id,
            application_id=application.id,
            requested_by_user_id=current_user.id,
        )
        for application in applications
    ]
    runs.sort(key=lambda r: r.overall_match_score or 0, reverse=True)
    return [_to_match_response(run) for run in runs]

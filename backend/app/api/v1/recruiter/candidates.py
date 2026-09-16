"""Recruiter-facing Candidate CRUD. `organization_id` is always taken from
the authenticated caller, never from the request (docs/security.md § 2)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.candidate import CandidateCreateRequest, CandidateResponse, CandidateUpdateRequest
from app.services import candidate_service

router = APIRouter(prefix="/candidates", tags=["recruiter-candidates"])


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    payload: CandidateCreateRequest,
    current_user: User = Depends(require_permission("candidate.create")),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    assert current_user.organization_id is not None
    candidate = await candidate_service.create_candidate(
        db, organization_id=current_user.organization_id, payload=payload
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
    _: User = Depends(require_permission("candidate.update")),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    candidate = await candidate_service.get_candidate(db, candidate_id)
    if candidate is None:
        raise NotFoundError("Candidate not found.")
    updated = await candidate_service.update_candidate(db, candidate, payload)
    return CandidateResponse.model_validate(updated)

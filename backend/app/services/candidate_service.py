import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreateRequest, CandidateUpdateRequest


async def create_candidate(
    db: AsyncSession, *, organization_id: uuid.UUID, payload: CandidateCreateRequest
) -> Candidate:
    candidate = Candidate(
        organization_id=organization_id,
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
        location=payload.location,
        current_title=payload.current_title,
        years_experience=payload.years_experience,
        source=payload.source,
    )
    db.add(candidate)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "A candidate with this email already exists in this organization."
        ) from exc
    return candidate


async def list_candidates(db: AsyncSession, organization_id: uuid.UUID) -> list[Candidate]:
    result = await db.execute(
        select(Candidate)
        .where(Candidate.organization_id == organization_id)
        .order_by(Candidate.created_at.desc())
    )
    return list(result.scalars().all())


async def get_candidate(db: AsyncSession, candidate_id: uuid.UUID) -> Candidate | None:
    """RLS scopes this to the caller's own tenant — a cross-tenant id
    returns None exactly as if the row didn't exist (docs/security.md § 2)."""
    return await db.get(Candidate, candidate_id)


async def update_candidate(
    db: AsyncSession, candidate: Candidate, payload: CandidateUpdateRequest
) -> Candidate:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(candidate, field, value)
    await db.flush()
    return candidate

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.candidate import Candidate
from app.models.user import User
from app.schemas.candidate import CandidateCreateRequest, CandidateUpdateRequest
from app.services import activity_service


async def create_candidate(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    payload: CandidateCreateRequest,
    actor: User | None = None,
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

    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="CANDIDATE_CREATED",
        entity_type="candidate",
        entity_id=candidate.id,
        entity_label=f"{candidate.full_name} ({candidate.email})",
        description=f"Candidate {candidate.full_name} was added.",
    )
    return candidate


async def get_candidate_by_email(
    db: AsyncSession, *, organization_id: uuid.UUID, email: str
) -> Candidate | None:
    result = await db.execute(
        select(Candidate).where(
            Candidate.organization_id == organization_id, Candidate.email == email
        )
    )
    return result.scalar_one_or_none()


async def list_candidates(db: AsyncSession, organization_id: uuid.UUID) -> list[Candidate]:
    result = await db.execute(
        select(Candidate)
        .where(Candidate.organization_id == organization_id, Candidate.deleted_at.is_(None))
        .order_by(Candidate.created_at.desc())
    )
    return list(result.scalars().all())


async def get_candidate(db: AsyncSession, candidate_id: uuid.UUID) -> Candidate | None:
    """RLS scopes this to the caller's own tenant — a cross-tenant id
    returns None exactly as if the row didn't exist (docs/security.md § 2)."""
    return await db.get(Candidate, candidate_id)


async def update_candidate(
    db: AsyncSession, candidate: Candidate, payload: CandidateUpdateRequest, *, actor: User
) -> Candidate:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return candidate

    for field, value in updates.items():
        setattr(candidate, field, value)
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=candidate.organization_id,
        actor=actor,
        action="CANDIDATE_UPDATED",
        entity_type="candidate",
        entity_id=candidate.id,
        entity_label=f"{candidate.full_name} ({candidate.email})",
        description=f"Candidate {candidate.full_name} was updated.",
    )
    return candidate


async def delete_candidate(
    db: AsyncSession, candidate: Candidate, *, actor: User, reason: str
) -> Candidate:
    """Soft-deletes: keeps the row (and every Application/Note/
    AssessmentInvitation pointing at it) but removes it from
    `list_candidates` and records an Activity, per CLAUDE.md's "never
    silently destroy historical recruitment records" rule."""
    if candidate.deleted_at is not None:
        raise ConflictError("This candidate has already been deleted.")

    candidate.deleted_at = datetime.now(UTC)
    candidate.deleted_by_user_id = actor.id
    candidate.deletion_reason = reason
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=candidate.organization_id,
        actor=actor,
        action="CANDIDATE_DELETED",
        entity_type="candidate",
        entity_id=candidate.id,
        entity_label=f"{candidate.full_name} ({candidate.email})",
        description=f"Candidate {candidate.full_name} was deleted.",
        reason=reason,
    )
    return candidate

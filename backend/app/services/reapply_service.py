"""The self-service reapply rule: a candidate may self-apply again once
`CANDIDATE_REAPPLY_COOLDOWN_MONTHS` (default 3) calendar months have passed
since their previous *self-service* application — or earlier, once, if an
HR user granted it (CandidateReapplyGrant).

Only self-service applications count (`Application.is_self_service`): a
candidate HR created, imported or matched to jobs has no self-apply history
and is never locked out by it. Every application counts, whatever its
status (an AI_SCREENED_OUT one included) and even if archived — the window
is about when the person last applied, not how it went.

Callers pass the organization explicitly and every query filters on it, on
top of RLS (the two-layer tenant rule, docs/security.md § 2).
"""

import calendar
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.candidate_reapply_grant import CandidateReapplyGrant
from app.models.user import User
from app.services import activity_service


def add_months(moment: datetime, months: int) -> datetime:
    """Same day-of-month `months` later, clamped to the last day of a
    shorter month (30 Nov + 3 months = 28/29 Feb)."""
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


@dataclass(frozen=True)
class ReapplyEligibility:
    """`last_self_applied_at` is None for a candidate with no self-service
    history. `eligible_from` is when the window opens (None = no history).
    `allowed` is the answer; `grant` is the open HR grant, if any."""

    allowed: bool
    last_self_applied_at: datetime | None
    eligible_from: datetime | None
    grant: CandidateReapplyGrant | None


async def last_self_application_at(
    db: AsyncSession, *, organization_id: uuid.UUID, candidate_id: uuid.UUID
) -> datetime | None:
    return await db.scalar(
        select(func.max(Application.applied_at)).where(
            Application.organization_id == organization_id,
            Application.candidate_id == candidate_id,
            Application.is_self_service.is_(True),
        )
    )


async def get_open_grant(
    db: AsyncSession, *, organization_id: uuid.UUID, candidate_id: uuid.UUID
) -> CandidateReapplyGrant | None:
    return await db.scalar(
        select(CandidateReapplyGrant).where(
            CandidateReapplyGrant.organization_id == organization_id,
            CandidateReapplyGrant.candidate_id == candidate_id,
            CandidateReapplyGrant.used_at.is_(None),
        )
    )


async def check_eligibility(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    candidate_id: uuid.UUID,
    now: datetime | None = None,
) -> ReapplyEligibility:
    now = now or datetime.now(UTC)
    last = await last_self_application_at(
        db, organization_id=organization_id, candidate_id=candidate_id
    )
    grant = await get_open_grant(db, organization_id=organization_id, candidate_id=candidate_id)
    if last is None:
        return ReapplyEligibility(
            allowed=True, last_self_applied_at=None, eligible_from=None, grant=grant
        )
    eligible_from = add_months(last, get_settings().candidate_reapply_cooldown_months)
    return ReapplyEligibility(
        allowed=now >= eligible_from or grant is not None,
        last_self_applied_at=last,
        eligible_from=eligible_from,
        grant=grant,
    )


def _format_day(value: date) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


def reapply_locked_error(
    eligibility: ReapplyEligibility, contact_email: str | None
) -> ConflictError:
    """Only ever raised to a caller who has just proven they own the
    candidate's email address, so naming their own dates is safe."""
    assert eligibility.last_self_applied_at is not None
    assert eligibility.eligible_from is not None
    months = get_settings().candidate_reapply_cooldown_months
    contact = (
        f" If your circumstances have changed, you can contact our recruitment team at "
        f"{contact_email}."
        if contact_email
        else ""
    )
    return ConflictError(
        f"You applied on {_format_day(eligibility.last_self_applied_at.date())}. Candidates can "
        f"apply again {months} months after their previous application, so you can apply again "
        f"from {_format_day(eligibility.eligible_from.date())}. Our recruitment team continues "
        f"to consider your profile for other suitable roles in the meantime.{contact}",
        code="reapply_locked",
        data={
            "last_applied_at": eligibility.last_self_applied_at.isoformat(),
            "eligible_from": eligibility.eligible_from.isoformat(),
        },
    )


async def grant_early_reapply(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    candidate_id: uuid.UUID,
    actor: User,
    reason: str,
) -> CandidateReapplyGrant:
    """HR allowing the candidate one self-application before the window
    opens. Refused when there is nothing to lift (no self-service history,
    or the window has already passed) or a grant is already open, so the
    audit trail only ever records grants that changed something."""
    candidate = await db.get(Candidate, candidate_id)
    if (
        candidate is None
        or candidate.deleted_at is not None
        or candidate.organization_id != organization_id
    ):
        raise NotFoundError("Candidate not found.")

    eligibility = await check_eligibility(
        db, organization_id=organization_id, candidate_id=candidate_id
    )
    if eligibility.grant is not None:
        raise ConflictError("This candidate has already been allowed to reapply.")
    if eligibility.allowed:
        raise ConflictError(
            "This candidate can already apply — there is no reapply restriction to lift."
        )

    grant = CandidateReapplyGrant(
        organization_id=organization_id,
        candidate_id=candidate_id,
        granted_by_user_id=actor.id,
        reason=reason,
    )
    db.add(grant)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:  # a concurrent grant won the race
        raise ConflictError("This candidate has already been allowed to reapply.") from exc

    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="CANDIDATE_REAPPLY_GRANTED",
        entity_type="candidate",
        entity_id=candidate.id,
        entity_label=f"{candidate.full_name} ({candidate.email})",
        description=(
            f"{candidate.full_name} was allowed to apply again before the reapply window ends "
            "(single use)."
        ),
        reason=reason,
    )
    return grant


async def consume_open_grant(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    candidate: Candidate,
    application_id: uuid.UUID,
) -> None:
    """Called for every new self-service application: an open grant is
    spent by the candidate's next self-application whether or not it was
    needed, so it can never linger and allow a second early one later."""
    grant = await get_open_grant(db, organization_id=organization_id, candidate_id=candidate.id)
    if grant is None:
        return
    grant.used_at = datetime.now(UTC)
    grant.used_by_application_id = application_id
    await db.flush()
    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=None,
        action="CANDIDATE_REAPPLY_GRANT_USED",
        entity_type="candidate",
        entity_id=candidate.id,
        entity_label=f"{candidate.full_name} ({candidate.email})",
        description=f"{candidate.full_name} used the early reapply HR had granted.",
    )

"""Application status transition rules — see docs/recruitment-workflow.md § 2.

Per CLAUDE.md § 2 ("Workflow state != ad hoc strings"), the legal-transition
table lives in exactly one place. Every status change on an `Application`
must go through `transition()`, which validates the move, writes the new
status, and appends an `ApplicationStatusHistory` row — no call site can put
an application into an invalid state or skip the history write.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.application import Application, ApplicationStatus, ApplicationStatusHistory
from app.models.user import User
from app.services import activity_service

TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.APPLIED: frozenset(
        {ApplicationStatus.UNDER_REVIEW, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.UNDER_REVIEW: frozenset(
        {ApplicationStatus.SCREENING, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.SCREENING: frozenset(
        {
            ApplicationStatus.ASSESSMENT_INVITED,
            ApplicationStatus.SHORTLISTED,
            ApplicationStatus.REJECTED,
        }
    ),
    ApplicationStatus.ASSESSMENT_INVITED: frozenset(
        {
            ApplicationStatus.ASSESSMENT_STARTED,
            ApplicationStatus.REJECTED,
        }
    ),
    ApplicationStatus.ASSESSMENT_STARTED: frozenset(
        {ApplicationStatus.ASSESSMENT_COMPLETED, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.ASSESSMENT_COMPLETED: frozenset(
        {
            ApplicationStatus.SHORTLISTED,
            ApplicationStatus.REJECTED,
            # A retest re-invites a candidate who already completed an
            # attempt (app/services/assessment_service.py::create_retest) —
            # the one explicit, audited exception to "no code path
            # transitions out of ASSESSMENT_COMPLETED without it".
            ApplicationStatus.ASSESSMENT_INVITED,
        }
    ),
    ApplicationStatus.SHORTLISTED: frozenset(
        {ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.INTERVIEW: frozenset(
        {ApplicationStatus.SELECTED, ApplicationStatus.REJECTED}
    ),
    # SELECTED -> HIRED is the one non-terminal edge left: a recruiter marks
    # a selected candidate as actually joined. REJECTED/HIRED are the only
    # true terminal states (a mis-rejection is corrected by an explicit,
    # audited recruiter override feature if/when that's built, not by
    # silently un-terminal-izing here).
    ApplicationStatus.SELECTED: frozenset({ApplicationStatus.HIRED}),
    ApplicationStatus.REJECTED: frozenset(),
    ApplicationStatus.HIRED: frozenset(),
}


def allowed_next_statuses(current: ApplicationStatus) -> frozenset[ApplicationStatus]:
    return TRANSITIONS[current]


async def transition(
    db: AsyncSession,
    application: Application,
    *,
    to_status: ApplicationStatus,
    actor_user_id: uuid.UUID | None,
    reason: str | None = None,
) -> Application:
    from_status = application.status
    if to_status not in TRANSITIONS[from_status]:
        raise ConflictError(
            f"Cannot move an application from {from_status.value} to {to_status.value}."
        )

    application.status = to_status
    db.add(
        ApplicationStatusHistory(
            application_id=application.id,
            from_status=from_status,
            to_status=to_status,
            changed_by_user_id=actor_user_id,
            reason=reason,
        )
    )
    await db.flush()

    # Centralized here (not at each call site — screening, recruiter review,
    # retest, campus auto-advance) so every status change is audited exactly
    # once, in exactly one place (QA § 5: "avoid copy-pasting audit logic").
    actor = await db.get(User, actor_user_id) if actor_user_id is not None else None
    await activity_service.record_activity(
        db,
        organization_id=application.organization_id,
        actor=actor,
        action="APPLICATION_STATUS_CHANGED",
        entity_type="application",
        entity_id=application.id,
        entity_label=f"Application #{str(application.id)[:8]}",
        description=f"Status changed from {from_status.value} to {to_status.value}.",
        reason=reason,
    )
    return application


async def record_initial_status(
    db: AsyncSession, application: Application, *, actor_user_id: uuid.UUID | None
) -> None:
    """Called once, right after an Application row is inserted. This is not
    a `transition()` — there is no prior state to validate against, matching
    the schema's `from_status NULL` for the very first history row (see
    docs/database.md § 3.5).
    """
    db.add(
        ApplicationStatusHistory(
            application_id=application.id,
            from_status=None,
            to_status=application.status,
            changed_by_user_id=actor_user_id,
        )
    )
    await db.flush()

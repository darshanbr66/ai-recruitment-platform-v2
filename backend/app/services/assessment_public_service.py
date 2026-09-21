"""Candidate-facing assessment access by opaque token — no login required
(docs/assessment.md § 4: "possession of the token is the authorization").
Every entry point here resolves the invitation's tenant via `rls_bypass`
(the token is looked up before any org is known — the same bootstrap case
documented in app/db/rls.py::rls_bypass), then sets tenant context so the
rest of the operation runs under ordinary RLS.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.security import hash_opaque_token
from app.db.rls import rls_bypass, set_tenant_context
from app.models.application import ApplicationStatus
from app.models.assessment import (
    Assessment,
    AssessmentInvitation,
    AssessmentMonitoringEvent,
    AssessmentResult,
    CandidateAnswer,
    InvitationStatus,
    Question,
)
from app.models.notification import NotificationType
from app.models.organization import Organization
from app.schemas.public_assessment import MonitoringEventCreate
from app.services import activity_service, application_service, in_app_notification_service

_INVALID_MESSAGE = "This invitation link is no longer valid."


async def _resolve_invitation(db: AsyncSession, token: str) -> AssessmentInvitation:
    token_hash = hash_opaque_token(token)
    async with rls_bypass(db):
        result = await db.execute(
            select(AssessmentInvitation)
            .where(AssessmentInvitation.token_hash == token_hash)
            .options(
                joinedload(AssessmentInvitation.assessment)
                .selectinload(Assessment.questions)
                .selectinload(Question.options),
                joinedload(AssessmentInvitation.result),
            )
        )
        invitation = result.unique().scalar_one_or_none()

    if invitation is None:
        raise NotFoundError(_INVALID_MESSAGE)

    await set_tenant_context(db, invitation.organization_id)

    if invitation.status == InvitationStatus.CANCELLED:
        raise NotFoundError(_INVALID_MESSAGE)
    if invitation.status not in (InvitationStatus.SUBMITTED,) and invitation.expires_at < datetime.now(UTC):
        invitation.status = InvitationStatus.EXPIRED
        await db.flush()
    if invitation.status == InvitationStatus.EXPIRED:
        raise NotFoundError(_INVALID_MESSAGE)

    return invitation


async def get_invitation(db: AsyncSession, token: str) -> AssessmentInvitation:
    return await _resolve_invitation(db, token)


async def start_attempt(db: AsyncSession, token: str) -> AssessmentInvitation:
    invitation = await _resolve_invitation(db, token)
    if invitation.status == InvitationStatus.SUBMITTED:
        raise AppError("This assessment has already been submitted.", code="already_submitted")

    if invitation.status == InvitationStatus.SENT:
        invitation.status = InvitationStatus.STARTED
        invitation.started_at = datetime.now(UTC)
        await db.flush()

        application = await application_service.get_application(db, invitation.application_id)
        if application is not None:
            await application_service.change_status(
                db, application, to_status=ApplicationStatus.ASSESSMENT_STARTED, actor_user_id=None
            )
            # Inside the SENT -> STARTED transition on purpose: a reload,
            # StrictMode double-call or repeat request finds STARTED and never
            # reaches this line (and the notification's unique index backs it
            # up under a race).
            await in_app_notification_service.notify_inviter_of_assessment_event(
                db,
                invitation=invitation,
                notification_type=NotificationType.ASSESSMENT_STARTED,
                candidate_name=application.candidate.full_name,
                assessment_title=invitation.assessment.title,
            )

    return invitation


async def submit_attempt(
    db: AsyncSession, token: str, answers: list[tuple[uuid.UUID, list[uuid.UUID]]]
) -> AssessmentResult:
    invitation = await _resolve_invitation(db, token)
    if invitation.status == InvitationStatus.SUBMITTED:
        raise AppError("This assessment has already been submitted.", code="already_submitted")

    assessment = invitation.assessment
    questions_by_id = {question.id: question for question in assessment.questions}

    score = 0
    max_score = 0
    for question in assessment.questions:
        max_score += question.points

    for question_id, selected_option_ids in answers:
        question = questions_by_id.get(question_id)
        if question is None:
            continue
        db.add(
            CandidateAnswer(
                invitation_id=invitation.id,
                question_id=question_id,
                selected_option_ids=[str(option_id) for option_id in selected_option_ids],
            )
        )
        correct_ids = {option.id for option in question.options if option.is_correct}
        if set(selected_option_ids) == correct_ids:
            score += question.points

    percentage = round((score / max_score) * 100) if max_score > 0 else 0
    passed = percentage >= assessment.pass_score

    result = AssessmentResult(
        invitation_id=invitation.id,
        score=score,
        max_score=max_score,
        percentage=percentage,
        passed=passed,
        evaluated_at=datetime.now(UTC),
    )
    db.add(result)

    invitation.status = InvitationStatus.SUBMITTED
    invitation.submitted_at = datetime.now(UTC)
    await db.flush()

    application = await application_service.get_application(db, invitation.application_id)
    if application is not None:
        await application_service.change_status(
            db, application, to_status=ApplicationStatus.ASSESSMENT_COMPLETED, actor_user_id=None
        )
        await activity_service.record_activity(
            db,
            organization_id=invitation.organization_id,
            actor=None,
            action="ASSESSMENT_COMPLETED",
            entity_type="application",
            entity_id=application.id,
            entity_label=f"{application.candidate.full_name} — {assessment.title}",
            description=(
                f"{application.candidate.full_name} completed \"{assessment.title}\" "
                f"(attempt {invitation.attempt_number}): {percentage}% — {'passed' if passed else 'failed'}."
            ),
        )
        # A second submit is rejected above (`already_submitted`), so this
        # runs once per invitation; the unique index covers a concurrent race.
        await in_app_notification_service.notify_inviter_of_assessment_event(
            db,
            invitation=invitation,
            notification_type=NotificationType.ASSESSMENT_SUBMITTED,
            candidate_name=application.candidate.full_name,
            assessment_title=assessment.title,
        )

    return result


async def record_monitoring_events(
    db: AsyncSession, token: str, events: list[MonitoringEventCreate]
) -> None:
    """Persists observed browser-monitoring events for the candidate's
    current attempt (SIGVITAS platform overhaul § 6-7) — only accepted
    while the attempt is actually in progress (STARTED), so the event
    stream stays meaningful (no events before consent/start, none after
    submission)."""
    invitation = await _resolve_invitation(db, token)
    if invitation.status != InvitationStatus.STARTED:
        raise ConflictError("Monitoring events can only be recorded during an active attempt.")

    for event in events:
        db.add(
            AssessmentMonitoringEvent(
                invitation_id=invitation.id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                duration_ms=event.duration_ms,
                event_metadata=event.metadata,
            )
        )
    await db.flush()


async def get_organization_name(db: AsyncSession, organization_id: uuid.UUID) -> str:
    organization = await db.get(Organization, organization_id)
    return organization.name if organization else ""

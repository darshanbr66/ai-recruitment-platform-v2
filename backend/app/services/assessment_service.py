import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_opaque_token, hash_opaque_token
from app.models.application import ApplicationStatus
from app.models.assessment import (
    Assessment,
    AssessmentInvitation,
    InvitationStatus,
    Question,
    QuestionOption,
)
from app.models.organization import Organization
from app.schemas.assessment import AssessmentCreateRequest
from app.services import application_service, notification_service

_INVITATION_EXPIRY_DAYS = 7


async def create_assessment(
    db: AsyncSession, *, organization_id: uuid.UUID, created_by: uuid.UUID, payload: AssessmentCreateRequest
) -> Assessment:
    assessment = Assessment(
        organization_id=organization_id,
        title=payload.title,
        instructions=payload.instructions,
        duration_minutes=payload.duration_minutes,
        pass_score=payload.pass_score,
        created_by=created_by,
    )
    db.add(assessment)
    await db.flush()

    for order_index, question_payload in enumerate(payload.questions):
        question = Question(
            assessment_id=assessment.id,
            prompt=question_payload.prompt,
            type=question_payload.type,
            points=question_payload.points,
            order_index=order_index,
        )
        db.add(question)
        await db.flush()

        for option_order, option_payload in enumerate(question_payload.options):
            db.add(
                QuestionOption(
                    question_id=question.id,
                    label=option_payload.label,
                    is_correct=option_payload.is_correct,
                    order_index=option_order,
                )
            )
    await db.flush()

    reloaded = await get_assessment(db, assessment.id)
    assert reloaded is not None
    return reloaded


async def list_assessments(db: AsyncSession, organization_id: uuid.UUID) -> list[Assessment]:
    result = await db.execute(
        select(Assessment)
        .where(Assessment.organization_id == organization_id)
        .options(selectinload(Assessment.questions))
        .order_by(Assessment.created_at.desc())
    )
    return list(result.unique().scalars().all())


async def get_assessment(db: AsyncSession, assessment_id: uuid.UUID) -> Assessment | None:
    result = await db.execute(
        select(Assessment)
        .where(Assessment.id == assessment_id)
        .options(selectinload(Assessment.questions).selectinload(Question.options))
    )
    return result.unique().scalar_one_or_none()


async def invite_candidate(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    assessment_id: uuid.UUID,
    application_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
) -> tuple[AssessmentInvitation, str]:
    assessment = await get_assessment(db, assessment_id)
    if assessment is None:
        raise NotFoundError("Assessment not found.")

    application = await application_service.get_application(db, application_id)
    if application is None:
        raise NotFoundError("Application not found.")

    existing = await db.scalar(
        select(AssessmentInvitation).where(AssessmentInvitation.application_id == application_id)
    )

    raw_token = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(days=_INVITATION_EXPIRY_DAYS)

    if existing is not None:
        # Resend: reuse the row, regenerate the token (docs/campus-hiring.md § 3).
        existing.assessment_id = assessment_id
        existing.token_hash = hash_opaque_token(raw_token)
        existing.status = InvitationStatus.SENT
        existing.expires_at = expires_at
        existing.started_at = None
        existing.submitted_at = None
        existing.invited_by_user_id = invited_by_user_id
        invitation = existing
    else:
        invitation = AssessmentInvitation(
            organization_id=organization_id,
            assessment_id=assessment_id,
            application_id=application_id,
            invited_by_user_id=invited_by_user_id,
            token_hash=hash_opaque_token(raw_token),
            status=InvitationStatus.SENT,
            expires_at=expires_at,
        )
        db.add(invitation)

    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("This application already has an assessment invitation.") from exc

    await application_service.change_status(
        db, application, to_status=ApplicationStatus.ASSESSMENT_INVITED, actor_user_id=invited_by_user_id
    )

    organization = await db.get(Organization, organization_id)
    if organization is not None:
        base_url = "http://localhost:5173"  # candidate-facing app origin
        await notification_service.send_assessment_invitation(
            to=application.candidate.email,
            candidate_name=application.candidate.full_name,
            job_title=application.job.title,
            organization_name=organization.name,
            assessment_title=assessment.title,
            invitation_link=f"{base_url}/assessment/{raw_token}",
            duration_minutes=assessment.duration_minutes,
        )

    reloaded = await get_invitation_for_application(db, application_id)
    assert reloaded is not None
    return reloaded, raw_token


async def get_invitation_for_application(
    db: AsyncSession, application_id: uuid.UUID
) -> AssessmentInvitation | None:
    result = await db.execute(
        select(AssessmentInvitation)
        .where(AssessmentInvitation.application_id == application_id)
        .options(joinedload(AssessmentInvitation.assessment), joinedload(AssessmentInvitation.result))
    )
    return result.unique().scalar_one_or_none()

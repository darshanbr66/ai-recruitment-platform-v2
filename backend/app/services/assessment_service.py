import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_opaque_token, hash_opaque_token
from app.integrations.documents.question_import import parse_questions as _parse_questions
from app.models.application import ApplicationStatus
from app.models.assessment import (
    Assessment,
    AssessmentInvitation,
    InvitationStatus,
    Question,
    QuestionOption,
)
from app.models.organization import Organization
from app.models.user import User
from app.schemas.assessment import (
    AssessmentCreateRequest,
    ParsedQuestionsResponse,
    QuestionCreate,
    RetestAssessmentChoice,
)
from app.schemas.assessment import QuestionOptionCreate as QuestionOptionCreateSchema
from app.services import activity_service, application_service, notification_service

_INVITATION_EXPIRY_DAYS = 7


def parse_import_file(*, content: bytes, filename: str) -> ParsedQuestionsResponse:
    """Extracts candidate questions from an uploaded PDF/DOCX/XLSX/CSV for
    the "Import Questions" preview step — never persists anything (see
    app/integrations/documents/question_import.py for the parsing rules).
    """
    result = _parse_questions(content=content, filename=filename)
    return ParsedQuestionsResponse(
        questions=[
            QuestionCreate(
                prompt=q.prompt,
                type=q.type,
                points=q.points,
                options=[
                    QuestionOptionCreateSchema(label=o.label, is_correct=o.is_correct)
                    for o in q.options
                ],
            )
            for q in result.questions
        ],
        warnings=result.warnings,
    )


async def create_assessment(
    db: AsyncSession, *, organization_id: uuid.UUID, created_by: uuid.UUID, payload: AssessmentCreateRequest,
    actor: User | None = None,
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

    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="ASSESSMENT_CREATED",
        entity_type="assessment",
        entity_id=assessment.id,
        entity_label=assessment.title,
        description=f"Assessment \"{assessment.title}\" was created with {len(payload.questions)} question(s).",
    )

    reloaded = await get_assessment(db, assessment.id)
    assert reloaded is not None
    return reloaded


async def list_assessments(db: AsyncSession, organization_id: uuid.UUID) -> list[Assessment]:
    result = await db.execute(
        select(Assessment)
        .where(Assessment.organization_id == organization_id, Assessment.deleted_at.is_(None))
        .options(selectinload(Assessment.questions))
        .order_by(Assessment.created_at.desc())
    )
    return list(result.unique().scalars().all())


async def delete_assessment(db: AsyncSession, assessment: Assessment, *, actor: User, reason: str) -> Assessment:
    """Soft-deletes/archives: keeps the row (and every AssessmentInvitation/
    AssessmentResult that used it) but removes it from `list_assessments`
    and the invite/retest pickers, and records an Activity."""
    if assessment.deleted_at is not None:
        raise ConflictError("This assessment has already been deleted.")

    # Local import: avoids a cross-domain top-level dependency between the
    # assessment and campus-drive service modules.
    from app.models.campus_drive import CampusDrive

    dependent_drive = await db.scalar(
        select(CampusDrive).where(
            CampusDrive.default_assessment_id == assessment.id,
            CampusDrive.deleted_at.is_(None),
        )
    )
    if dependent_drive is not None:
        raise ConflictError(
            f"This assessment is set as the default for campus drive \"{dependent_drive.name}\". "
            "Change that drive's default assessment before deleting this one."
        )

    assessment.deleted_at = datetime.now(UTC)
    assessment.deleted_by_user_id = actor.id
    assessment.deletion_reason = reason
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=assessment.organization_id,
        actor=actor,
        action="ASSESSMENT_DELETED",
        entity_type="assessment",
        entity_id=assessment.id,
        entity_label=assessment.title,
        description=f"Assessment \"{assessment.title}\" was deleted.",
        reason=reason,
    )
    return assessment


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
    if assessment is None or assessment.deleted_at is not None:
        raise NotFoundError("Assessment not found.")

    application = await application_service.get_application(db, application_id)
    if application is None:
        raise NotFoundError("Application not found.")

    existing = await db.scalar(
        select(AssessmentInvitation)
        .where(AssessmentInvitation.application_id == application_id)
        .order_by(AssessmentInvitation.attempt_number.desc())
        .limit(1)
    )

    raw_token = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(days=_INVITATION_EXPIRY_DAYS)

    if existing is not None:
        # Resend: reuse the row, regenerate the token (docs/campus-hiring.md § 3).
        # Only legal pre-submission — a submitted attempt goes through
        # `create_retest` instead, which adds a new row rather than
        # mutating this one (the application_workflow gate on this
        # function's own SCREENING-only precondition already prevents
        # invite_candidate from running again post-submission).
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
            attempt_number=1,
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

    invited_by = await db.get(User, invited_by_user_id)
    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=invited_by,
        action="ASSESSMENT_INVITATION_CREATED",
        entity_type="application",
        entity_id=application_id,
        entity_label=f"{application.candidate.full_name} — {assessment.title}",
        description=f"{application.candidate.full_name} was invited to take \"{assessment.title}\".",
    )

    reloaded = await get_invitation_for_application(db, application_id)
    assert reloaded is not None
    return reloaded, raw_token


async def get_invitation_for_application(
    db: AsyncSession, application_id: uuid.UUID
) -> AssessmentInvitation | None:
    """The most recent attempt (highest `attempt_number`) — the one
    candidates currently interact with and the one shown by default. Use
    `list_attempts_for_application` for full retest history."""
    result = await db.execute(
        select(AssessmentInvitation)
        .where(AssessmentInvitation.application_id == application_id)
        .options(joinedload(AssessmentInvitation.assessment), joinedload(AssessmentInvitation.result))
        .order_by(AssessmentInvitation.attempt_number.desc())
        .limit(1)
    )
    return result.unique().scalar_one_or_none()


async def list_attempts_for_application(
    db: AsyncSession, application_id: uuid.UUID
) -> list[AssessmentInvitation]:
    result = await db.execute(
        select(AssessmentInvitation)
        .where(AssessmentInvitation.application_id == application_id)
        .options(joinedload(AssessmentInvitation.assessment), joinedload(AssessmentInvitation.result))
        .order_by(AssessmentInvitation.attempt_number.asc())
    )
    return list(result.unique().scalars().all())


async def create_retest(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    application_id: uuid.UUID,
    authorized_by: User,
    reason: str,
    assessment_choice: RetestAssessmentChoice = RetestAssessmentChoice.SAME,
    assessment_id: uuid.UUID | None = None,
    new_assessment: AssessmentCreateRequest | None = None,
) -> tuple[AssessmentInvitation, str]:
    """Gives a candidate another attempt — at the *same* assessment
    (default), an *existing* one, or a brand-new one created inline (QA § 6)
    — the previous attempt's row (and its linked AssessmentResult/
    CandidateAnswers) is never touched, only a new row is added (CLAUDE.md
    § 3: never silently erase assessment history)."""
    latest = await get_invitation_for_application(db, application_id)
    if latest is None:
        raise NotFoundError("This application has no assessment attempt to retest.")
    if latest.status != InvitationStatus.SUBMITTED:
        raise ConflictError(
            "A retest can only be given after the current attempt has been submitted."
        )

    application = await application_service.get_application(db, application_id)
    if application is None:
        raise NotFoundError("Application not found.")

    if assessment_choice == RetestAssessmentChoice.EXISTING:
        assert assessment_id is not None
        chosen_assessment = await get_assessment(db, assessment_id)
        if chosen_assessment is None or chosen_assessment.deleted_at is not None:
            raise NotFoundError("Assessment not found.")
    elif assessment_choice == RetestAssessmentChoice.NEW:
        assert new_assessment is not None
        chosen_assessment = await create_assessment(
            db,
            organization_id=organization_id,
            created_by=authorized_by.id,
            payload=new_assessment,
            actor=authorized_by,
        )
    else:
        chosen_assessment = latest.assessment

    raw_token = generate_opaque_token()
    invitation = AssessmentInvitation(
        organization_id=organization_id,
        assessment_id=chosen_assessment.id,
        application_id=application_id,
        invited_by_user_id=authorized_by.id,
        token_hash=hash_opaque_token(raw_token),
        status=InvitationStatus.SENT,
        expires_at=datetime.now(UTC) + timedelta(days=_INVITATION_EXPIRY_DAYS),
        attempt_number=latest.attempt_number + 1,
        retest_reason=reason,
    )
    db.add(invitation)
    await db.flush()

    await application_service.change_status(
        db, application, to_status=ApplicationStatus.ASSESSMENT_INVITED, actor_user_id=authorized_by.id
    )

    choice_label = (
        "the same" if assessment_choice == RetestAssessmentChoice.SAME
        else assessment_choice.value.lower()
    )
    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=authorized_by,
        action="ASSESSMENT_RETEST_CREATED",
        entity_type="application",
        entity_id=application_id,
        entity_label=(
            f"{application.candidate.full_name} — {chosen_assessment.title} "
            f"(attempt {invitation.attempt_number})"
        ),
        description=(
            f"Retest #{invitation.attempt_number - 1} authorized for "
            f"{application.candidate.full_name} using {choice_label} assessment "
            f"(\"{chosen_assessment.title}\")."
        ),
        reason=reason,
    )

    organization = await db.get(Organization, organization_id)
    if organization is not None:
        base_url = "http://localhost:5173"
        await notification_service.send_assessment_invitation(
            to=application.candidate.email,
            candidate_name=application.candidate.full_name,
            job_title=application.job.title,
            organization_name=organization.name,
            assessment_title=chosen_assessment.title,
            invitation_link=f"{base_url}/assessment/{raw_token}",
            duration_minutes=chosen_assessment.duration_minutes,
        )

    reloaded = await get_invitation_for_application(db, application_id)
    assert reloaded is not None
    return reloaded, raw_token

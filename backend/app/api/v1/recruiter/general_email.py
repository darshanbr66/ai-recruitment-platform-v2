"""General (non-application) email: an authorized recruiter/admin composes,
previews and sends a professional templated email to addresses they type.

This is deliberately not a mail client: it always sends from the configured
platform SMTP address (Reply-To = the sender), reuses the same templates and
HTML layout as application emails, and every send is audited. The SMTP
configuration is never read from, or returned to, the client.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.email import (
    EmailComposeRequest,
    EmailComposeResponse,
    GeneralEmailDraftRequest,
    GeneralEmailPreviewResponse,
    GeneralEmailSendResponse,
)
from app.services import email_composer

router = APIRouter(prefix="/email", tags=["recruiter-general-email"])


@router.post("/compose", response_model=EmailComposeResponse)
async def compose_general_email(
    payload: EmailComposeRequest,
    current_user: User = Depends(require_permission("application.email.send")),
    db: AsyncSession = Depends(get_db),
) -> EmailComposeResponse:
    """Loads a template for a general email: company and recruiter details are
    filled in; the recipient name and role come from `variables`. Nothing is
    sent."""
    composed = await email_composer.compose_general_email(db, actor=current_user, request=payload)
    return EmailComposeResponse(
        template_key=composed.template_key,
        subject=composed.subject,
        body=composed.body,
        variables=composed.variables,
        missing_required=composed.missing_required,
    )


@router.post("/preview", response_model=GeneralEmailPreviewResponse)
async def preview_general_email(
    payload: GeneralEmailDraftRequest,
    current_user: User = Depends(require_permission("application.email.send")),
    db: AsyncSession = Depends(get_db),
) -> GeneralEmailPreviewResponse:
    previewed = await email_composer.preview_general_email(db, actor=current_user, draft=payload)
    return GeneralEmailPreviewResponse(
        to=previewed.to,
        cc=previewed.cc,
        bcc=previewed.bcc,
        reply_to=previewed.reply_to,
        subject=previewed.rendered.subject,
        html=previewed.rendered.html,
        text=previewed.rendered.text,
        has_call_to_action=previewed.has_call_to_action,
    )


@router.post("/send", response_model=GeneralEmailSendResponse)
async def send_general_email(
    payload: GeneralEmailDraftRequest,
    current_user: User = Depends(require_permission("application.email.send")),
    db: AsyncSession = Depends(get_db),
) -> GeneralEmailSendResponse:
    """Explicit send. No SMTP configuration -> 503 `email_not_configured`;
    provider failure -> 502 `email_delivery_failed`; unfilled placeholders ->
    422. The outcome is recorded in Activities (`GENERAL_EMAIL_SENT` /
    `GENERAL_EMAIL_FAILED`) with the recipients and subject, never the body."""
    sent = await email_composer.send_general_email(db, actor=current_user, draft=payload)
    return GeneralEmailSendResponse(
        sent=True, to=sent.to, cc=sent.cc, bcc=sent.bcc, subject=sent.rendered.subject
    )

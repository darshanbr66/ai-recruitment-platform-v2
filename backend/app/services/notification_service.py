"""Recruitment-workflow email notifications. Route handlers and domain
services never call an email provider SDK directly (CLAUDE.md § 2) — they
call the functions here, which resolve a provider (app/integrations/email)
and know the templates.

Every send is best-effort: a failed or unconfigured provider is logged and
reported back to the caller as `False`, never silently swallowed and never
reported as success when nothing actually went out (see
app/integrations/email/base.py::UnconfiguredEmailProvider). Callers that
trigger email as a side effect of a core workflow action (applying to a
job, changing an application's status) must not let an email failure fail
that action — see app/services/public_application_service.py and
app/api/v1/recruiter/applications.py for how the return value is used.
"""

from app.core.logging import get_logger
from app.integrations.email import EmailError, get_email_provider

logger = get_logger(__name__)


async def _send(*, to: str, subject: str, html: str, context: dict) -> bool:
    provider = get_email_provider()
    try:
        await provider.send(to=to, subject=subject, html=html)
    except EmailError as exc:
        logger.warning(
            "Email not sent", extra={"extra_fields": {**context, "reason": str(exc)}}
        )
        return False
    logger.info("Email sent", extra={"extra_fields": context})
    return True


async def send_application_confirmation(
    *, to: str, candidate_name: str, job_title: str, organization_name: str
) -> bool:
    subject = f"We received your application for {job_title}"
    html = f"""
    <p>Hi {candidate_name},</p>
    <p>Thanks for applying to <strong>{job_title}</strong> at {organization_name}.
    Your application and resume have been received — our team will review it and
    reach out if there's a fit.</p>
    <p>— {organization_name} Hiring Team</p>
    """
    return await _send(
        to=to,
        subject=subject,
        html=html,
        context={"kind": "application_confirmation", "job_title": job_title},
    )


_STATUS_MESSAGES: dict[str, str] = {
    "UNDER_REVIEW": "Your application is now under review by our hiring team.",
    "SCREENING": "Your application has moved into the screening stage.",
    "SHORTLISTED": "Good news — you've been shortlisted for this role.",
    "ASSESSMENT_INVITED": "You've been invited to complete an assessment for this role.",
    "INTERVIEW": "You've been moved to the interview stage. We'll be in touch to schedule.",
    "SELECTED": "Congratulations — you've been selected for this role!",
    "REJECTED": (
        "After careful review, we won't be moving forward with your application "
        "at this time. We appreciate your interest and encourage you to apply again "
        "in the future."
    ),
}


async def send_status_update(
    *, to: str, candidate_name: str, job_title: str, organization_name: str, status: str
) -> bool:
    message = _STATUS_MESSAGES.get(
        status, f"Your application status has been updated to {status.replace('_', ' ').title()}."
    )
    subject = f"Update on your application for {job_title}"
    html = f"""
    <p>Hi {candidate_name},</p>
    <p>{message}</p>
    <p>Role: <strong>{job_title}</strong> at {organization_name}</p>
    <p>— {organization_name} Hiring Team</p>
    """
    return await _send(
        to=to,
        subject=subject,
        html=html,
        context={"kind": "status_update", "job_title": job_title, "status": status},
    )


async def send_assessment_invitation(
    *,
    to: str,
    candidate_name: str,
    job_title: str,
    organization_name: str,
    assessment_title: str,
    invitation_link: str,
    duration_minutes: int,
) -> bool:
    subject = f"Assessment invitation: {assessment_title}"
    html = f"""
    <p>Hi {candidate_name},</p>
    <p>As part of your application for <strong>{job_title}</strong> at
    {organization_name}, please complete the following assessment:</p>
    <p><strong>{assessment_title}</strong> ({duration_minutes} minutes)</p>
    <p><a href="{invitation_link}">Start assessment</a></p>
    <p>— {organization_name} Hiring Team</p>
    """
    return await _send(
        to=to,
        subject=subject,
        html=html,
        context={"kind": "assessment_invitation", "job_title": job_title},
    )

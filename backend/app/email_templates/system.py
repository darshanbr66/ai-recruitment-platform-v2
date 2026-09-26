"""System-sent candidate emails — the two the platform sends on its own
(everything else a candidate receives is composed and sent manually by a
recruiter, see templates.py):

* the email verification code (the candidate asked for it), and
* the welcome / application-acknowledgement email, sent after every
  successful verified self-service application (careers site or campus
  drive link) — in one of two versions: "in review" when the application
  entered the recruitment pipeline, or "not eligible for this role" when
  the submission-time screening screened it out (the profile is retained
  for other roles either way).

Both render through the same layout as recruiter emails (layout.py), and
take the organization's name and published careers contact from the
Organization row — nothing company-specific is hardcoded here. Neither
mentions AI screening, scores or internal statuses.
"""

from app.email_templates.layout import RenderedEmail, render_email

RECRUITMENT_TEAM_NAME = "Recruitment Team"


def render_verification_code_email(
    *, company_name: str, code: str, expires_in_minutes: int, contact_email: str | None
) -> RenderedEmail:
    body = (
        "Hello,\n\n"
        f"Use the verification code below to confirm your email address and continue your "
        f"application with {company_name}.\n\n"
        "Your verification code\n"
        f"Code: {code}\n"
        f"Valid for: {expires_in_minutes} minutes\n\n"
        "For your security, never share this code with anyone. Our team will never ask you "
        "for it.\n\n"
        "If you did not request this code, you can safely ignore this email — no application "
        "will be submitted without it.\n\n"
        f"Kind regards,\n{RECRUITMENT_TEAM_NAME}\n{company_name}"
    )
    return render_email(
        subject=f"Your {company_name} verification code: {code}",
        body=body,
        company_name=company_name,
        recruiter_name=RECRUITMENT_TEAM_NAME,
        recruiter_email=contact_email or "",
    )


def render_welcome_email(
    *,
    company_name: str,
    candidate_name: str,
    job_title: str,
    contact_email: str | None,
    eligible_for_role: bool = True,
) -> RenderedEmail:
    """`eligible_for_role=False` is the version for an application the
    submission-time screening screened out: still a welcome and an
    acknowledgement, but it states plainly that the candidate is not
    eligible for *this* role — never why, and never mentioning AI."""
    update_line = (
        f"If you need to update any of the information you submitted, please contact our "
        f"recruitment team at {contact_email}."
        if contact_email
        else "If you need to update any of the information you submitted, please reply to "
        "this email."
    )
    if eligible_for_role:
        body = (
            f"Dear {candidate_name},\n\n"
            f"Thank you for applying for the {job_title} position at {company_name}, and "
            "welcome to our recruitment process. We have received your application and your "
            "profile is now with our recruitment team.\n\n"
            "What happens next\n"
            "- Our recruitment team will review your profile against the role.\n"
            "- If your background is a good fit, we will contact you by email about the next "
            "steps, which may include an assessment and interviews.\n"
            "- Please keep an eye on your inbox, including your spam folder.\n\n"
            f"{update_line}\n\n"
            "We appreciate your interest and wish you the very best.\n\n"
            f"Kind regards,\n{RECRUITMENT_TEAM_NAME}\n{company_name}"
        )
        subject = f"Welcome to {company_name} – application received for {job_title}"
    else:
        body = (
            f"Dear {candidate_name},\n\n"
            f"Thank you for applying for the {job_title} position at {company_name}, and for "
            "your interest in joining us. We have received your application and your profile "
            "has been created with our recruitment team.\n\n"
            "About this role\n"
            f"Based on the information provided, your profile does not currently meet the "
            f"requirements for the {job_title} role, so you are not eligible for this "
            "particular position and we will not be taking this application forward.\n\n"
            "Your profile stays with us\n"
            "Your profile has been retained, and our recruitment team may contact you by email "
            "if another suitable opportunity arises.\n\n"
            f"{update_line}\n\n"
            "We appreciate the time you took to apply and wish you the very best.\n\n"
            f"Kind regards,\n{RECRUITMENT_TEAM_NAME}\n{company_name}"
        )
        subject = f"Your application to {company_name} for {job_title}"
    return render_email(
        subject=subject,
        body=body,
        company_name=company_name,
        recruiter_name=RECRUITMENT_TEAM_NAME,
        recruiter_email=contact_email or "",
        job_title=job_title,
    )

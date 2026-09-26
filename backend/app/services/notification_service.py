"""Email delivery. Route handlers and domain services never call a provider
SDK directly (CLAUDE.md § 2: "Email provider != business logic") — they come
through here, which resolves the configured provider (app/integrations/email).

Recruitment email is manual. Assigning an assessment, changing a status,
rejecting or selecting never sends anything on its own — those emails go out
only through the explicit "Send" action in `app/services/email_composer.py`.

Exactly two system emails exist, both from the candidate self-service flow
(first HR meeting requirements): the email verification code the candidate
requests (app/services/email_verification_service.py) and the welcome email
sent once their application is accepted into the pipeline
(app/services/public_application_service.py). Templates live in
app/email_templates/system.py.

Failures always propagate as `EmailError` (including
`EmailNotConfiguredError`), so every caller reports exactly what happened
rather than a fake success.
"""

from collections.abc import Sequence

from app.core.logging import get_logger
from app.integrations.email import EmailError, get_email_provider

logger = get_logger(__name__)


async def send_email(
    *,
    to: Sequence[str],
    subject: str,
    html: str,
    text: str,
    reply_to: str | None = None,
    cc: Sequence[str] = (),
    bcc: Sequence[str] = (),
    kind: str = "manual_email",
) -> None:
    """`kind` only labels the structured log line (e.g. "manual_email",
    "email_verification_code", "candidate_welcome")."""
    provider = get_email_provider()
    try:
        await provider.send(
            to=to, subject=subject, html=html, text=text, reply_to=reply_to, cc=cc, bcc=bcc
        )
    except EmailError as exc:
        logger.warning(
            "Email not sent",
            extra={"extra_fields": {"kind": kind, "reason": str(exc)}},
        )
        raise
    # Counts only — never addresses, subject or body.
    logger.info(
        "Email sent",
        extra={
            "extra_fields": {
                "kind": kind,
                "recipients": len(to) + len(cc) + len(bcc),
            }
        },
    )

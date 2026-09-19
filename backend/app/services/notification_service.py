"""Email delivery. Route handlers and domain services never call a provider
SDK directly (CLAUDE.md § 2: "Email provider != business logic") — they come
through here, which resolves the configured provider (app/integrations/email).

Email is MANUAL ONLY. Nothing in the application calls this as a side effect
of a workflow event — applying, assigning an assessment, or changing a status
never sends anything. The single caller is the explicit "Send" action in
`app/services/email_composer.py`, and failures propagate as `EmailError`
(including `EmailNotConfiguredError`) so the sender is told exactly what
happened rather than being shown a fake success.
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
) -> None:
    provider = get_email_provider()
    try:
        await provider.send(
            to=to, subject=subject, html=html, text=text, reply_to=reply_to, cc=cc, bcc=bcc
        )
    except EmailError as exc:
        logger.warning(
            "Email not sent",
            extra={"extra_fields": {"kind": "manual_email", "reason": str(exc)}},
        )
        raise
    # Counts only — never addresses, subject or body.
    logger.info(
        "Email sent",
        extra={
            "extra_fields": {
                "kind": "manual_email",
                "recipients": len(to) + len(cc) + len(bcc),
            }
        },
    )

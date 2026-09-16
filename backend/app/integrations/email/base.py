from abc import ABC, abstractmethod


class EmailError(Exception):
    """Base for every email-sending failure — callers treat "not
    configured" and "provider rejected the request" the same way: the
    email did not go out, log it, do not fail the caller's own workflow
    (CLAUDE.md § 2: "Email provider != business logic")."""


class EmailNotConfiguredError(EmailError):
    """Raised instead of pretending to send. No `RESEND_API_KEY` in the
    environment means no email provider exists yet — the caller must never
    report success in this case (see docs/TEST_CREDENTIALS.md-adjacent
    README section on required env vars)."""


class EmailProvider(ABC):
    @abstractmethod
    async def send(self, *, to: str, subject: str, html: str) -> None: ...


class UnconfiguredEmailProvider(EmailProvider):
    """Selected when no provider is configured. Always raises — this is
    the honest alternative to a fake success response."""

    async def send(self, *, to: str, subject: str, html: str) -> None:
        raise EmailNotConfiguredError(
            "No email provider is configured. Set RESEND_API_KEY and EMAIL_FROM "
            "to enable outbound email (see README)."
        )

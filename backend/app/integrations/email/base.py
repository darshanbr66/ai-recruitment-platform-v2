from abc import ABC, abstractmethod
from collections.abc import Sequence


def as_address_list(value: str | Sequence[str]) -> list[str]:
    """One address or several -> a list. A bare string is itself a sequence of
    characters, so it must never be iterated directly."""
    return [value] if isinstance(value, str) else list(value)


class EmailError(Exception):
    """Base for every email-sending failure. The message is safe to show
    to the recruiter — it never contains credentials or raw server
    responses (CLAUDE.md § 2: "Email provider != business logic")."""


class EmailNotConfiguredError(EmailError):
    """Raised instead of pretending to send. No provider configured in the
    environment means no email can go out — the caller must never report
    success in this case (see README's required env vars)."""


class EmailProvider(ABC):
    @abstractmethod
    async def send(
        self,
        *,
        to: str | Sequence[str],
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
        cc: Sequence[str] = (),
        bcc: Sequence[str] = (),
    ) -> None:
        """`text` is the plain-text alternative; providers that support
        multipart include it alongside `html`. `bcc` recipients receive the
        message but are not named in any header. `reply_to` is where the
        recipient's replies go (the sending recruiter), while the envelope
        sender stays the configured platform address."""


class UnconfiguredEmailProvider(EmailProvider):
    """Selected when no provider is configured. Always raises — this is
    the honest alternative to a fake success response."""

    async def send(
        self,
        *,
        to: str | Sequence[str],
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
        cc: Sequence[str] = (),
        bcc: Sequence[str] = (),
    ) -> None:
        raise EmailNotConfiguredError(
            "Email is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, "
            "SMTP_PASSWORD and SMTP_FROM_EMAIL on the server to enable outbound email."
        )

from app.core.config import get_settings
from app.integrations.email.base import (
    EmailError,
    EmailNotConfiguredError,
    EmailProvider,
    UnconfiguredEmailProvider,
)
from app.integrations.email.resend_provider import ResendEmailProvider
from app.integrations.email.smtp_provider import SmtpEmailProvider

__all__ = [
    "EmailError",
    "EmailNotConfiguredError",
    "EmailProvider",
    "UnconfiguredEmailProvider",
    "ResendEmailProvider",
    "SmtpEmailProvider",
    "get_email_provider",
]


def get_email_provider() -> EmailProvider:
    """Resend (HTTPS) when RESEND_API_KEY and EMAIL_FROM are set, else SMTP
    when fully configured, else an always-raising provider — never a fake
    success.

    Resend wins when both are configured on purpose: production hosts such as
    Render's free web services block outbound SMTP ports, so a deployment that
    has both must use the HTTPS path. Local development configures only SMTP
    and is unaffected; to use SMTP on a machine that also has Resend keys,
    leave RESEND_API_KEY empty."""
    settings = get_settings()
    if (
        settings.resend_api_key is not None
        and settings.resend_api_key.get_secret_value()
        and settings.email_from
    ):
        return ResendEmailProvider(api_key=settings.resend_api_key, from_email=settings.email_from)
    if (
        settings.smtp_host
        and settings.smtp_username
        and settings.smtp_password is not None
        and settings.smtp_password.get_secret_value()
        and settings.smtp_from_email
    ):
        return SmtpEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_email=settings.smtp_from_email,
            from_name=settings.smtp_from_name,
            use_tls=settings.smtp_use_tls,
        )
    return UnconfiguredEmailProvider()

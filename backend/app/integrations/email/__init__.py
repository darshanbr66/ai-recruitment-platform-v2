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
    """SMTP when fully configured, else Resend (legacy), else an
    always-raising provider — never a fake success."""
    settings = get_settings()
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
    if settings.resend_api_key and settings.email_from:
        return ResendEmailProvider(api_key=settings.resend_api_key, from_email=settings.email_from)
    return UnconfiguredEmailProvider()

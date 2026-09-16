from app.core.config import get_settings
from app.integrations.email.base import (
    EmailError,
    EmailNotConfiguredError,
    EmailProvider,
    UnconfiguredEmailProvider,
)
from app.integrations.email.resend_provider import ResendEmailProvider

__all__ = [
    "EmailError",
    "EmailNotConfiguredError",
    "EmailProvider",
    "UnconfiguredEmailProvider",
    "ResendEmailProvider",
    "get_email_provider",
]


def get_email_provider() -> EmailProvider:
    settings = get_settings()
    if settings.resend_api_key and settings.email_from:
        return ResendEmailProvider(api_key=settings.resend_api_key, from_email=settings.email_from)
    return UnconfiguredEmailProvider()

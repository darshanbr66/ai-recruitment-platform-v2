"""Email one-time-code verification for the anonymous candidate flow.

Flow: `request_code` emails a 6-digit code -> `verify_code` checks it and
issues an opaque, single-use verification token -> the application
submission presents that token, which `require_verified_token` validates and
`consume` spends. The backend is authoritative: the browser never holds a
"verified" flag of its own, only a token the server can check.

Abuse controls, all enforced here in the database (so they hold across
server instances and restarts):
- code expiry (`EMAIL_OTP_TTL_MINUTES`) and single use (cleared on success);
- wrong-guess limit per code (`EMAIL_OTP_MAX_ATTEMPTS`), after which a new
  code must be requested;
- resend cooldown (`EMAIL_OTP_RESEND_COOLDOWN_SECONDS`) and a rolling hourly
  send cap per email (`EMAIL_OTP_MAX_SENDS_PER_HOUR`);
- token expiry (`EMAIL_VERIFICATION_TOKEN_TTL_MINUTES`) and single use.
Per-IP request budgets sit in front of this at the API layer.

Secrets at rest: the code is stored only as an HMAC keyed by the server
secret (a 6-digit space is trivially brute-forced from a plain hash), the
token only as its SHA-256 (the same scheme as assessment invitation tokens).
"""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    BadGatewayError,
    ServiceUnavailableError,
    TooManyRequestsError,
    UnprocessableError,
)
from app.core.logging import get_logger
from app.core.security import generate_opaque_token, hash_opaque_token
from app.email_templates.system import render_verification_code_email
from app.integrations.email import EmailError, EmailNotConfiguredError
from app.models.email_verification import EmailVerification, EmailVerificationPurpose
from app.models.organization import Organization
from app.services import notification_service

logger = get_logger(__name__)

CODE_LENGTH = 6
_SEND_WINDOW = timedelta(hours=1)

NOT_VERIFIED_MESSAGE = (
    "Please verify your email address before submitting your application."
)


@dataclass(frozen=True)
class CodeSent:
    expires_in_seconds: int
    resend_available_in_seconds: int


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at: datetime


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_code(verification_id: uuid.UUID, code: str) -> str:
    key = get_settings().jwt_secret_key.encode("utf-8")
    return hmac.new(key, f"{verification_id}:{code}".encode(), hashlib.sha256).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


def _as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def _get_row(
    db: AsyncSession, *, organization_id: uuid.UUID, email: str
) -> EmailVerification | None:
    result = await db.execute(
        select(EmailVerification)
        .where(
            EmailVerification.organization_id == organization_id,
            EmailVerification.email == email,
            EmailVerification.purpose == EmailVerificationPurpose.CANDIDATE_APPLICATION,
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def request_code(
    db: AsyncSession, *, organization: Organization, email: str
) -> CodeSent:
    """Emails a fresh code (invalidating any previous one and any issued
    token for this email). The response never reveals whether the address
    belongs to an existing candidate."""
    settings = get_settings()
    now = datetime.now(UTC)
    email = normalize_email(email)

    row = await _get_row(db, organization_id=organization.id, email=email)
    if row is None:
        row = EmailVerification(
            organization_id=organization.id,
            email=email,
            purpose=EmailVerificationPurpose.CANDIDATE_APPLICATION,
            failed_attempts=0,
            sends_in_window=0,
        )
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
        except IntegrityError as exc:
            # A concurrent request for the same email created the row first.
            raise TooManyRequestsError(
                "A verification code was just requested for this email. Please wait a "
                "moment and try again.",
                code="otp_resend_throttled",
            ) from exc

    cooldown = timedelta(seconds=settings.email_otp_resend_cooldown_seconds)
    if row.last_sent_at is not None and now - _as_aware(row.last_sent_at) < cooldown:
        wait = int((cooldown - (now - _as_aware(row.last_sent_at))).total_seconds()) + 1
        raise TooManyRequestsError(
            f"Please wait {wait} seconds before requesting a new code.",
            code="otp_resend_throttled",
        )

    window_start = row.send_window_started_at
    if window_start is None or now - _as_aware(window_start) >= _SEND_WINDOW:
        row.send_window_started_at = now
        row.sends_in_window = 0
    if row.sends_in_window >= settings.email_otp_max_sends_per_hour:
        raise TooManyRequestsError(
            "Too many verification codes have been requested for this email address. "
            "Please try again later.",
            code="otp_send_limit",
        )

    code = _generate_code()
    ttl = timedelta(minutes=settings.email_otp_ttl_minutes)
    row.code_hash = _hash_code(row.id, code)
    row.code_expires_at = now + ttl
    row.failed_attempts = 0
    row.last_sent_at = now
    row.sends_in_window += 1
    row.verified_at = None
    row.token_hash = None
    row.token_expires_at = None
    row.consumed_at = None
    await db.flush()

    rendered = render_verification_code_email(
        company_name=organization.name,
        code=code,
        expires_in_minutes=settings.email_otp_ttl_minutes,
        contact_email=organization.careers_contact_email,
    )
    try:
        await notification_service.send_email(
            to=[email],
            subject=rendered.subject,
            html=rendered.html,
            text=rendered.text,
            reply_to=organization.careers_contact_email,
            kind="email_verification_code",
        )
    except EmailNotConfiguredError as exc:
        raise ServiceUnavailableError(
            "We can't send verification emails right now. Please try again later.",
            code="email_not_configured",
        ) from exc
    except EmailError as exc:
        raise BadGatewayError(
            "We couldn't send the verification code. Please check the email address and "
            "try again.",
            code="email_delivery_failed",
        ) from exc

    return CodeSent(
        expires_in_seconds=int(ttl.total_seconds()),
        resend_available_in_seconds=settings.email_otp_resend_cooldown_seconds,
    )


async def verify_code(
    db: AsyncSession, *, organization_id: uuid.UUID, email: str, code: str
) -> IssuedToken:
    """Checks the code; on success returns a fresh single-use token. A wrong
    guess is committed before the error is raised, so the attempt counter
    can't be reset by the request's own rollback."""
    settings = get_settings()
    now = datetime.now(UTC)
    email = normalize_email(email)
    code = code.strip()

    row = await _get_row(db, organization_id=organization_id, email=email)
    if row is None or row.code_hash is None or row.code_expires_at is None:
        raise UnprocessableError(
            "No active verification code for this email. Please request a new code.",
            code="otp_invalid",
        )
    if now >= _as_aware(row.code_expires_at):
        raise UnprocessableError(
            "This verification code has expired. Please request a new code.",
            code="otp_expired",
        )
    if row.failed_attempts >= settings.email_otp_max_attempts:
        raise TooManyRequestsError(
            "Too many incorrect attempts. Please request a new code.", code="otp_locked"
        )

    if not (code.isdigit() and hmac.compare_digest(row.code_hash, _hash_code(row.id, code))):
        row.failed_attempts += 1
        remaining = settings.email_otp_max_attempts - row.failed_attempts
        if remaining <= 0:
            row.code_hash = None
        await db.commit()
        if remaining <= 0:
            raise TooManyRequestsError(
                "Too many incorrect attempts. Please request a new code.", code="otp_locked"
            )
        raise UnprocessableError(
            f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
            code="otp_incorrect",
        )

    token = generate_opaque_token()
    expires_at = now + timedelta(minutes=settings.email_verification_token_ttl_minutes)
    row.code_hash = None
    row.code_expires_at = None
    row.failed_attempts = 0
    row.verified_at = now
    row.token_hash = hash_opaque_token(token)
    row.token_expires_at = expires_at
    row.consumed_at = None
    await db.flush()
    return IssuedToken(token=token, expires_at=expires_at)


async def require_verified_token(
    db: AsyncSession, *, organization_id: uuid.UUID, email: str, token: str | None
) -> EmailVerification:
    """The server-side "is this email verified?" check for a submission —
    the token must belong to this organization and this exact email, be
    unexpired and unspent."""
    if not token:
        raise UnprocessableError(NOT_VERIFIED_MESSAGE, code="email_not_verified")
    result = await db.execute(
        select(EmailVerification)
        .where(
            EmailVerification.organization_id == organization_id,
            EmailVerification.token_hash == hash_opaque_token(token),
            EmailVerification.purpose == EmailVerificationPurpose.CANDIDATE_APPLICATION,
        )
        .with_for_update()
    )
    row = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        row is None
        or row.email != normalize_email(email)
        or row.verified_at is None
        or row.consumed_at is not None
        or row.token_expires_at is None
        or now >= _as_aware(row.token_expires_at)
    ):
        raise UnprocessableError(
            "Your email verification has expired or is invalid. Please verify your email "
            "address again.",
            code="email_not_verified",
        )
    return row


async def consume(db: AsyncSession, verification: EmailVerification) -> None:
    verification.consumed_at = datetime.now(UTC)
    await db.flush()

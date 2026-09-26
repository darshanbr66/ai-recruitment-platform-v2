from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EmailVerificationPurpose(StrEnum):
    CANDIDATE_APPLICATION = "CANDIDATE_APPLICATION"


class EmailVerification(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """Proof that an anonymous visitor controls an email address — the
    one-time-code flow in app/services/email_verification_service.py.

    One row per (organization, email, purpose), refreshed in place on every
    new code, so the resend/hourly-send throttles live in the database (they
    hold across server instances and restarts, unlike an in-process limiter).

    Nothing here is stored in a usable form: `code_hash` is an HMAC of the
    code keyed by the server secret (a 6-digit code can't be brute-forced
    from a leaked row without it), and `token_hash` is the SHA-256 of the
    opaque verification token handed to the browser — the same
    hash-at-rest rule as assessment invitation tokens (CLAUDE.md § 4.4).
    """

    __tablename__ = "email_verifications"
    __table_args__ = (
        Index(
            "uq_email_verifications_org_email_purpose",
            "organization_id",
            "email",
            "purpose",
            unique=True,
        ),
        Index("uq_email_verifications_token_hash", "token_hash", unique=True),
    )

    # Lower-cased; a candidate's email is compared case-insensitively.
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    purpose: Mapped[EmailVerificationPurpose] = mapped_column(
        Enum(EmailVerificationPurpose, name="email_verification_purpose", native_enum=True),
        nullable=False,
    )

    code_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Wrong guesses against the *current* code; reset when a new code is sent.
    failed_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Rolling one-hour send budget: codes sent since `send_window_started_at`.
    send_window_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sends_in_window: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when the token was spent on a submitted application (or burned by
    # a blocked duplicate attempt) — a token is single-use.
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

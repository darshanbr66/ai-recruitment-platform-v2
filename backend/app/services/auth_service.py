import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.core.security import (
    TokenAudience,
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    verify_password,
)
from app.db.rls import rls_bypass
from app.models.user import User, UserRefreshToken
from app.services import activity_service

logger = get_logger(__name__)

# One generic message for every failure mode (unknown email, wrong password,
# inactive account, ambiguous cross-tenant email match) — never tell a
# caller *why* their login failed; that would help an attacker enumerate
# valid accounts.
_INVALID_CREDENTIALS = "Invalid email or password."
_INVALID_REFRESH_TOKEN = "Refresh token is invalid or expired."


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    refresh_token_id: uuid.UUID
    access_expires_in: int
    refresh_expires_at: datetime


async def _find_users_by_email(db: AsyncSession, email: str) -> list[User]:
    """Login has no tenant to scope by yet — the client supplies only an
    email/password, and `(organization_id, email)` is unique only *within*
    a tenant (docs/database.md § 3.1), not globally, so the same email can
    exist in more than one organization. Resolving "which account is this"
    is therefore itself a cross-tenant, privileged lookup — exactly the
    class of operation `rls_bypass` exists for (see app/db/rls.py).
    """
    async with rls_bypass(db):
        result = await db.execute(select(User).where(User.email == email))
        return list(result.scalars().all())


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User:
    candidates = await _find_users_by_email(db, email)

    if len(candidates) != 1:
        if len(candidates) > 1:
            # Our schema permits this (uniqueness is per-tenant), but it
            # means we cannot safely tell which account the caller means —
            # fail closed rather than guess.
            logger.warning(
                "login email matched more than one account across tenants",
                extra={"extra_fields": {"match_count": len(candidates)}},
            )
        raise UnauthorizedError(_INVALID_CREDENTIALS)

    user = candidates[0]
    if not user.is_active or not verify_password(password, user.hashed_password):
        # A single account matched but the password (or active flag) was
        # wrong — safe to attribute to that account's own tenant without
        # revealing anything to the caller (the response is identical
        # either way). Zero-match attempts have no tenant to scope to and
        # are deliberately not logged here.
        if user.organization_id is not None:
            async with rls_bypass(db):
                await activity_service.record_activity(
                    db,
                    organization_id=user.organization_id,
                    actor=None,
                    action="LOGIN_FAILED",
                    entity_type="user",
                    entity_id=user.id,
                    entity_label=user.email,
                    description=f"Failed login attempt for {user.email}.",
                )
            # Commit immediately — this function raises right after, and
            # get_db rolls back the whole transaction on any exception
            # (see rotate_refresh_token's identical breach-containment
            # commit above for the same reason).
            await db.commit()
        raise UnauthorizedError(_INVALID_CREDENTIALS)

    return user


async def issue_tokens(
    db: AsyncSession, user: User, *, family_id: uuid.UUID | None = None
) -> IssuedTokens:
    settings = get_settings()
    access_token = create_access_token(
        subject=user.id, audience=TokenAudience.USER, organization_id=user.organization_id
    )

    raw_refresh_token = generate_opaque_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    # Writing a refresh token row is a User-scoped operation, but for a
    # brand-new login the caller's tenant context may not be the token
    # owner's own org (e.g. rotation, resolved via bypass lookup below) —
    # bypass keeps this write correct regardless of the caller's current
    # RLS context rather than depending on it being set just right.
    async with rls_bypass(db):
        refresh_row = UserRefreshToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_refresh_token),
            family_id=family_id or uuid.uuid4(),
            expires_at=expires_at,
        )
        db.add(refresh_row)
        await db.flush()
        refresh_token_id = refresh_row.id

    return IssuedTokens(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        refresh_token_id=refresh_token_id,
        access_expires_in=settings.access_token_expire_minutes * 60,
        refresh_expires_at=expires_at,
    )


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> tuple[User, IssuedTokens]:
    """Rotates a refresh token: the presented token is revoked and a new one
    in the same `family_id` is issued. Presenting a token that was already
    revoked (i.e. reuse of a rotated-out token) revokes the whole family —
    a standard breach-detection signal (docs/architecture.md § 4).
    """
    token_hash = hash_opaque_token(raw_token)

    async with rls_bypass(db):
        token_row = await db.scalar(
            select(UserRefreshToken).where(UserRefreshToken.token_hash == token_hash)
        )

        if token_row is None or token_row.expires_at < datetime.now(UTC):
            raise UnauthorizedError(_INVALID_REFRESH_TOKEN)

        if token_row.revoked_at is not None:
            await db.execute(
                update(UserRefreshToken)
                .where(
                    UserRefreshToken.family_id == token_row.family_id,
                    UserRefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC))
            )
            # Commit the breach-containment revocation immediately rather
            # than letting it ride on the request's normal end-of-request
            # commit (see app/db/session.py::get_db): this handler raises
            # right after, and get_db rolls back the whole transaction on
            # any exception — which would silently undo the very
            # revocation this branch exists to guarantee.
            await db.commit()
            raise UnauthorizedError(_INVALID_REFRESH_TOKEN)

        user = await db.get(User, token_row.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError(_INVALID_REFRESH_TOKEN)

    new_tokens = await issue_tokens(db, user, family_id=token_row.family_id)

    async with rls_bypass(db):
        token_row.revoked_at = datetime.now(UTC)
        token_row.replaced_by_id = new_tokens.refresh_token_id
        await db.flush()

    return user, new_tokens


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Best-effort logout: revokes the presented token if it exists and
    isn't already revoked. Silently no-ops otherwise — logout is not a
    place to reveal whether a token was valid.
    """
    token_hash = hash_opaque_token(raw_token)
    async with rls_bypass(db):
        token_row = await db.scalar(
            select(UserRefreshToken).where(UserRefreshToken.token_hash == token_hash)
        )
        if token_row is not None and token_row.revoked_at is None:
            token_row.revoked_at = datetime.now(UTC)
            await db.flush()

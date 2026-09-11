"""Authentication primitives: password hashing and JWT encode/decode.

Deliberately kept isolated from any domain module (Organization/User/etc.) —
this file knows nothing about the database or any specific entity. Phase 2
wires these primitives into actual register/login/refresh services and
FastAPI dependencies.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

from app.core.config import get_settings

# argon2-cffi's defaults already track current OWASP guidance (time_cost=3,
# memory_cost=64MiB, parallelism=4); set explicitly so a future library
# default change can't silently weaken hashing without review.
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
)


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHash):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """True if a stored hash was made with weaker-than-current parameters."""
    return _password_hasher.check_needs_rehash(hashed_password)


class TokenAudience(StrEnum):
    """Keeps staff (User) and Candidate tokens structurally unable to be
    used against each other's endpoints, even if a role check were ever
    accidentally omitted on a route.
    """

    USER = "user"
    CANDIDATE = "candidate"


class InvalidTokenError(Exception):
    pass


def create_access_token(
    *,
    subject: uuid.UUID,
    audience: TokenAudience,
    organization_id: uuid.UUID | None,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))

    claims: dict[str, Any] = {
        "sub": str(subject),
        "aud": audience.value,
        "org_id": str(organization_id) if organization_id else None,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        claims.update(extra_claims)

    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, *, audience: TokenAudience) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=audience.value,
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc


def generate_opaque_token() -> str:
    """High-entropy bearer token for refresh tokens (and, from Phase 7,
    assessment invitations) — random, not a JWT, shown to the client once.
    """
    return secrets.token_urlsafe(48)


def hash_opaque_token(token: str) -> str:
    """Deterministic digest for opaque bearer tokens, so a presented token
    can be looked up by equality (`WHERE token_hash = :hash`) without ever
    storing it in reversible or comparable-to-many form.

    Not for passwords: Argon2id (`hash_password`/`verify_password`) is
    salted and non-deterministic by design, which is exactly wrong for a
    "find the row this token belongs to" query — but exactly right for
    "verify this one already-identified user's password."
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

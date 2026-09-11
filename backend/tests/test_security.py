import uuid

import pytest

from app.core.security import (
    InvalidTokenError,
    TokenAudience,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True


def test_password_verify_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_password_verify_rejects_garbage_hash() -> None:
    assert verify_password("anything", "not-a-real-argon2-hash") is False


def test_access_token_round_trip() -> None:
    subject = uuid.uuid4()
    org_id = uuid.uuid4()
    token = create_access_token(
        subject=subject, audience=TokenAudience.USER, organization_id=org_id
    )

    claims = decode_access_token(token, audience=TokenAudience.USER)

    assert claims["sub"] == str(subject)
    assert claims["org_id"] == str(org_id)
    assert claims["aud"] == "user"


def test_token_audience_mismatch_is_rejected() -> None:
    """A candidate token must never validate against the user audience, and
    vice versa — this is the structural guarantee behind CLAUDE.md's
    "candidate accounts and recruiter accounts must be logically separated"
    rule.
    """
    token = create_access_token(
        subject=uuid.uuid4(), audience=TokenAudience.CANDIDATE, organization_id=uuid.uuid4()
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, audience=TokenAudience.USER)

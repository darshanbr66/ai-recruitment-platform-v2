from httpx import AsyncClient

from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login


async def test_successful_login_returns_access_token_and_sets_refresh_cookie(
    client: AsyncClient, super_admin: User
) -> None:
    response = await client.post(
        "/api/v1/recruiter/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert isinstance(body["access_token"], str) and body["access_token"]

    assert "refresh_token" in response.cookies
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header
    # Lax in development (frontend + API share the `localhost` site); the
    # production SameSite=None variant is covered in test_session_cookie.py.
    assert "samesite=lax" in set_cookie_header.lower()


async def test_login_with_wrong_password_is_rejected(
    client: AsyncClient, super_admin: User
) -> None:
    response = await client.post(
        "/api/v1/recruiter/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": "definitely-wrong"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


async def test_login_with_unknown_email_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/recruiter/auth/login",
        json={"email": "nobody@nowhere.dev", "password": "whatever12345"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


async def test_login_error_message_is_identical_for_unknown_email_and_wrong_password(
    client: AsyncClient, super_admin: User
) -> None:
    """Guards against user-enumeration: the two failure modes must be
    indistinguishable to the caller (docs/security.md § 7).
    """
    unknown = await client.post(
        "/api/v1/recruiter/auth/login",
        json={"email": "nobody@nowhere.dev", "password": "whatever12345"},
    )
    wrong_password = await client.post(
        "/api/v1/recruiter/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": "wrong-password"},
    )
    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json()["error"]["message"] == wrong_password.json()["error"]["message"]


async def test_login_rejects_malformed_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/recruiter/auth/login",
        json={"email": "not-an-email", "password": "whatever12345"},
    )
    assert response.status_code == 422


async def test_me_requires_a_valid_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/recruiter/auth/me")
    assert response.status_code == 401

    response = await client.get(
        "/api/v1/recruiter/auth/me", headers={"Authorization": "Bearer garbage.token.value"}
    )
    assert response.status_code == 401


async def test_me_returns_current_user_with_roles(client: AsyncClient, super_admin: User) -> None:
    tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)

    response = await client.get(
        "/api/v1/recruiter/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == SUPER_ADMIN_EMAIL
    assert body["organization_id"] is None
    assert body["roles"] == ["SUPER_ADMIN"]

"""Refresh-token rotation and reuse detection
(docs/architecture.md § 4, docs/security.md § 1).
"""

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login


async def test_refresh_issues_a_new_access_token(client: AsyncClient, super_admin: User) -> None:
    login_body = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)

    response = await client.post("/api/v1/recruiter/auth/refresh")

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["access_token"] != login_body["access_token"]


async def test_refresh_rotates_the_cookie_value(client: AsyncClient, super_admin: User) -> None:
    await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    first_cookie = client.cookies.get("refresh_token")

    await client.post("/api/v1/recruiter/auth/refresh")
    second_cookie = client.cookies.get("refresh_token")

    assert first_cookie is not None
    assert second_cookie is not None
    assert first_cookie != second_cookie


async def test_refresh_without_cookie_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/recruiter/auth/refresh")
    assert response.status_code == 401


async def test_reusing_a_rotated_refresh_token_is_rejected_and_revokes_the_family(
    client: AsyncClient, super_admin: User
) -> None:
    await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    old_refresh_token = client.cookies.get("refresh_token")
    assert old_refresh_token is not None

    # Legitimate rotation.
    first_refresh = await client.post("/api/v1/recruiter/auth/refresh")
    assert first_refresh.status_code == 200
    new_refresh_token = client.cookies.get("refresh_token")

    # Replay the now-superseded token — simulates a stolen/duplicated token.
    client.cookies.set("refresh_token", old_refresh_token, path="/api/v1/recruiter/auth")
    replay = await client.post("/api/v1/recruiter/auth/refresh")
    assert replay.status_code == 401

    # The whole family (including the token issued by the legitimate
    # rotation above) must now be revoked too — breach containment.
    client.cookies.set("refresh_token", new_refresh_token, path="/api/v1/recruiter/auth")
    follow_up = await client.post("/api/v1/recruiter/auth/refresh")
    assert follow_up.status_code == 401


async def test_logout_revokes_the_refresh_token(client: AsyncClient, super_admin: User) -> None:
    await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)

    logout_response = await client.post("/api/v1/recruiter/auth/logout")
    assert logout_response.status_code == 204

    refresh_response = await client.post("/api/v1/recruiter/auth/refresh")
    assert refresh_response.status_code == 401

"""Refresh-cookie attributes (session persistence across page reloads) and
the `/auth/me` payload the UI uses to label tenant-scoped screens."""

import pytest
from httpx import AsyncClient

from app.api.v1.recruiter import auth as auth_module
from app.core.config import get_settings
from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login
from tests.test_applications import _bootstrap_org, _org_admin_headers


async def _login_response(client: AsyncClient):
    return await client.post(
        "/api/v1/recruiter/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
    )


async def test_refresh_cookie_is_lax_in_development(client: AsyncClient, super_admin: User) -> None:
    response = await _login_response(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


async def test_refresh_cookie_is_cross_site_capable_in_production(
    client: AsyncClient, super_admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vercel (frontend) and Render (API) are different sites: a
    SameSite=Strict cookie is never sent on the SPA's refresh call, which
    logged users out on every page reload. Production must issue
    SameSite=None; Secure."""
    real = get_settings()
    monkeypatch.setattr(
        auth_module,
        "get_settings",
        lambda: real.model_copy(update={"environment": "production", "debug": False}),
    )

    response = await _login_response(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=none" in cookie


async def test_me_returns_the_organization_name_for_org_users_only(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "me-org-name")
    headers = await _org_admin_headers(client, org)

    me = await client.get("/api/v1/recruiter/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["organization_name"] == "Acme Corp"
    assert me.json()["full_name"] == "Acme Admin"

    super_tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    super_me = await client.get(
        "/api/v1/recruiter/auth/me",
        headers={"Authorization": f"Bearer {super_tokens['access_token']}"},
    )
    assert super_me.json()["organization_name"] is None

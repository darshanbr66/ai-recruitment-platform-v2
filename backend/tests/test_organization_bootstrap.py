"""Organization creation must go through the SUPER_ADMIN-only privileged
path (docs/security.md § 3) and must not be reachable by an ordinary tenant
user — even one holding ORG_ADMIN in their own org.
"""

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login


def _org_payload(slug: str) -> dict:
    return {
        "name": "Acme Corp",
        "slug": slug,
        "admin_email": f"admin@{slug}.dev",
        "admin_password": "AcmeAdminPass1",
        "admin_full_name": "Acme Admin",
    }


async def test_super_admin_can_create_organization(client: AsyncClient, super_admin: User) -> None:
    tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)

    response = await client.post(
        "/api/v1/admin/organizations",
        json=_org_payload("acme-bootstrap"),
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["slug"] == "acme-bootstrap"
    assert body["status"] == "ACTIVE"


async def test_created_org_admin_can_immediately_log_in(
    client: AsyncClient, super_admin: User
) -> None:
    tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    payload = _org_payload("acme-login-check")

    create_response = await client.post(
        "/api/v1/admin/organizations",
        json=payload,
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert create_response.status_code == 201

    admin_tokens = await login(
        client, email=payload["admin_email"], password=payload["admin_password"]
    )
    assert admin_tokens["access_token"]


async def test_duplicate_slug_is_rejected(client: AsyncClient, super_admin: User) -> None:
    tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    payload = _org_payload("acme-dup")

    first = await client.post("/api/v1/admin/organizations", json=payload, headers=headers)
    assert first.status_code == 201

    second_payload = dict(payload, admin_email="someoneelse@acme-dup.dev")
    second = await client.post(
        "/api/v1/admin/organizations", json=second_payload, headers=headers
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_invalid_slug_is_rejected(client: AsyncClient, super_admin: User) -> None:
    tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await client.post(
        "/api/v1/admin/organizations",
        json=_org_payload("Not A Valid Slug!"),
        headers=headers,
    )
    assert response.status_code == 422


async def test_ordinary_tenant_admin_cannot_create_organization(
    client: AsyncClient, super_admin: User
) -> None:
    super_admin_tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    payload = _org_payload("acme-no-escalation")
    create_response = await client.post(
        "/api/v1/admin/organizations",
        json=payload,
        headers={"Authorization": f"Bearer {super_admin_tokens['access_token']}"},
    )
    assert create_response.status_code == 201

    org_admin_tokens = await login(
        client, email=payload["admin_email"], password=payload["admin_password"]
    )

    response = await client.post(
        "/api/v1/admin/organizations",
        json=_org_payload("acme-escalation-attempt"),
        headers={"Authorization": f"Bearer {org_admin_tokens['access_token']}"},
    )
    assert response.status_code == 403


async def test_organization_endpoints_require_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/admin/organizations", json=_org_payload("no-auth"))
    assert response.status_code == 401

    response = await client.get("/api/v1/admin/organizations")
    assert response.status_code == 401

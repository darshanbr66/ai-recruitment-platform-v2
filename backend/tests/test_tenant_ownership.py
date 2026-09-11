"""API-level tenant ownership enforcement — complements
tests/test_tenant_isolation.py (which exercises the raw RLS policies
directly). These tests go through the real HTTP endpoints and real JWTs to
confirm the whole stack (auth dependency -> RLS tenant context -> query)
actually denies cross-tenant access end to end, per docs/security.md § 2:
"Cross-tenant access to an existing resource returns 404, not 403."
"""

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login


async def _bootstrap_org(client: AsyncClient, slug: str) -> dict:
    super_admin_tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    payload = {
        "name": "Acme Corp",
        "slug": slug,
        "admin_email": f"admin@{slug}.dev",
        "admin_password": "AcmeAdminPass1",
        "admin_full_name": "Acme Admin",
    }
    response = await client.post(
        "/api/v1/admin/organizations",
        json=payload,
        headers={"Authorization": f"Bearer {super_admin_tokens['access_token']}"},
    )
    assert response.status_code == 201, response.text
    return payload


async def _org_admin_headers(client: AsyncClient, org: dict) -> dict:
    tokens = await login(client, email=org["admin_email"], password=org["admin_password"])
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_org_a_cannot_see_org_bs_users_in_list(
    client: AsyncClient, super_admin: User
) -> None:
    org_a = await _bootstrap_org(client, "tenant-list-a")
    org_b = await _bootstrap_org(client, "tenant-list-b")

    await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": "hire@tenant-list-b.dev",
            "password": "SomePassword1",
            "full_name": "Org B Recruiter",
            "role": "RECRUITER",
        },
        headers=await _org_admin_headers(client, org_b),
    )

    response = await client.get(
        "/api/v1/recruiter/users", headers=await _org_admin_headers(client, org_a)
    )

    assert response.status_code == 200
    emails = {user["email"] for user in response.json()}
    assert "hire@tenant-list-b.dev" not in emails
    assert org_a["admin_email"] in emails


async def test_org_a_gets_404_fetching_org_bs_user_by_id(
    client: AsyncClient, super_admin: User
) -> None:
    org_a = await _bootstrap_org(client, "tenant-getid-a")
    org_b = await _bootstrap_org(client, "tenant-getid-b")

    create_response = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": "target@tenant-getid-b.dev",
            "password": "SomePassword1",
            "full_name": "Target User",
            "role": "RECRUITER",
        },
        headers=await _org_admin_headers(client, org_b),
    )
    assert create_response.status_code == 201
    target_user_id = create_response.json()["id"]

    response = await client.get(
        f"/api/v1/recruiter/users/{target_user_id}",
        headers=await _org_admin_headers(client, org_a),
    )

    assert response.status_code == 404


async def test_org_admin_can_fetch_their_own_organizations_user_by_id(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "tenant-getid-own")
    headers = await _org_admin_headers(client, org)

    create_response = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": "colleague@tenant-getid-own.dev",
            "password": "SomePassword1",
            "full_name": "Colleague",
            "role": "RECRUITER",
        },
        headers=headers,
    )
    user_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/recruiter/users/{user_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "colleague@tenant-getid-own.dev"


async def test_a_users_token_only_ever_grants_access_within_their_own_org(
    client: AsyncClient, super_admin: User
) -> None:
    """A stronger end-to-end variant: log in as Org B's admin and confirm
    every user id returned by /me and by listing belongs to Org B alone,
    even after Org A has created several users of its own.
    """
    org_a = await _bootstrap_org(client, "tenant-strict-a")
    org_b = await _bootstrap_org(client, "tenant-strict-b")
    headers_a = await _org_admin_headers(client, org_a)
    headers_b = await _org_admin_headers(client, org_b)

    for i in range(3):
        await client.post(
            "/api/v1/recruiter/users",
            json={
                "email": f"a-user-{i}@tenant-strict-a.dev",
                "password": "SomePassword1",
                "full_name": f"A User {i}",
                "role": "RECRUITER",
            },
            headers=headers_a,
        )

    listing_b = await client.get("/api/v1/recruiter/users", headers=headers_b)
    assert listing_b.status_code == 200
    orgs_seen = {user["organization_id"] for user in listing_b.json()}

    me_b = await client.get("/api/v1/recruiter/auth/me", headers=headers_b)
    assert orgs_seen == {me_b.json()["organization_id"]}

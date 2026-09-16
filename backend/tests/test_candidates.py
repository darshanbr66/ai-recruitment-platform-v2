"""Recruiter-facing Candidate CRUD (Phase 3) — creation, per-org email
uniqueness, and tenant isolation."""

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


def _candidate_payload(email: str) -> dict:
    return {
        "email": email,
        "full_name": "Cara Candidate",
        "phone": "+1-555-0100",
        "location": "Bengaluru, India",
        "current_title": "Software Engineer",
        "years_experience": 4,
    }


async def test_org_admin_can_create_and_list_a_candidate(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "candidates-happy-path")
    headers = await _org_admin_headers(client, org)

    response = await client.post(
        "/api/v1/recruiter/candidates",
        json=_candidate_payload("cara@candidates-happy-path-candidate.dev"),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source"] == "RECRUITER_ADDED"
    assert body["is_active"] is True

    list_response = await client.get("/api/v1/recruiter/candidates", headers=headers)
    emails = [candidate["email"] for candidate in list_response.json()]
    assert "cara@candidates-happy-path-candidate.dev" in emails


async def test_duplicate_candidate_email_in_same_org_is_rejected(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "candidates-duplicate")
    headers = await _org_admin_headers(client, org)
    payload = _candidate_payload("dup@candidates-duplicate-candidate.dev")

    first = await client.post("/api/v1/recruiter/candidates", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/recruiter/candidates", json=payload, headers=headers)
    assert second.status_code == 409


async def test_same_candidate_email_allowed_in_different_organizations(
    client: AsyncClient, super_admin: User
) -> None:
    org_a = await _bootstrap_org(client, "candidates-cross-a")
    org_b = await _bootstrap_org(client, "candidates-cross-b")
    shared_payload = _candidate_payload("shared-candidate@example.dev")

    response_a = await client.post(
        "/api/v1/recruiter/candidates",
        json=shared_payload,
        headers=await _org_admin_headers(client, org_a),
    )
    response_b = await client.post(
        "/api/v1/recruiter/candidates",
        json=shared_payload,
        headers=await _org_admin_headers(client, org_b),
    )
    assert response_a.status_code == 201
    assert response_b.status_code == 201


async def test_org_a_gets_404_fetching_org_bs_candidate(
    client: AsyncClient, super_admin: User
) -> None:
    org_a = await _bootstrap_org(client, "candidates-tenant-a")
    org_b = await _bootstrap_org(client, "candidates-tenant-b")

    created_in_b = (
        await client.post(
            "/api/v1/recruiter/candidates",
            json=_candidate_payload("target@candidates-tenant-b-candidate.dev"),
            headers=await _org_admin_headers(client, org_b),
        )
    ).json()

    response = await client.get(
        f"/api/v1/recruiter/candidates/{created_in_b['id']}",
        headers=await _org_admin_headers(client, org_a),
    )
    assert response.status_code == 404


async def test_create_candidate_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/recruiter/candidates", json=_candidate_payload("nobody@nowhere.dev")
    )
    assert response.status_code == 401

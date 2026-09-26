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
    # The 409 names the profile it collided with, so staff can add the
    # resume/role to that candidate rather than creating a duplicate (the
    # HR "add resume + applying role" flow relies on this).
    error = second.json()["error"]
    assert error["data"]["existing_candidate_id"] == first.json()["id"]


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


async def test_delete_candidate_requires_a_reason(client: AsyncClient, super_admin: User) -> None:
    org = await _bootstrap_org(client, "candidates-delete-no-reason")
    headers = await _org_admin_headers(client, org)
    candidate = (
        await client.post(
            "/api/v1/recruiter/candidates",
            json=_candidate_payload("noreason@candidates-delete-no-reason-candidate.dev"),
            headers=headers,
        )
    ).json()

    response = await client.post(
        f"/api/v1/recruiter/candidates/{candidate['id']}/delete", json={"reason": ""}, headers=headers
    )
    assert response.status_code == 422


async def test_delete_candidate_soft_deletes_and_records_an_activity(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "candidates-delete-happy")
    headers = await _org_admin_headers(client, org)
    candidate = (
        await client.post(
            "/api/v1/recruiter/candidates",
            json=_candidate_payload("gone@candidates-delete-happy-candidate.dev"),
            headers=headers,
        )
    ).json()

    delete_response = await client.post(
        f"/api/v1/recruiter/candidates/{candidate['id']}/delete",
        json={"reason": "Duplicate candidate record."},
        headers=headers,
    )
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["deleted_at"] is not None

    # Gone from the active list...
    listing = await client.get("/api/v1/recruiter/candidates", headers=headers)
    assert candidate["id"] not in [c["id"] for c in listing.json()]

    # ...but still reachable by id (audit trail navigation), not hard-deleted.
    detail = await client.get(f"/api/v1/recruiter/candidates/{candidate['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["deleted_at"] is not None

    # Deleting again is rejected rather than silently no-op-ing.
    second_delete = await client.post(
        f"/api/v1/recruiter/candidates/{candidate['id']}/delete",
        json={"reason": "Trying again."},
        headers=headers,
    )
    assert second_delete.status_code == 409

    activities = await client.get("/api/v1/recruiter/activities", headers=headers)
    assert activities.status_code == 200
    entries = activities.json()
    # Login/organization-bootstrap actions are legitimately audited too now
    # (QA § 5: "track every meaningful administrative action") — this test
    # only asserts on the one entry it cares about.
    delete_entries = [e for e in entries if e["action"] == "CANDIDATE_DELETED"]
    assert len(delete_entries) == 1
    entry = delete_entries[0]
    assert entry["entity_type"] == "candidate"
    assert entry["entity_id"] == candidate["id"]
    assert entry["reason"] == "Duplicate candidate record."
    assert entry["actor_name"] == "Acme Admin"


async def test_activities_endpoint_requires_activity_read_permission(
    client: AsyncClient, super_admin: User
) -> None:
    """RECRUITER can delete a candidate but cannot read the audit log —
    Activities is an org-admin-only surface (CLAUDE.md's "hidden platform
    role" sibling rule: never expose audit history to ordinary staff)."""
    org = await _bootstrap_org(client, "candidates-activity-perm")
    admin_headers = await _org_admin_headers(client, org)

    recruiter_created = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": f"recruiter@{org['slug']}.dev",
            "full_name": "Riya Recruiter",
            "password": "RecruiterPass1",
            "role": "RECRUITER",
        },
        headers=admin_headers,
    )
    assert recruiter_created.status_code == 201, recruiter_created.text
    recruiter_tokens = await login(
        client, email=f"recruiter@{org['slug']}.dev", password="RecruiterPass1"
    )
    recruiter_headers = {"Authorization": f"Bearer {recruiter_tokens['access_token']}"}

    response = await client.get("/api/v1/recruiter/activities", headers=recruiter_headers)
    assert response.status_code == 403

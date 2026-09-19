"""ORG_ADMIN deletion of activity/audit entries: permission gating and
tenant isolation. Every authorization decision is enforced server-side
(CLAUDE.md § 2)."""

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import login
from tests.test_applications import _bootstrap_org, _org_admin_headers


async def _create_candidate_entry(client: AsyncClient, headers: dict, email: str) -> str:
    """Creating a candidate writes a CANDIDATE_CREATED activity; returns its id."""
    response = await client.post(
        "/api/v1/recruiter/candidates",
        json={"email": email, "full_name": "Cara Candidate"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    activities = (await client.get("/api/v1/recruiter/activities", headers=headers)).json()
    (entry,) = [a for a in activities if a["action"] == "CANDIDATE_CREATED"]
    return entry["id"]


async def _activity_ids(client: AsyncClient, headers: dict) -> list[str]:
    response = await client.get("/api/v1/recruiter/activities", headers=headers)
    assert response.status_code == 200, response.text
    return [a["id"] for a in response.json()]


async def test_org_admin_can_delete_an_activity_entry(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "activity-delete-happy")
    headers = await _org_admin_headers(client, org)
    activity_id = await _create_candidate_entry(client, headers, "a@activity-delete-happy.dev")

    response = await client.delete(f"/api/v1/recruiter/activities/{activity_id}", headers=headers)

    assert response.status_code == 204, response.text
    assert activity_id not in await _activity_ids(client, headers)

    # Deleting it again is a clean 404, not a silent success.
    again = await client.delete(f"/api/v1/recruiter/activities/{activity_id}", headers=headers)
    assert again.status_code == 404


async def test_recruiter_cannot_delete_activities(client: AsyncClient, super_admin: User) -> None:
    org = await _bootstrap_org(client, "activity-delete-perm")
    admin_headers = await _org_admin_headers(client, org)
    activity_id = await _create_candidate_entry(client, admin_headers, "a@activity-delete-perm.dev")

    created = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": f"recruiter@{org['slug']}.dev",
            "full_name": "Riya Recruiter",
            "password": "RecruiterPass1",
            "role": "RECRUITER",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    tokens = await login(client, email=f"recruiter@{org['slug']}.dev", password="RecruiterPass1")
    recruiter_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await client.delete(
        f"/api/v1/recruiter/activities/{activity_id}", headers=recruiter_headers
    )

    assert response.status_code == 403
    assert activity_id in await _activity_ids(client, admin_headers)


async def test_delete_activity_requires_authentication(client: AsyncClient) -> None:
    response = await client.delete(
        "/api/v1/recruiter/activities/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 401


async def test_org_admin_cannot_delete_another_organizations_activity(
    client: AsyncClient, super_admin: User
) -> None:
    org_a = await _bootstrap_org(client, "activity-delete-tenant-a")
    org_b = await _bootstrap_org(client, "activity-delete-tenant-b")
    headers_a = await _org_admin_headers(client, org_a)
    headers_b = await _org_admin_headers(client, org_b)
    activity_id_a = await _create_candidate_entry(
        client, headers_a, "a@activity-delete-tenant-a.dev"
    )

    response = await client.delete(
        f"/api/v1/recruiter/activities/{activity_id_a}", headers=headers_b
    )

    # Indistinguishable from "doesn't exist" — and the row is untouched.
    assert response.status_code == 404
    assert activity_id_a in await _activity_ids(client, headers_a)

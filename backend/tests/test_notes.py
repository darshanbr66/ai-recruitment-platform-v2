"""Recruiter notes on an Application."""

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login


async def _bootstrap_org_with_application(client: AsyncClient, slug: str) -> dict:
    super_admin_tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    org_payload = {
        "name": "Acme Corp",
        "slug": slug,
        "admin_email": f"admin@{slug}.dev",
        "admin_password": "AcmeAdminPass1",
        "admin_full_name": "Acme Admin",
    }
    await client.post(
        "/api/v1/admin/organizations",
        json=org_payload,
        headers={"Authorization": f"Bearer {super_admin_tokens['access_token']}"},
    )
    admin_tokens = await login(
        client, email=org_payload["admin_email"], password=org_payload["admin_password"]
    )
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    job = (
        await client.post(
            "/api/v1/recruiter/jobs", json={"title": "Engineer", "description": "..."}, headers=headers
        )
    ).json()
    candidate = (
        await client.post(
            "/api/v1/recruiter/candidates",
            json={"email": "c1@example.com", "full_name": "Cara Candidate"},
            headers=headers,
        )
    ).json()
    application = (
        await client.post(
            "/api/v1/recruiter/applications",
            json={"candidate_id": candidate["id"], "job_id": job["id"]},
            headers=headers,
        )
    ).json()

    return {"headers": headers, "application_id": application["id"]}


async def test_create_and_list_notes(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_application(client, "notes-happy")

    response = await client.post(
        f"/api/v1/recruiter/applications/{ctx['application_id']}/notes",
        json={"body": "Strong communication skills in the phone screen."},
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["body"] == "Strong communication skills in the phone screen."
    assert body["author_name"] == "Acme Admin"

    listing = await client.get(
        f"/api/v1/recruiter/applications/{ctx['application_id']}/notes", headers=ctx["headers"]
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_notes_require_authentication(client: AsyncClient) -> None:
    import uuid

    response = await client.get(f"/api/v1/recruiter/applications/{uuid.uuid4()}/notes")
    assert response.status_code == 401

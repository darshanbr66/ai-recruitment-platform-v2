"""Campus drives: composing an existing Job with scheduling metadata, and
automatic Application.campus_drive_id association for public applicants
(docs/campus-hiring.md)."""

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login, make_minimal_pdf


async def _bootstrap_org_with_job(client: AsyncClient, slug: str) -> dict:
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
            "/api/v1/recruiter/jobs",
            json={"title": "Graduate Engineer", "description": "Entry-level role."},
            headers=headers,
        )
    ).json()
    await client.patch(
        f"/api/v1/recruiter/jobs/{job['id']}", json={"status": "OPEN"}, headers=headers
    )

    return {"headers": headers, "job": job, "slug": slug}


async def test_create_and_list_campus_drive(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_job(client, "campus-create")

    response = await client.post(
        "/api/v1/recruiter/campus-drives",
        json={"name": "Fall 2026 Drive", "job_id": ctx["job"]["id"], "college_name": "MIT", "batch_year": 2026},
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PLANNED"
    assert body["job_title"] == "Graduate Engineer"
    assert body["application_count"] == 0

    listing = await client.get("/api/v1/recruiter/campus-drives", headers=ctx["headers"])
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_update_drive_status(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_job(client, "campus-update")
    drive = (
        await client.post(
            "/api/v1/recruiter/campus-drives",
            json={"name": "Drive", "job_id": ctx["job"]["id"], "college_name": "MIT"},
            headers=ctx["headers"],
        )
    ).json()

    response = await client.patch(
        f"/api/v1/recruiter/campus-drives/{drive['id']}",
        json={"status": "ACTIVE"},
        headers=ctx["headers"],
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"


async def test_public_applicant_is_auto_associated_with_active_drive(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_job(client, "campus-auto-assoc")
    drive = (
        await client.post(
            "/api/v1/recruiter/campus-drives",
            json={"name": "Drive", "job_id": ctx["job"]["id"], "college_name": "MIT"},
            headers=ctx["headers"],
        )
    ).json()
    await client.patch(
        f"/api/v1/recruiter/campus-drives/{drive['id']}", json={"status": "ACTIVE"}, headers=ctx["headers"]
    )

    resume = make_minimal_pdf("Cara Candidate")
    apply_response = await client.post(
        f"/api/v1/public/organizations/{ctx['slug']}/jobs/{ctx['job']['id']}/apply",
        data={"full_name": "Cara Candidate", "email": "cara@example.com"},
        files={"resume": ("resume.pdf", resume, "application/pdf")},
    )
    assert apply_response.status_code == 201
    application_id = apply_response.json()["id"]

    application = (
        await client.get(f"/api/v1/recruiter/applications/{application_id}", headers=ctx["headers"])
    ).json()
    assert application["campus_drive_id"] == drive["id"]

    filtered = await client.get(
        f"/api/v1/recruiter/applications?campus_drive_id={drive['id']}", headers=ctx["headers"]
    )
    assert len(filtered.json()) == 1

    drive_after = (
        await client.get(f"/api/v1/recruiter/campus-drives/{drive['id']}", headers=ctx["headers"])
    ).json()
    assert drive_after["application_count"] == 1


async def test_planned_drive_does_not_auto_associate(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_job(client, "campus-planned-no-assoc")
    await client.post(
        "/api/v1/recruiter/campus-drives",
        json={"name": "Drive", "job_id": ctx["job"]["id"], "college_name": "MIT"},
        headers=ctx["headers"],
    )

    resume = make_minimal_pdf("Dana Candidate")
    apply_response = await client.post(
        f"/api/v1/public/organizations/{ctx['slug']}/jobs/{ctx['job']['id']}/apply",
        data={"full_name": "Dana Candidate", "email": "dana@example.com"},
        files={"resume": ("resume.pdf", resume, "application/pdf")},
    )
    application_id = apply_response.json()["id"]
    application = (
        await client.get(f"/api/v1/recruiter/applications/{application_id}", headers=ctx["headers"])
    ).json()
    assert application["campus_drive_id"] is None


async def test_campus_drives_are_tenant_scoped(client: AsyncClient, super_admin: User) -> None:
    ctx_a = await _bootstrap_org_with_job(client, "campus-tenant-a")
    ctx_b = await _bootstrap_org_with_job(client, "campus-tenant-b")

    await client.post(
        "/api/v1/recruiter/campus-drives",
        json={"name": "Org A Drive", "job_id": ctx_a["job"]["id"], "college_name": "MIT"},
        headers=ctx_a["headers"],
    )

    listing_b = await client.get("/api/v1/recruiter/campus-drives", headers=ctx_b["headers"])
    assert listing_b.json() == []

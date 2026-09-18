"""Recruitment reports are computed from real, tenant-scoped data — never
hardcoded (CLAUDE.md § 2)."""

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
    tokens = await login(client, email=payload["admin_email"], password=payload["admin_password"])
    return {"headers": {"Authorization": f"Bearer {tokens['access_token']}"}}


async def test_overview_reflects_real_data(client: AsyncClient, super_admin: User) -> None:
    org = await _bootstrap_org(client, "reports-overview")
    headers = org["headers"]

    empty = await client.get("/api/v1/recruiter/reports/overview", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {
        "total_jobs": 0,
        "open_jobs": 0,
        "total_candidates": 0,
        "total_applications": 0,
        "selected_candidates": 0,
        "rejected_candidates": 0,
        "hired_candidates": 0,
        "applications_by_status": [],
        "applications_by_job": [],
        "screening": {"total_runs": 0, "completed": 0, "failed": 0, "average_score": None},
        "assessments": {"total_invitations": 0, "submitted": 0, "passed": 0},
        "campus_drives": [],
    }

    job = (
        await client.post(
            "/api/v1/recruiter/jobs",
            json={"title": "Backend Engineer", "description": "Build things."},
            headers=headers,
        )
    ).json()
    await client.patch(
        f"/api/v1/recruiter/jobs/{job['id']}", json={"status": "OPEN"}, headers=headers
    )

    candidate = (
        await client.post(
            "/api/v1/recruiter/candidates",
            json={"email": "c1@example.com", "full_name": "Cara Candidate"},
            headers=headers,
        )
    ).json()

    await client.post(
        "/api/v1/recruiter/applications",
        json={"candidate_id": candidate["id"], "job_id": job["id"]},
        headers=headers,
    )

    report = (
        await client.get("/api/v1/recruiter/reports/overview", headers=headers)
    ).json()
    assert report["total_jobs"] == 1
    assert report["open_jobs"] == 1
    assert report["total_candidates"] == 1
    assert report["total_applications"] == 1
    assert report["applications_by_status"] == [{"status": "APPLIED", "count": 1}]
    assert report["applications_by_job"] == [
        {"job_id": job["id"], "job_title": "Backend Engineer", "count": 1}
    ]


async def test_overview_includes_campus_drive_breakdown(client: AsyncClient, super_admin: User) -> None:
    org = await _bootstrap_org(client, "reports-campus")
    headers = org["headers"]

    job = (
        await client.post(
            "/api/v1/recruiter/jobs",
            json={"title": "Graduate Engineer", "description": "..."},
            headers=headers,
        )
    ).json()
    drive = (
        await client.post(
            "/api/v1/recruiter/campus-drives",
            json={"name": "Fall Drive", "job_id": job["id"], "college_name": "MIT"},
            headers=headers,
        )
    ).json()

    report = (await client.get("/api/v1/recruiter/reports/overview", headers=headers)).json()
    assert report["campus_drives"] == [
        {"drive_id": drive["id"], "drive_name": "Fall Drive", "application_count": 0}
    ]


async def test_overview_outcome_metrics_exclude_soft_deleted_applications(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "reports-outcomes")
    headers = org["headers"]

    job = (
        await client.post(
            "/api/v1/recruiter/jobs",
            json={"title": "Backend Engineer", "description": "Build things."},
            headers=headers,
        )
    ).json()
    await client.patch(f"/api/v1/recruiter/jobs/{job['id']}", json={"status": "OPEN"}, headers=headers)

    async def _application(email: str) -> str:
        candidate = (
            await client.post(
                "/api/v1/recruiter/candidates",
                json={"email": email, "full_name": "Test Candidate"},
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
        return application["id"]

    async def _advance(application_id: str, *statuses: str) -> None:
        for status in statuses:
            response = await client.post(
                f"/api/v1/recruiter/applications/{application_id}/status",
                json={"to_status": status},
                headers=headers,
            )
            assert response.status_code == 200, response.text

    selected_id = await _application("selected@reports-outcomes.dev")
    await _advance(selected_id, "UNDER_REVIEW", "SCREENING", "SHORTLISTED", "INTERVIEW", "SELECTED")

    rejected_id = await _application("rejected@reports-outcomes.dev")
    await _advance(rejected_id, "UNDER_REVIEW", "REJECTED")

    hired_id = await _application("hired@reports-outcomes.dev")
    await _advance(hired_id, "UNDER_REVIEW", "SCREENING", "SHORTLISTED", "INTERVIEW", "SELECTED", "HIRED")

    # A rejected application that's then soft-deleted must not be counted.
    deleted_rejected_id = await _application("deleted-rejected@reports-outcomes.dev")
    await _advance(deleted_rejected_id, "UNDER_REVIEW", "REJECTED")
    delete_response = await client.post(
        f"/api/v1/recruiter/applications/{deleted_rejected_id}/delete",
        json={"reason": "Duplicate entry"},
        headers=headers,
    )
    assert delete_response.status_code == 200, delete_response.text

    report = (await client.get("/api/v1/recruiter/reports/overview", headers=headers)).json()
    assert report["selected_candidates"] == 1
    assert report["rejected_candidates"] == 1
    assert report["hired_candidates"] == 1


async def test_reports_are_tenant_scoped(client: AsyncClient, super_admin: User) -> None:
    org_a = await _bootstrap_org(client, "reports-tenant-a")
    org_b = await _bootstrap_org(client, "reports-tenant-b")

    await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Org A Job", "description": "..."},
        headers=org_a["headers"],
    )

    report_b = (
        await client.get("/api/v1/recruiter/reports/overview", headers=org_b["headers"])
    ).json()
    assert report_b["total_jobs"] == 0


async def test_reports_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/recruiter/reports/overview")
    assert response.status_code == 401

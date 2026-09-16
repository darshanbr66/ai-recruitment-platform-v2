"""Recruiter-facing Application creation and status workflow (Phase 3) —
see docs/recruitment-workflow.md § 2. The transition table itself is
exercised directly; here we confirm the HTTP layer enforces it."""

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


async def _create_job(client: AsyncClient, headers: dict) -> str:
    response = await client.post(
        "/api/v1/recruiter/jobs",
        json={
            "title": "Backend Engineer",
            "description": "Build the platform.",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _create_candidate(client: AsyncClient, headers: dict, email: str) -> str:
    response = await client.post(
        "/api/v1/recruiter/candidates",
        json={"email": email, "full_name": "Cara Candidate"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_creating_an_application_links_candidate_and_job_and_starts_applied(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "applications-happy-path")
    headers = await _org_admin_headers(client, org)
    job_id = await _create_job(client, headers)
    candidate_id = await _create_candidate(
        client, headers, "cara@applications-happy-path-candidate.dev"
    )

    response = await client.post(
        "/api/v1/recruiter/applications",
        json={"candidate_id": candidate_id, "job_id": job_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "APPLIED"
    assert body["candidate_full_name"] == "Cara Candidate"
    assert body["job_title"] == "Backend Engineer"


async def test_duplicate_application_for_same_candidate_and_job_is_rejected(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "applications-duplicate")
    headers = await _org_admin_headers(client, org)
    job_id = await _create_job(client, headers)
    candidate_id = await _create_candidate(
        client, headers, "cara@applications-duplicate-candidate.dev"
    )
    payload = {"candidate_id": candidate_id, "job_id": job_id}

    first = await client.post("/api/v1/recruiter/applications", json=payload, headers=headers)
    assert first.status_code == 201

    second = await client.post("/api/v1/recruiter/applications", json=payload, headers=headers)
    assert second.status_code == 409


async def test_legal_status_transition_is_recorded(client: AsyncClient, super_admin: User) -> None:
    org = await _bootstrap_org(client, "applications-transition")
    headers = await _org_admin_headers(client, org)
    job_id = await _create_job(client, headers)
    candidate_id = await _create_candidate(
        client, headers, "cara@applications-transition-candidate.dev"
    )
    application_id = (
        await client.post(
            "/api/v1/recruiter/applications",
            json={"candidate_id": candidate_id, "job_id": job_id},
            headers=headers,
        )
    ).json()["id"]

    response = await client.post(
        f"/api/v1/recruiter/applications/{application_id}/status",
        json={"to_status": "UNDER_REVIEW"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "UNDER_REVIEW"


async def test_illegal_status_transition_is_rejected(
    client: AsyncClient, super_admin: User
) -> None:
    """APPLIED can only move to UNDER_REVIEW or WITHDRAWN — jumping straight
    to SELECTED must be rejected (docs/recruitment-workflow.md § 2)."""
    org = await _bootstrap_org(client, "applications-illegal-transition")
    headers = await _org_admin_headers(client, org)
    job_id = await _create_job(client, headers)
    candidate_id = await _create_candidate(
        client, headers, "cara@applications-illegal-transition-candidate.dev"
    )
    application_id = (
        await client.post(
            "/api/v1/recruiter/applications",
            json={"candidate_id": candidate_id, "job_id": job_id},
            headers=headers,
        )
    ).json()["id"]

    response = await client.post(
        f"/api/v1/recruiter/applications/{application_id}/status",
        json={"to_status": "SELECTED"},
        headers=headers,
    )
    assert response.status_code == 409


async def test_terminal_status_cannot_be_transitioned_out_of(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "applications-terminal")
    headers = await _org_admin_headers(client, org)
    job_id = await _create_job(client, headers)
    candidate_id = await _create_candidate(
        client, headers, "cara@applications-terminal-candidate.dev"
    )
    application_id = (
        await client.post(
            "/api/v1/recruiter/applications",
            json={"candidate_id": candidate_id, "job_id": job_id},
            headers=headers,
        )
    ).json()["id"]

    withdraw = await client.post(
        f"/api/v1/recruiter/applications/{application_id}/status",
        json={"to_status": "WITHDRAWN"},
        headers=headers,
    )
    assert withdraw.status_code == 200

    revive = await client.post(
        f"/api/v1/recruiter/applications/{application_id}/status",
        json={"to_status": "UNDER_REVIEW"},
        headers=headers,
    )
    assert revive.status_code == 409


async def test_interviewer_can_view_but_not_change_application_status(
    client: AsyncClient, super_admin: User
) -> None:
    org = await _bootstrap_org(client, "applications-interviewer")
    admin_headers = await _org_admin_headers(client, org)
    job_id = await _create_job(client, admin_headers)
    candidate_id = await _create_candidate(
        client, admin_headers, "cara@applications-interviewer-candidate.dev"
    )
    application_id = (
        await client.post(
            "/api/v1/recruiter/applications",
            json={"candidate_id": candidate_id, "job_id": job_id},
            headers=admin_headers,
        )
    ).json()["id"]

    await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": "interviewer@applications-interviewer.dev",
            "password": "SomePassword1",
            "full_name": "Ivy Interviewer",
            "role": "INTERVIEWER",
        },
        headers=admin_headers,
    )
    interviewer_tokens = await login(
        client, email="interviewer@applications-interviewer.dev", password="SomePassword1"
    )
    interviewer_headers = {"Authorization": f"Bearer {interviewer_tokens['access_token']}"}

    read_response = await client.get(
        f"/api/v1/recruiter/applications/{application_id}", headers=interviewer_headers
    )
    assert read_response.status_code == 200

    status_response = await client.post(
        f"/api/v1/recruiter/applications/{application_id}/status",
        json={"to_status": "UNDER_REVIEW"},
        headers=interviewer_headers,
    )
    assert status_response.status_code == 403


async def test_application_for_a_candidate_from_another_org_is_rejected(
    client: AsyncClient, super_admin: User
) -> None:
    org_a = await _bootstrap_org(client, "applications-cross-tenant-a")
    org_b = await _bootstrap_org(client, "applications-cross-tenant-b")
    headers_a = await _org_admin_headers(client, org_a)
    headers_b = await _org_admin_headers(client, org_b)

    job_id_a = await _create_job(client, headers_a)
    candidate_id_b = await _create_candidate(
        client, headers_b, "cara@applications-cross-tenant-b-candidate.dev"
    )

    response = await client.post(
        "/api/v1/recruiter/applications",
        json={"candidate_id": candidate_id_b, "job_id": job_id_a},
        headers=headers_a,
    )
    assert response.status_code == 404

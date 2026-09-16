"""AI screening: real orchestration (extraction -> provider -> persistence),
with the LLM provider itself mocked at the one legitimate boundary — an
external paid API call is exactly the "real integration impractical in test
scope" case CLAUDE.md § 5 carves out. No other layer is mocked."""

import pytest
from httpx import AsyncClient

from app.integrations.ai.base import AIProviderError, ScreeningVerdict
from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login, make_minimal_pdf

_JOB_PAYLOAD = {
    "title": "Backend Engineer",
    "description": "We need someone strong in Python and PostgreSQL.",
}


async def _bootstrap_org_with_applied_application(client: AsyncClient, slug: str) -> dict:
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
        await client.post("/api/v1/recruiter/jobs", json=_JOB_PAYLOAD, headers=headers)
    ).json()
    await client.patch(
        f"/api/v1/recruiter/jobs/{job['id']}", json={"status": "OPEN"}, headers=headers
    )

    resume_bytes = make_minimal_pdf("Jane Candidate. Skills: Python, PostgreSQL, FastAPI.")
    apply_response = await client.post(
        f"/api/v1/public/organizations/{slug}/jobs/{job['id']}/apply",
        data={"full_name": "Jane Candidate", "email": "jane@example.com"},
        files={"resume": ("resume.pdf", resume_bytes, "application/pdf")},
    )
    application_id = apply_response.json()["id"]

    return {"headers": headers, "job": job, "application_id": application_id}


class _FakeSuccessProvider:
    name = "fake"
    model = "fake-model"

    async def screen_candidate(self, *, resume_text, job_title, job_description):
        return ScreeningVerdict(
            overall_score=82,
            recommendation="STRONG_MATCH",
            summary="Strong candidate for this role.",
            matching_skills=["Python", "PostgreSQL"],
            missing_skills=["Kubernetes"],
            strengths=["Deep backend experience"],
            concerns=["No cloud infra experience listed"],
            experience_assessment="5 years of relevant experience.",
            education_assessment="BS in Computer Science.",
        )


class _FakeFailingProvider:
    name = "fake"
    model = "fake-model"

    async def screen_candidate(self, *, resume_text, job_title, job_description):
        raise AIProviderError("The model timed out.")


@pytest.fixture
def mock_successful_provider(monkeypatch):
    monkeypatch.setattr(
        "app.services.screening_service.get_llm_provider", lambda: _FakeSuccessProvider()
    )


@pytest.fixture
def mock_failing_provider(monkeypatch):
    monkeypatch.setattr(
        "app.services.screening_service.get_llm_provider", lambda: _FakeFailingProvider()
    )


async def test_screening_persists_structured_result(
    client: AsyncClient, super_admin: User, mock_successful_provider
) -> None:
    ctx = await _bootstrap_org_with_applied_application(client, "screening-happy")

    response = await client.post(
        f"/api/v1/recruiter/applications/{ctx['application_id']}/screening",
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["overall_score"] == 82
    assert body["recommendation"] == "STRONG_MATCH"
    assert "Python" in body["matching_skills"]
    assert body["provider"] == "fake"

    listing = await client.get(
        f"/api/v1/recruiter/applications/{ctx['application_id']}/screening",
        headers=ctx["headers"],
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_screening_failure_is_recorded_not_fabricated(
    client: AsyncClient, super_admin: User, mock_failing_provider
) -> None:
    ctx = await _bootstrap_org_with_applied_application(client, "screening-fail")

    response = await client.post(
        f"/api/v1/recruiter/applications/{ctx['application_id']}/screening",
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["overall_score"] is None
    assert "timed out" in body["error_message"]


async def test_screening_without_a_configured_provider_fails_honestly(
    client: AsyncClient, super_admin: User
) -> None:
    """No monkeypatch here — this exercises the real, unconfigured path."""
    ctx = await _bootstrap_org_with_applied_application(client, "screening-unconfigured")

    response = await client.post(
        f"/api/v1/recruiter/applications/{ctx['application_id']}/screening",
        headers=ctx["headers"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "FAILED"
    assert "No AI provider is configured" in body["error_message"]


async def test_screening_requires_an_existing_resume(
    client: AsyncClient, super_admin: User, mock_successful_provider
) -> None:
    ctx = await _bootstrap_org_with_applied_application(client, "screening-no-resume")

    candidate = (
        await client.post(
            "/api/v1/recruiter/candidates",
            json={"email": "no-resume@example.com", "full_name": "No Resume"},
            headers=ctx["headers"],
        )
    ).json()
    application = (
        await client.post(
            "/api/v1/recruiter/applications",
            json={"candidate_id": candidate["id"], "job_id": ctx["job"]["id"]},
            headers=ctx["headers"],
        )
    ).json()

    response = await client.post(
        f"/api/v1/recruiter/applications/{application['id']}/screening",
        headers=ctx["headers"],
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "no_resume"


async def test_screening_requires_permission(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_applied_application(client, "screening-no-permission")

    await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": "interviewer@screening-no-permission.dev",
            "password": "SomePassword1",
            "full_name": "Ivy Interviewer",
            "role": "INTERVIEWER",
        },
        headers=ctx["headers"],
    )
    interviewer_tokens = await login(
        client, email="interviewer@screening-no-permission.dev", password="SomePassword1"
    )

    response = await client.post(
        f"/api/v1/recruiter/applications/{ctx['application_id']}/screening",
        headers={"Authorization": f"Bearer {interviewer_tokens['access_token']}"},
    )
    assert response.status_code == 403

"""Email must never fake success, and — because candidate email is manual
only — never gets in the way of a workflow action (CLAUDE.md § 2: "Email
provider != business logic"). Applying and changing status work with no
email provider configured at all."""

from httpx import AsyncClient

from app.integrations.email import UnconfiguredEmailProvider, get_email_provider
from app.integrations.email.base import EmailNotConfiguredError
from app.models.user import User
from app.services import notification_service
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login
from tests.public_apply import apply_publicly


async def test_unconfigured_provider_raises_rather_than_faking_success() -> None:
    provider = get_email_provider()
    assert isinstance(provider, UnconfiguredEmailProvider)

    raised = False
    try:
        await provider.send(to="a@example.com", subject="Hi", html="<p>Hi</p>")
    except EmailNotConfiguredError:
        raised = True
    assert raised


async def test_sending_without_a_configured_provider_raises_rather_than_faking_success() -> None:
    raised = False
    try:
        await notification_service.send_email(
            to=["candidate@example.com"], subject="Hi", html="<p>Hi</p>", text="Hi"
        )
    except EmailNotConfiguredError:
        raised = True
    assert raised


async def test_apply_with_unconfigured_email_still_succeeds(
    client: AsyncClient, super_admin: User
) -> None:
    """A candidate's application must go through even though no email
    provider is configured in this test environment."""
    super_admin_tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    org_payload = {
        "name": "Acme Corp",
        "slug": "notif-apply-flow",
        "admin_email": "admin@notif-apply-flow.dev",
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
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    job = (
        await client.post(
            "/api/v1/recruiter/jobs",
            json={"title": "Backend Engineer", "description": "Build things."},
            headers=admin_headers,
        )
    ).json()
    await client.patch(
        f"/api/v1/recruiter/jobs/{job['id']}", json={"status": "OPEN"}, headers=admin_headers
    )

    response = await apply_publicly(
        client, org_payload["slug"], job["id"], email="jane@example.com"
    )
    assert response.status_code == 201, response.text


async def test_status_change_with_unconfigured_email_still_succeeds(
    client: AsyncClient, super_admin: User
) -> None:
    super_admin_tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    org_payload = {
        "name": "Acme Corp",
        "slug": "notif-status-flow",
        "admin_email": "admin@notif-status-flow.dev",
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
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    job = (
        await client.post(
            "/api/v1/recruiter/jobs",
            json={"title": "Backend Engineer", "description": "Build things."},
            headers=admin_headers,
        )
    ).json()
    candidate = (
        await client.post(
            "/api/v1/recruiter/candidates",
            json={"email": "c1@example.com", "full_name": "Cara Candidate"},
            headers=admin_headers,
        )
    ).json()
    application = (
        await client.post(
            "/api/v1/recruiter/applications",
            json={"candidate_id": candidate["id"], "job_id": job["id"]},
            headers=admin_headers,
        )
    ).json()

    response = await client.post(
        f"/api/v1/recruiter/applications/{application['id']}/status",
        json={"to_status": "UNDER_REVIEW"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "UNDER_REVIEW"

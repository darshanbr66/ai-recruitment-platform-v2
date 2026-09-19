"""General (non-application) email: any authorized recruiter/admin can send a
professional templated email to addresses they type — with the same manual-only
rule, RBAC, tenant isolation, honest failures and audit as application email."""

import smtplib

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations import email as email_module
from app.integrations.email import EmailError
from app.models.user import User
from app.services import notification_service
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, RecordingEmailProvider, login
from tests.test_applications import _org_admin_headers
from tests.test_email_workflow import _staff_headers

_URL = "/api/v1/recruiter/email"
_DUMMY_SMTP_PASSWORD = "dummy-test-password-not-real"


async def _org(client: AsyncClient, slug: str, name: str = "Acme Corp") -> dict:
    """An organization (with the given display name) + its admin headers."""
    super_tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    org = {
        "name": name,
        "slug": slug,
        "admin_email": f"admin@{slug}.dev",
        "admin_password": "AcmeAdminPass1",
        "admin_full_name": f"{name.split()[0]} Admin",
    }
    created = await client.post(
        "/api/v1/admin/organizations",
        json=org,
        headers={"Authorization": f"Bearer {super_tokens['access_token']}"},
    )
    assert created.status_code == 201, created.text
    return {"org": org, "headers": await _org_admin_headers(client, org)}


async def _compose(client: AsyncClient, headers: dict, key: str, variables=None):
    return await client.post(
        f"{_URL}/compose",
        json={"template_key": key, "variables": variables or {}},
        headers=headers,
    )


def _draft(composed: dict, **overrides) -> dict:
    return {
        "template_key": composed["template_key"],
        "subject": composed["subject"],
        "body": composed["body"],
        "variables": composed["variables"],
        "to": ["hr.partner@example.com"],
        **overrides,
    }


async def _activities(client: AsyncClient, headers: dict) -> list[dict]:
    return (await client.get("/api/v1/recruiter/activities", headers=headers)).json()


# --- templates & placeholders -------------------------------------------------


async def test_template_listing_marks_which_templates_work_without_an_application(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org(client, "gen-template-list")

    templates = {
        t["key"]: t
        for t in (await client.get("/api/v1/recruiter/email-templates", headers=ctx["headers"])).json()
    }

    assert templates["ASSESSMENT_INVITATION"]["general_fields"] is None
    for key in ("APPLICATION_RECEIVED", "INTERVIEW_INVITATION", "NEXT_STEPS", "REJECTION", "GENERAL"):
        general = {f["key"]: f for f in templates[key]["general_fields"]}
        assert "candidate_name" in general and general["candidate_name"]["required"] is False
    role = {f["key"]: f for f in templates["REJECTION"]["general_fields"]}["job_title"]
    assert role["required"] is True
    # The General template only mentions a role on an optional line.
    general_message = {f["key"]: f for f in templates["GENERAL"]["general_fields"]}
    assert general_message["job_title"]["required"] is False


async def test_general_compose_fills_company_and_recruiter_and_falls_back_for_the_name(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org(client, "gen-compose")

    composed = (await _compose(client, ctx["headers"], "GENERAL")).json()

    assert composed["subject"] == "A message from Acme Corp"
    assert composed["missing_required"] == []
    assert "Dear Sir or Madam," in composed["body"]
    assert "on behalf of Acme Corp" in composed["body"]
    assert "Acme Admin" in composed["body"]  # signed-in sender
    # No role given -> the role sentence is dropped, nothing raw left behind.
    assert "{{" not in composed["subject"] + composed["body"]
    assert "position" not in composed["body"]


async def test_general_compose_uses_the_recipient_name_and_role_when_given(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org(client, "gen-compose-vars")

    composed = (
        await _compose(
            client,
            ctx["headers"],
            "REJECTION",
            {"candidate_name": "Dana Recipient", "job_title": "Data Analyst"},
        )
    ).json()

    assert composed["subject"] == "Application Update – Data Analyst"
    assert "Dear Dana Recipient," in composed["body"]
    assert "Data Analyst position at Acme Corp" in composed["body"]
    assert composed["missing_required"] == []


async def test_a_template_that_needs_information_asks_for_it_and_blocks_sending(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    ctx = await _org(client, "gen-required")

    composed = (await _compose(client, ctx["headers"], "APPLICATION_RECEIVED")).json()

    assert composed["missing_required"] == ["job_title"]
    assert "{{job_title}}" in composed["body"]
    blocked = await client.post(f"{_URL}/send", json=_draft(composed), headers=ctx["headers"])
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "unresolved_placeholders"
    assert recording_email.sent == []


async def test_assessment_invitation_cannot_be_sent_without_an_application(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    ctx = await _org(client, "gen-assessment")

    response = await _compose(client, ctx["headers"], "ASSESSMENT_INVITATION")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "template_requires_application"
    assert recording_email.sent == []


async def test_interview_invitation_works_for_a_general_recipient(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    ctx = await _org(client, "gen-interview")
    variables = {
        "job_title": "Backend Engineer",
        "interview_date": "2026-09-25",
        "interview_time": "14:30",
        "interview_mode": "Video call",
        "meeting_link": "https://meet.example.com/abc",
    }
    composed = (await _compose(client, ctx["headers"], "INTERVIEW_INVITATION", variables)).json()

    preview = (
        await client.post(f"{_URL}/preview", json=_draft(composed), headers=ctx["headers"])
    ).json()

    assert composed["missing_required"] == []
    assert preview["has_call_to_action"] is True
    assert 'href="https://meet.example.com/abc"' in preview["html"]
    assert "Friday, 25 September 2026" in preview["html"]
    # Not an application email, so the footer doesn't claim it is about one.
    assert "regarding your application" not in preview["html"]
    assert "You are receiving this message from Acme Corp." in preview["html"]


# --- send: recipients, edits, audit -------------------------------------------


async def test_admin_can_preview_and_send_with_to_cc_and_bcc(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    ctx = await _org(client, "gen-send")
    composed = (await _compose(client, ctx["headers"], "GENERAL")).json()
    body = composed["body"] + "\n\nSECRET-BODY-MARKER: please review the attached offer."
    draft = _draft(
        composed,
        subject="Welcome to the team",
        body=body,
        to=["a@example.com", "b@example.com"],
        cc=["c@example.com"],
        bcc=["d@example.com"],
    )

    preview = await client.post(f"{_URL}/preview", json=draft, headers=ctx["headers"])
    assert preview.status_code == 200, preview.text
    assert preview.json()["to"] == ["a@example.com", "b@example.com"]
    assert preview.json()["html"].startswith("<!DOCTYPE html>")
    assert recording_email.sent == []  # previewing never sends

    sent = await client.post(f"{_URL}/send", json=draft, headers=ctx["headers"])

    assert sent.status_code == 200, sent.text
    assert sent.json() == {
        "sent": True,
        "to": ["a@example.com", "b@example.com"],
        "cc": ["c@example.com"],
        "bcc": ["d@example.com"],
        "subject": "Welcome to the team",
    }
    (email,) = recording_email.sent
    assert (email.to, email.cc, email.bcc) == (
        ["a@example.com", "b@example.com"],
        ["c@example.com"],
        ["d@example.com"],
    )
    assert email.subject == "Welcome to the team"
    assert email.reply_to == "admin@gen-send.dev"  # the sender, so replies reach them
    assert "SECRET-BODY-MARKER" in email.html and "SECRET-BODY-MARKER" in email.text


async def test_general_send_is_audited_without_the_body(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    ctx = await _org(client, "gen-audit")
    composed = (await _compose(client, ctx["headers"], "GENERAL")).json()
    draft = _draft(
        composed,
        subject="Quarterly hiring plan",
        body=composed["body"] + "\n\nSENSITIVE-DETAIL-1234",
        to=["a@example.com"],
        cc=["c@example.com"],
        bcc=["hidden@example.com"],
    )

    await client.post(f"{_URL}/send", json=draft, headers=ctx["headers"])

    (entry,) = [a for a in await _activities(client, ctx["headers"]) if a["action"] == "GENERAL_EMAIL_SENT"]
    assert entry["actor_name"] == "Acme Admin"
    assert entry["entity_type"] == "email"
    assert entry["entity_id"] is None
    description = entry["description"]
    assert "Quarterly hiring plan" in description
    assert "General recruitment message" in description  # template used
    for address in ("a@example.com", "c@example.com", "hidden@example.com"):
        assert address in description
    assert "SENSITIVE-DETAIL-1234" not in description  # never the body
    assert "SENSITIVE-DETAIL-1234" not in str(entry)


async def test_editing_an_email_never_changes_the_template(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    ctx = await _org(client, "gen-edit")
    first = (await _compose(client, ctx["headers"], "GENERAL")).json()
    await client.post(
        f"{_URL}/send",
        json=_draft(first, subject="Totally different", body="Just this one custom message."),
        headers=ctx["headers"],
    )

    again = (await _compose(client, ctx["headers"], "GENERAL")).json()

    assert again["subject"] == first["subject"] == "A message from Acme Corp"
    assert again["body"] == first["body"]
    assert recording_email.sent[0].subject == "Totally different"


# --- recipient validation ---------------------------------------------------


@pytest.mark.parametrize(
    "recipients",
    [
        {"to": []},
        {"to": ["not-an-email"]},
        {"to": ["victim@example.com\nBcc: attacker@example.com"]},
        {"to": ["a@example.com"], "cc": ["nope"]},
        {"to": ["a@example.com"], "bcc": ["a b@example.com"]},
        {"to": [f"user{i}@example.com" for i in range(11)]},
        {
            "to": [f"to{i}@example.com" for i in range(10)],
            "cc": [f"cc{i}@example.com" for i in range(10)],
            "bcc": ["extra@example.com"],
        },
    ],
)
async def test_invalid_or_excessive_recipients_are_rejected(
    client: AsyncClient,
    super_admin: User,
    recording_email: RecordingEmailProvider,
    recipients: dict,
) -> None:
    ctx = await _org(client, "gen-recipients")
    composed = (await _compose(client, ctx["headers"], "GENERAL")).json()

    for action in ("preview", "send"):
        response = await client.post(
            f"{_URL}/{action}", json={**_draft(composed), **recipients}, headers=ctx["headers"]
        )
        assert response.status_code == 422, (action, recipients, response.text)
    assert recording_email.sent == []


async def test_a_pasted_display_name_is_reduced_to_the_bare_address(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    ctx = await _org(client, "gen-display-name")
    composed = (await _compose(client, ctx["headers"], "GENERAL")).json()

    await client.post(
        f"{_URL}/send",
        json=_draft(composed, to=["Dana Recipient <dana@example.com>"]),
        headers=ctx["headers"],
    )

    (email,) = recording_email.sent
    assert email.to == ["dana@example.com"]  # the name is discarded, never put in a header


async def test_duplicate_addresses_are_removed_across_to_cc_and_bcc(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    ctx = await _org(client, "gen-dedupe")
    composed = (await _compose(client, ctx["headers"], "GENERAL")).json()

    await client.post(
        f"{_URL}/send",
        json=_draft(
            composed,
            to=["A@Example.com", "a@example.com"],
            cc=["a@example.com", "b@example.com"],
            bcc=["B@example.com", "c@example.com"],
        ),
        headers=ctx["headers"],
    )

    (email,) = recording_email.sent
    assert (email.to, email.cc, email.bcc) == (["A@example.com"], ["b@example.com"], ["c@example.com"])


# --- authorization & tenant isolation -----------------------------------------


async def test_recruiter_can_send_but_hiring_manager_and_interviewer_cannot(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    ctx = await _org(client, "gen-authz")
    composed = (await _compose(client, ctx["headers"], "GENERAL")).json()
    draft = _draft(composed)

    recruiter = await _staff_headers(client, ctx["headers"], "gen-authz", "RECRUITER")
    assert (await client.post(f"{_URL}/send", json=draft, headers=recruiter)).status_code == 200
    assert len(recording_email.sent) == 1

    for role in ("HIRING_MANAGER", "INTERVIEWER"):
        headers = await _staff_headers(client, ctx["headers"], "gen-authz", role)
        for action, body in (
            ("compose", {"template_key": "GENERAL", "variables": {}}),
            ("preview", draft),
            ("send", draft),
        ):
            response = await client.post(f"{_URL}/{action}", json=body, headers=headers)
            assert response.status_code == 403, (role, action)
    anonymous = await client.post(f"{_URL}/send", json=draft)
    assert anonymous.status_code == 401
    assert len(recording_email.sent) == 1  # nothing beyond the recruiter's send


async def test_general_email_is_scoped_to_the_senders_own_organization(
    client: AsyncClient, super_admin: User, recording_email: RecordingEmailProvider
) -> None:
    a = await _org(client, "gen-tenant-a", "Acme Corp")
    b = await _org(client, "gen-tenant-b", "Globex Industries")
    composed_b = (await _compose(client, b["headers"], "GENERAL")).json()
    assert "Globex Industries" in composed_b["body"] and "Acme" not in composed_b["body"]

    # B's admin tries to send as "A" by naming another organization in the request.
    smuggled = {
        **_draft(composed_b, to=["x@example.com"]),
        "organization_id": "anything",
        "company_name": "Acme Corp",
    }
    response = await client.post(f"{_URL}/send", json=smuggled, headers=b["headers"])

    assert response.status_code == 200, response.text
    (email,) = recording_email.sent
    assert email.reply_to == "admin@gen-tenant-b.dev"
    assert "Globex Industries" in email.html
    assert "Acme" not in email.html and "Acme" not in email.text
    # The audit entry lands in the sender's own organization only.
    b_actions = [e["action"] for e in await _activities(client, b["headers"])]
    a_actions = [e["action"] for e in await _activities(client, a["headers"])]
    assert "GENERAL_EMAIL_SENT" in b_actions
    assert "GENERAL_EMAIL_SENT" not in a_actions


# --- failures ----------------------------------------------------------------


async def test_provider_failure_returns_an_honest_error_and_is_audited(
    client: AsyncClient, super_admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = RecordingEmailProvider(error=EmailError("Could not deliver the email."))
    monkeypatch.setattr(notification_service, "get_email_provider", lambda: provider)
    ctx = await _org(client, "gen-failure")
    composed = (await _compose(client, ctx["headers"], "GENERAL")).json()

    response = await client.post(f"{_URL}/send", json=_draft(composed), headers=ctx["headers"])

    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "email_delivery_failed"
    actions = [a["action"] for a in await _activities(client, ctx["headers"])]
    assert "GENERAL_EMAIL_FAILED" in actions
    assert "GENERAL_EMAIL_SENT" not in actions


async def test_unconfigured_smtp_returns_a_configuration_error(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org(client, "gen-unconfigured")
    composed = (await _compose(client, ctx["headers"], "GENERAL")).json()

    response = await client.post(f"{_URL}/send", json=_draft(composed), headers=ctx["headers"])

    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "email_not_configured"


async def test_no_smtp_configuration_or_credentials_are_ever_exposed(
    client: AsyncClient,
    super_admin: User,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret_key="x" * 32,
        smtp_host="smtp.example.test",
        smtp_username="sender@example.test",
        smtp_password=SecretStr(_DUMMY_SMTP_PASSWORD),
        smtp_from_email="sender@example.test",
    )
    monkeypatch.setattr(email_module, "get_settings", lambda: settings)

    class _RejectingSmtp:
        def __init__(self, *args: object, **kwargs: object) -> None: ...
        def __enter__(self) -> "_RejectingSmtp":
            return self
        def __exit__(self, *exc: object) -> None:
            return None
        def starttls(self, **kwargs: object) -> None: ...
        def login(self, username: str, password: str) -> None:
            raise smtplib.SMTPAuthenticationError(535, f"bad credentials {password}".encode())

    monkeypatch.setattr(smtplib, "SMTP", _RejectingSmtp)
    ctx = await _org(client, "gen-secrets")
    composed = await _compose(client, ctx["headers"], "GENERAL")
    draft = _draft(composed.json())

    templates = await client.get("/api/v1/recruiter/email-templates", headers=ctx["headers"])
    preview = await client.post(f"{_URL}/preview", json=draft, headers=ctx["headers"])
    failed = await client.post(f"{_URL}/send", json=draft, headers=ctx["headers"])
    activities = await client.get("/api/v1/recruiter/activities", headers=ctx["headers"])

    assert failed.status_code == 502
    for response in (composed, templates, preview, failed, activities):
        assert _DUMMY_SMTP_PASSWORD not in response.text
        assert "smtp.example.test" not in response.text
        assert "sender@example.test" not in response.text
    assert _DUMMY_SMTP_PASSWORD not in caplog.text
    # A client can't supply SMTP settings either: unknown fields are ignored.
    hostile = {**draft, "smtp_host": "evil.example.com", "smtp_password": "x"}
    assert (await client.post(f"{_URL}/preview", json=hostile, headers=ctx["headers"])).status_code == 200

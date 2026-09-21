"""In-app notifications for assessment start/submission: the inviter — and only
the inviter — is notified once per event, tenant-isolated, acknowledged by the
recipient. Distinct from tests/test_notifications.py, which covers *email*."""

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.rls import rls_bypass, set_tenant_context
from app.models.assessment import AssessmentInvitation
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.services import in_app_notification_service
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login
from tests.test_assessments import (
    _ASSESSMENT_PAYLOAD,
    _bootstrap_org_with_screening_application,
    _extract_token,
)

_NOTIFICATIONS = "/api/v1/recruiter/notifications"


async def _create_recruiter(client: AsyncClient, admin_headers: dict, email: str) -> dict:
    created = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": email,
            "password": "RecruiterPass1",
            "full_name": "Riley Recruiter",
            "role": "RECRUITER",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    tokens = await login(client, email=email, password="RecruiterPass1")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _invite(client: AsyncClient, ctx: dict, *, as_headers: dict | None = None) -> dict:
    """Creates the assessment and sends the invitation as `as_headers` (the
    org admin by default). Returns the invitation token and the assessment."""
    assessment = (
        await client.post(
            "/api/v1/recruiter/assessments", json=_ASSESSMENT_PAYLOAD, headers=ctx["headers"]
        )
    ).json()
    invitation = await client.post(
        "/api/v1/recruiter/assessments/invite",
        json={"assessment_id": assessment["id"], "application_id": ctx["application_id"]},
        headers=as_headers or ctx["headers"],
    )
    assert invitation.status_code == 201, invitation.text
    return {
        "token": _extract_token(invitation.json()["invitation_link"]),
        "assessment": assessment,
    }


def _correct_answers(assessment: dict) -> list[dict]:
    return [
        {
            "question_id": question["id"],
            "selected_option_ids": [o["id"] for o in question["options"] if o["is_correct"]],
        }
        for question in assessment["questions"]
    ]


async def _submit(client: AsyncClient, invite: dict):
    # Question ids are the same in the candidate view and the recruiter payload.
    return await client.post(
        f"/api/v1/public/assessment/{invite['token']}/submit",
        json={"answers": _correct_answers(invite["assessment"])},
    )


async def _unread(client: AsyncClient, headers: dict) -> list[dict]:
    response = await client.get(_NOTIFICATIONS, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_start_creates_a_notification_for_the_inviter(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_screening_application(client, "notif-start")
    invite = await _invite(client, ctx)
    assert await _unread(client, ctx["headers"]) == []

    start = await client.post(f"/api/v1/public/assessment/{invite['token']}/start")
    assert start.status_code == 200

    notifications = await _unread(client, ctx["headers"])
    assert len(notifications) == 1
    assert notifications[0]["type"] == "ASSESSMENT_STARTED"
    assert notifications[0]["title"] == "Assessment started"
    assert notifications[0]["message"] == "Jane Candidate has started the Python Basics assessment."
    assert notifications[0]["read_at"] is None
    # Privacy: only what the toast shows — no invitation id, email or token.
    assert set(notifications[0]) == {"id", "type", "title", "message", "created_at", "read_at"}
    assert "jane@example.com" not in str(notifications[0])
    assert invite["token"] not in str(notifications[0])


async def test_submission_creates_a_notification_for_the_inviter(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_screening_application(client, "notif-submit")
    invite = await _invite(client, ctx)
    await client.post(f"/api/v1/public/assessment/{invite['token']}/start")

    submit = await _submit(client, invite)
    assert submit.status_code == 200, submit.text

    # Not asserting order: `now()` is the transaction start time and this whole
    # test is one transaction, so both rows share a created_at. In production
    # start and submit are separate requests with distinct timestamps.
    notifications = {n["type"]: n for n in await _unread(client, ctx["headers"])}
    assert set(notifications) == {"ASSESSMENT_STARTED", "ASSESSMENT_SUBMITTED"}
    submitted = notifications["ASSESSMENT_SUBMITTED"]
    assert submitted["title"] == "Assessment submitted"
    assert submitted["message"] == "Jane Candidate has submitted the Python Basics assessment."
    # The candidate-facing result is unchanged: still no score.
    assert set(submit.json()) == {"submitted_at"}


async def test_only_the_inviting_recruiter_is_notified_not_the_org_admin(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_screening_application(client, "notif-inviter")
    recruiter_headers = await _create_recruiter(client, ctx["headers"], "riley@notif-inviter.dev")
    other_recruiter_headers = await _create_recruiter(
        client, ctx["headers"], "other@notif-inviter.dev"
    )
    invite = await _invite(client, ctx, as_headers=recruiter_headers)

    await client.post(f"/api/v1/public/assessment/{invite['token']}/start")
    await _submit(client, invite)

    assert sorted(n["type"] for n in await _unread(client, recruiter_headers)) == [
        "ASSESSMENT_STARTED",
        "ASSESSMENT_SUBMITTED",
    ]
    # Same organization, different people: nothing is broadcast.
    assert await _unread(client, ctx["headers"]) == []
    assert await _unread(client, other_recruiter_headers) == []


async def test_another_organization_cannot_see_the_notification(
    client: AsyncClient, super_admin: User, db_session: AsyncSession
) -> None:
    ctx_a = await _bootstrap_org_with_screening_application(client, "notif-org-a")
    ctx_b = await _bootstrap_org_with_screening_application(client, "notif-org-b")
    invite = await _invite(client, ctx_a)
    await client.post(f"/api/v1/public/assessment/{invite['token']}/start")

    notification_id = (await _unread(client, ctx_a["headers"]))[0]["id"]

    assert await _unread(client, ctx_b["headers"]) == []
    # Acknowledging another tenant's id is a no-op, not an error and not a leak.
    foreign_ack = await client.post(
        f"{_NOTIFICATIONS}/read", json={"ids": [notification_id]}, headers=ctx_b["headers"]
    )
    assert foreign_ack.status_code == 200
    assert foreign_ack.json() == {"updated": 0}
    assert len(await _unread(client, ctx_a["headers"])) == 1

    # And the database itself hides the row from another tenant (RLS), not
    # just the API filter.
    async with rls_bypass(db_session):
        org_b_id = (
            await db_session.execute(
                select(User.organization_id).where(User.email == "admin@notif-org-b.dev")
            )
        ).scalar_one()
    await set_tenant_context(db_session, org_b_id)
    visible_to_b = await db_session.scalar(select(func.count()).select_from(Notification))
    assert visible_to_b == 0


async def test_repeated_start_requests_create_only_one_notification(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_screening_application(client, "notif-dup-start")
    invite = await _invite(client, ctx)

    for _ in range(3):  # reloads, StrictMode double-calls, retries
        start = await client.post(f"/api/v1/public/assessment/{invite['token']}/start")
        assert start.status_code == 200
        view = await client.get(f"/api/v1/public/assessment/{invite['token']}")
        assert view.status_code == 200

    notifications = await _unread(client, ctx["headers"])
    assert [n["type"] for n in notifications] == ["ASSESSMENT_STARTED"]


async def test_repeated_submission_creates_only_one_notification(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_screening_application(client, "notif-dup-submit")
    invite = await _invite(client, ctx)
    await client.post(f"/api/v1/public/assessment/{invite['token']}/start")

    assert (await _submit(client, invite)).status_code == 200
    second = await _submit(client, invite)
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "already_submitted"

    types = [n["type"] for n in await _unread(client, ctx["headers"])]
    assert types.count("ASSESSMENT_SUBMITTED") == 1
    assert types.count("ASSESSMENT_STARTED") == 1


async def test_the_database_itself_refuses_a_duplicate_event(
    client: AsyncClient, super_admin: User, db_session: AsyncSession
) -> None:
    """Concurrent requests can both pass the status check; the unique index
    is the backstop. Calling the service again for the same invitation and
    type must be a no-op."""
    ctx = await _bootstrap_org_with_screening_application(client, "notif-race")
    invite = await _invite(client, ctx)
    await client.post(f"/api/v1/public/assessment/{invite['token']}/start")

    async with rls_bypass(db_session):
        invitation = (
            await db_session.execute(
                select(AssessmentInvitation).where(
                    AssessmentInvitation.application_id == uuid.UUID(ctx["application_id"])
                )
            )
        ).scalar_one()
    await set_tenant_context(db_session, invitation.organization_id)

    created = await in_app_notification_service.notify_inviter_of_assessment_event(
        db_session,
        invitation=invitation,
        notification_type=NotificationType.ASSESSMENT_STARTED,
        candidate_name="Jane Candidate",
        assessment_title="Python Basics",
    )
    assert created is False
    assert len(await _unread(client, ctx["headers"])) == 1


async def test_assessment_flow_is_unaffected_when_the_inviter_no_longer_exists(
    client: AsyncClient, super_admin: User, db_session: AsyncSession
) -> None:
    """`invited_by_user_id` is nullable (ON DELETE SET NULL): with nobody to
    notify, the candidate's start and submit must still work exactly as before."""
    ctx = await _bootstrap_org_with_screening_application(client, "notif-no-inviter")
    invite = await _invite(client, ctx)

    async with rls_bypass(db_session):
        invitation = (
            await db_session.execute(
                select(AssessmentInvitation).where(
                    AssessmentInvitation.application_id == uuid.UUID(ctx["application_id"])
                )
            )
        ).scalar_one()
        invitation.invited_by_user_id = None
        await db_session.flush()

    start = await client.post(f"/api/v1/public/assessment/{invite['token']}/start")
    assert start.status_code == 200
    assert start.json()["status"] == "STARTED"
    assert (await _submit(client, invite)).status_code == 200

    application = (
        await client.get(
            f"/api/v1/recruiter/applications/{ctx['application_id']}", headers=ctx["headers"]
        )
    ).json()
    assert application["status"] == "ASSESSMENT_COMPLETED"
    assert await _unread(client, ctx["headers"]) == []


async def test_acknowledging_removes_it_from_the_unread_list_and_is_repeatable(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_screening_application(client, "notif-ack")
    recruiter_headers = await _create_recruiter(client, ctx["headers"], "riley@notif-ack.dev")
    invite = await _invite(client, ctx, as_headers=recruiter_headers)
    await client.post(f"/api/v1/public/assessment/{invite['token']}/start")

    notification_id = (await _unread(client, recruiter_headers))[0]["id"]

    # A colleague cannot acknowledge (or thereby hide) someone else's notification.
    colleague = await client.post(
        f"{_NOTIFICATIONS}/read", json={"ids": [notification_id]}, headers=ctx["headers"]
    )
    assert colleague.json() == {"updated": 0}
    assert len(await _unread(client, recruiter_headers)) == 1

    first = await client.post(
        f"{_NOTIFICATIONS}/read", json={"ids": [notification_id]}, headers=recruiter_headers
    )
    assert first.json() == {"updated": 1}
    assert await _unread(client, recruiter_headers) == []

    again = await client.post(
        f"{_NOTIFICATIONS}/read", json={"ids": [notification_id]}, headers=recruiter_headers
    )
    assert again.json() == {"updated": 0}

    # Submitting later still notifies — acknowledging one event never blocks the next.
    await _submit(client, invite)
    assert [n["type"] for n in await _unread(client, recruiter_headers)] == ["ASSESSMENT_SUBMITTED"]


async def test_endpoints_require_a_signed_in_organization_user(
    client: AsyncClient, super_admin: User
) -> None:
    # Log in first: the test client rolls the shared session back on any error
    # response, which would also undo the just-seeded SUPER_ADMIN fixture.
    tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    assert (await client.get(_NOTIFICATIONS)).status_code == 401
    assert (
        await client.post(f"{_NOTIFICATIONS}/read", json={"ids": [str(uuid.uuid4())]})
    ).status_code == 401

    # A platform SUPER_ADMIN has no organization and therefore no notifications.
    assert (await client.get(_NOTIFICATIONS, headers=headers)).status_code == 403
    foreign_ack = await client.post(
        f"{_NOTIFICATIONS}/read", json={"ids": [str(uuid.uuid4())]}, headers=headers
    )
    assert foreign_ack.status_code == 403

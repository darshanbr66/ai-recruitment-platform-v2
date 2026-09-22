"""Internal Notification Center: announcements, direct messages, mark-read/
mark-all-read, tenant isolation, and permission enforcement. The existing
assessment-notification flow (test_assessment.py-adjacent) is untouched —
these tests only exercise the new surface built on top of the same table.
"""

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login


async def _bootstrap_org(client: AsyncClient, slug: str) -> dict:
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
    admin_tokens = await login(client, email=org_payload["admin_email"], password=org_payload["admin_password"])
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    recruiter_resp = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": f"recruiter@{slug}.dev",
            "password": "RecruiterPass1",
            "full_name": "Rita Recruiter",
            "role": "RECRUITER",
        },
        headers=admin_headers,
    )
    recruiter_id = recruiter_resp.json()["id"]
    recruiter_tokens = await login(client, email=f"recruiter@{slug}.dev", password="RecruiterPass1")
    recruiter_headers = {"Authorization": f"Bearer {recruiter_tokens['access_token']}"}

    return {
        "slug": slug,
        "admin_headers": admin_headers,
        "admin_id": org_payload,
        "recruiter_headers": recruiter_headers,
        "recruiter_id": recruiter_id,
    }


async def test_direct_message_is_delivered_and_listed(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org(client, "notif-dm")

    send_resp = await client.post(
        "/api/v1/recruiter/notifications/send",
        json={
            "recipient_user_id": ctx["recruiter_id"],
            "title": "Welcome",
            "message": "Glad to have you on the team.",
        },
        headers=ctx["admin_headers"],
    )
    assert send_resp.status_code == 201, send_resp.text
    assert send_resp.json()["sender_name"] == "Acme Admin"

    listing = await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])
    assert listing.status_code == 200
    messages = listing.json()
    assert len(messages) == 1
    assert messages[0]["type"] == "DIRECT_MESSAGE"
    assert messages[0]["read_at"] is None
    assert messages[0]["sender_name"] == "Acme Admin"


async def test_direct_message_cannot_target_another_organization(client: AsyncClient, super_admin: User) -> None:
    org_a = await _bootstrap_org(client, "notif-dm-tenant-a")
    org_b = await _bootstrap_org(client, "notif-dm-tenant-b")

    response = await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": org_b["recruiter_id"], "title": "Hi", "message": "Hello there"},
        headers=org_a["admin_headers"],
    )

    assert response.status_code == 404


async def test_direct_message_cannot_target_self(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org(client, "notif-dm-self")
    admin_me = await client.get("/api/v1/recruiter/auth/me", headers=ctx["admin_headers"])
    admin_id = admin_me.json()["id"]

    response = await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": admin_id, "title": "Hi", "message": "Hello"},
        headers=ctx["admin_headers"],
    )

    assert response.status_code == 422


async def test_announce_requires_permission_for_broadcast(client: AsyncClient, super_admin: User) -> None:
    """RECRUITER has notification.send but not notification.announce —
    broadcast is ORG_ADMIN-only."""
    ctx = await _bootstrap_org(client, "notif-announce-perm")

    response = await client.post(
        "/api/v1/recruiter/notifications/announce",
        json={"title": "Office closed", "message": "Closed tomorrow.", "target": "EVERYONE"},
        headers=ctx["recruiter_headers"],
    )

    assert response.status_code == 403


async def test_announce_to_everyone_notifies_every_active_user_except_the_sender(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org(client, "notif-announce-all")

    response = await client.post(
        "/api/v1/recruiter/notifications/announce",
        json={
            "title": "Maintenance",
            "message": "Tomorrow the office will be closed due to maintenance.",
            "target": "EVERYONE",
        },
        headers=ctx["admin_headers"],
    )
    assert response.status_code == 201, response.text
    # admin + recruiter = 2 active users in this org, minus the sender (admin).
    assert response.json()["recipients_notified"] == 1

    recruiter_listing = await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])
    assert any(n["type"] == "ANNOUNCEMENT" for n in recruiter_listing.json())

    # The sender must never receive a notification for their own announcement.
    admin_listing = await client.get("/api/v1/recruiter/notifications/all", headers=ctx["admin_headers"])
    assert not any(n["type"] == "ANNOUNCEMENT" for n in admin_listing.json())


async def test_announce_to_department_targets_linked_employees_only(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org(client, "notif-announce-dept")

    dept_resp = await client.post(
        "/api/v1/recruiter/departments", json={"name": "Engineering"}, headers=ctx["admin_headers"]
    )
    department_id = dept_resp.json()["id"]

    await client.post(
        "/api/v1/recruiter/employees",
        json={
            "full_name": "Rita Recruiter",
            "email": "rita.employee@notif-announce-dept.dev",
            "department_id": department_id,
            "user_id": ctx["recruiter_id"],
        },
        headers=ctx["admin_headers"],
    )

    response = await client.post(
        "/api/v1/recruiter/notifications/announce",
        json={
            "title": "Team sync",
            "message": "Engineering sync at 3pm.",
            "target": "DEPARTMENT",
            "department_id": department_id,
        },
        headers=ctx["admin_headers"],
    )
    assert response.status_code == 201, response.text
    assert response.json()["recipients_notified"] == 1

    recruiter_listing = (
        await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])
    ).json()
    assert any(n["message"] == "Engineering sync at 3pm." for n in recruiter_listing)

    admin_listing = (
        await client.get("/api/v1/recruiter/notifications/all", headers=ctx["admin_headers"])
    ).json()
    assert not any(n["message"] == "Engineering sync at 3pm." for n in admin_listing)


async def test_mark_read_and_mark_all_read(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org(client, "notif-mark-read")

    await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": ctx["recruiter_id"], "title": "One", "message": "First message"},
        headers=ctx["admin_headers"],
    )
    await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": ctx["recruiter_id"], "title": "Two", "message": "Second message"},
        headers=ctx["admin_headers"],
    )

    unread_before = await client.get("/api/v1/recruiter/notifications/unread-count", headers=ctx["recruiter_headers"])
    assert unread_before.json()["unread"] == 2

    mark_all = await client.post("/api/v1/recruiter/notifications/read-all", headers=ctx["recruiter_headers"])
    assert mark_all.status_code == 200
    assert mark_all.json()["updated"] == 2

    unread_after = await client.get("/api/v1/recruiter/notifications/unread-count", headers=ctx["recruiter_headers"])
    assert unread_after.json()["unread"] == 0

    listing = (await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])).json()
    assert len(listing) == 2
    assert all(n["read_at"] is not None for n in listing)


async def test_hr_employee_can_message_admin_individually(client: AsyncClient, super_admin: User) -> None:
    """The reverse direction of test_direct_message_is_delivered_and_listed
    — every staff role holds `notification.send` and any active org user is
    a valid recipient, so a RECRUITER can already message an ORG_ADMIN."""
    ctx = await _bootstrap_org(client, "notif-hr-to-admin")
    admin_me = await client.get("/api/v1/recruiter/auth/me", headers=ctx["admin_headers"])
    admin_id = admin_me.json()["id"]

    response = await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": admin_id, "title": "Quick question", "message": "Do you have 5 minutes?"},
        headers=ctx["recruiter_headers"],
    )
    assert response.status_code == 201, response.text

    admin_listing = (await client.get("/api/v1/recruiter/notifications/all", headers=ctx["admin_headers"])).json()
    assert any(n["title"] == "Quick question" and n["sender_name"] == "Rita Recruiter" for n in admin_listing)

    # The sender must not see their own message in their own inbox.
    recruiter_listing = (
        await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])
    ).json()
    assert not any(n["title"] == "Quick question" for n in recruiter_listing)


async def test_direct_message_cannot_target_a_candidate(client: AsyncClient, super_admin: User) -> None:
    """Candidates live in a separate table entirely (never `users`), so a
    candidate id is structurally indistinguishable from a nonexistent user."""
    ctx = await _bootstrap_org(client, "notif-no-candidates")

    candidate_resp = await client.post(
        "/api/v1/recruiter/candidates",
        json={"email": "candidate@notif-no-candidates.dev", "full_name": "Chris Candidate"},
        headers=ctx["admin_headers"],
    )
    candidate_id = candidate_resp.json()["id"]

    response = await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": candidate_id, "title": "Hi", "message": "Hello"},
        headers=ctx["admin_headers"],
    )
    assert response.status_code == 404


async def test_sent_tab_groups_an_announcement_into_one_entry(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org(client, "notif-sent-grouping")

    await client.post(
        "/api/v1/recruiter/notifications/announce",
        json={"title": "All hands", "message": "Meeting at 4pm.", "target": "EVERYONE"},
        headers=ctx["admin_headers"],
    )
    await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": ctx["recruiter_id"], "title": "Hey", "message": "Got a sec?"},
        headers=ctx["admin_headers"],
    )

    sent = (await client.get("/api/v1/recruiter/notifications/sent", headers=ctx["admin_headers"])).json()
    assert len(sent) == 2

    announcement = next(s for s in sent if s["type"] == "ANNOUNCEMENT")
    assert announcement["recipient_count"] == 1  # admin excluded, only the recruiter remains
    assert announcement["target_description"] == "Everyone in the organization"

    dm = next(s for s in sent if s["type"] == "DIRECT_MESSAGE")
    assert dm["recipient_count"] == 1
    assert dm["recipient_name"] == "Rita Recruiter"

    # The recruiter's own "Sent" tab is empty — they sent nothing.
    recruiter_sent = (
        await client.get("/api/v1/recruiter/notifications/sent", headers=ctx["recruiter_headers"])
    ).json()
    assert recruiter_sent == []


async def test_search_filters_received_notifications(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org(client, "notif-search")

    await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": ctx["recruiter_id"], "title": "Budget review", "message": "Numbers attached."},
        headers=ctx["admin_headers"],
    )
    await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": ctx["recruiter_id"], "title": "Lunch", "message": "Order is in."},
        headers=ctx["admin_headers"],
    )

    results = (
        await client.get("/api/v1/recruiter/notifications/all?search=budget", headers=ctx["recruiter_headers"])
    ).json()
    assert len(results) == 1
    assert results[0]["title"] == "Budget review"


async def test_delete_removes_only_the_callers_own_copy(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org(client, "notif-delete")

    await client.post(
        "/api/v1/recruiter/notifications/announce",
        json={"title": "Reminder", "message": "Submit timesheets.", "target": "EVERYONE"},
        headers=ctx["admin_headers"],
    )
    recruiter_listing = (
        await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])
    ).json()
    notification_id = recruiter_listing[0]["id"]

    # The sender never received a copy (excluded), so there is nothing of
    # theirs to delete for this broadcast.
    forbidden = await client.delete(
        f"/api/v1/recruiter/notifications/{notification_id}", headers=ctx["admin_headers"]
    )
    assert forbidden.status_code == 404

    deleted = await client.delete(
        f"/api/v1/recruiter/notifications/{notification_id}", headers=ctx["recruiter_headers"]
    )
    assert deleted.status_code == 204

    after = (await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])).json()
    assert not any(n["id"] == notification_id for n in after)


async def test_announce_direct_message_and_delete_are_recorded_in_activity(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org(client, "notif-activity")

    await client.post(
        "/api/v1/recruiter/notifications/announce",
        json={"title": "Policy update", "message": "New policy in effect.", "target": "EVERYONE"},
        headers=ctx["admin_headers"],
    )
    send_resp = await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": ctx["recruiter_id"], "title": "FYI", "message": "See attached."},
        headers=ctx["admin_headers"],
    )
    notification_id = send_resp.json()["id"]

    recruiter_notification_id = (
        await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])
    ).json()[0]["id"]
    await client.delete(
        f"/api/v1/recruiter/notifications/{recruiter_notification_id}", headers=ctx["recruiter_headers"]
    )

    activities = (await client.get("/api/v1/recruiter/activities", headers=ctx["admin_headers"])).json()
    actions = {a["action"] for a in activities}
    assert "ANNOUNCEMENT_SENT" in actions
    assert "DIRECT_MESSAGE_SENT" in actions
    assert "NOTIFICATION_DELETED" in actions
    # Safe metadata only — never the private message body.
    for activity in activities:
        assert "See attached" not in (activity.get("description") or "")
    assert notification_id  # sanity: the DM was actually created


async def test_a_user_can_never_mark_another_users_notification_read(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org(client, "notif-cross-user")

    send_resp = await client.post(
        "/api/v1/recruiter/notifications/send",
        json={"recipient_user_id": ctx["recruiter_id"], "title": "Private", "message": "For the recruiter only."},
        headers=ctx["admin_headers"],
    )
    notification_id = send_resp.json()["id"]

    # The admin (sender, not recipient) tries to mark the recruiter's own
    # notification read — must be a no-op, never touching someone else's row.
    ack = await client.post(
        "/api/v1/recruiter/notifications/read",
        json={"ids": [notification_id]},
        headers=ctx["admin_headers"],
    )
    assert ack.json()["updated"] == 0

    still_unread = (await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])).json()
    assert still_unread[0]["read_at"] is None

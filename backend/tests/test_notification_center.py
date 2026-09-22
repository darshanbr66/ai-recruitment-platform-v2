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


async def test_announce_to_everyone_notifies_every_active_user(client: AsyncClient, super_admin: User) -> None:
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
    # admin + recruiter = 2 active users in this org.
    assert response.json()["recipients_notified"] == 2

    recruiter_listing = await client.get("/api/v1/recruiter/notifications/all", headers=ctx["recruiter_headers"])
    assert any(n["type"] == "ANNOUNCEMENT" for n in recruiter_listing.json())


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

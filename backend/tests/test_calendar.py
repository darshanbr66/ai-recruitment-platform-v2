"""Calendar events: CRUD, ownership, permissions, tenant isolation,
timezone handling, and reminder firing/idempotency (the DB-backed poll —
no Celery/Redis worker is provisioned)."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login


async def _bootstrap_org_with_two_users(client: AsyncClient, slug: str) -> dict:
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

    await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": f"recruiter@{slug}.dev",
            "password": "RecruiterPass1",
            "full_name": "Rita Recruiter",
            "role": "RECRUITER",
        },
        headers=admin_headers,
    )
    recruiter_tokens = await login(client, email=f"recruiter@{slug}.dev", password="RecruiterPass1")
    recruiter_headers = {"Authorization": f"Bearer {recruiter_tokens['access_token']}"}

    return {"admin_headers": admin_headers, "recruiter_headers": recruiter_headers}


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def test_create_and_fetch_event(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "cal-create")
    start = datetime.now(UTC) + timedelta(days=1)

    create_resp = await client.post(
        "/api/v1/recruiter/calendar/events",
        json={
            "title": "Interview with Priya",
            "event_type": "INTERVIEW",
            "start_at": _iso(start),
            "end_at": _iso(start + timedelta(hours=1)),
            "timezone": "Asia/Kolkata",
        },
        headers=ctx["admin_headers"],
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()
    assert body["title"] == "Interview with Priya"
    assert body["status"] == "SCHEDULED"
    assert body["organizer_name"] == "Acme Admin"

    fetched = await client.get(f"/api/v1/recruiter/calendar/events/{body['id']}", headers=ctx["admin_headers"])
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Interview with Priya"


async def test_end_before_start_is_rejected(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "cal-bad-range")
    start = datetime.now(UTC) + timedelta(days=1)

    response = await client.post(
        "/api/v1/recruiter/calendar/events",
        json={
            "title": "Backwards event",
            "start_at": _iso(start),
            "end_at": _iso(start - timedelta(hours=1)),
            "timezone": "UTC",
        },
        headers=ctx["admin_headers"],
    )
    assert response.status_code == 422


async def test_list_events_filters_by_date_range(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "cal-range")
    now = datetime.now(UTC)

    async def _create(title: str, start: datetime) -> None:
        await client.post(
            "/api/v1/recruiter/calendar/events",
            json={
                "title": title,
                "start_at": _iso(start),
                "end_at": _iso(start + timedelta(hours=1)),
                "timezone": "UTC",
            },
            headers=ctx["admin_headers"],
        )

    await _create("This week", now + timedelta(days=2))
    await _create("Next month", now + timedelta(days=40))

    in_range = await client.get(
        "/api/v1/recruiter/calendar/events",
        params={"start": _iso(now), "end": _iso(now + timedelta(days=7))},
        headers=ctx["admin_headers"],
    )
    titles = [e["title"] for e in in_range.json()]
    assert "This week" in titles
    assert "Next month" not in titles


async def test_only_the_organizer_can_edit_or_delete(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "cal-organizer")
    start = datetime.now(UTC) + timedelta(days=1)

    create_resp = await client.post(
        "/api/v1/recruiter/calendar/events",
        json={"title": "Team sync", "start_at": _iso(start), "end_at": _iso(start + timedelta(hours=1)), "timezone": "UTC"},
        headers=ctx["admin_headers"],
    )
    event_id = create_resp.json()["id"]

    forbidden_edit = await client.patch(
        f"/api/v1/recruiter/calendar/events/{event_id}",
        json={"title": "Hijacked"},
        headers=ctx["recruiter_headers"],
    )
    assert forbidden_edit.status_code == 403

    forbidden_delete = await client.delete(
        f"/api/v1/recruiter/calendar/events/{event_id}", headers=ctx["recruiter_headers"]
    )
    assert forbidden_delete.status_code == 403

    # Anyone with calendar.read can still see it.
    visible = await client.get(f"/api/v1/recruiter/calendar/events/{event_id}", headers=ctx["recruiter_headers"])
    assert visible.status_code == 200

    allowed_edit = await client.patch(
        f"/api/v1/recruiter/calendar/events/{event_id}",
        json={"title": "Renamed by organizer"},
        headers=ctx["admin_headers"],
    )
    assert allowed_edit.status_code == 200
    assert allowed_edit.json()["title"] == "Renamed by organizer"


async def test_events_are_tenant_isolated(client: AsyncClient, super_admin: User) -> None:
    org_a = await _bootstrap_org_with_two_users(client, "cal-tenant-a")
    org_b = await _bootstrap_org_with_two_users(client, "cal-tenant-b")
    start = datetime.now(UTC) + timedelta(days=1)

    create_resp = await client.post(
        "/api/v1/recruiter/calendar/events",
        json={"title": "Org A event", "start_at": _iso(start), "end_at": _iso(start + timedelta(hours=1)), "timezone": "UTC"},
        headers=org_a["admin_headers"],
    )
    event_id = create_resp.json()["id"]

    cross_tenant = await client.get(f"/api/v1/recruiter/calendar/events/{event_id}", headers=org_b["admin_headers"])
    assert cross_tenant.status_code == 404

    org_b_list = await client.get(
        "/api/v1/recruiter/calendar/events",
        params={"start": _iso(start - timedelta(days=1)), "end": _iso(start + timedelta(days=1))},
        headers=org_b["admin_headers"],
    )
    assert not any(e["id"] == event_id for e in org_b_list.json())


async def test_timezone_is_preserved_for_display_while_instant_is_unambiguous(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "cal-timezone")
    start = datetime(2026, 12, 25, 9, 30, tzinfo=UTC)

    create_resp = await client.post(
        "/api/v1/recruiter/calendar/events",
        json={
            "title": "Christmas standup",
            "start_at": _iso(start),
            "end_at": _iso(start + timedelta(minutes=30)),
            "timezone": "Asia/Kolkata",
        },
        headers=ctx["admin_headers"],
    )
    body = create_resp.json()
    assert body["timezone"] == "Asia/Kolkata"
    # The stored instant round-trips exactly regardless of the display zone.
    assert datetime.fromisoformat(body["start_at"]) == start


async def test_attendees_must_belong_to_the_same_organization(client: AsyncClient, super_admin: User) -> None:
    org_a = await _bootstrap_org_with_two_users(client, "cal-attendee-a")
    org_b = await _bootstrap_org_with_two_users(client, "cal-attendee-b")
    start = datetime.now(UTC) + timedelta(days=1)

    org_b_me = await client.get("/api/v1/recruiter/auth/me", headers=org_b["admin_headers"])
    org_b_user_id = org_b_me.json()["id"]

    response = await client.post(
        "/api/v1/recruiter/calendar/events",
        json={
            "title": "Cross-tenant invite",
            "start_at": _iso(start),
            "end_at": _iso(start + timedelta(hours=1)),
            "timezone": "UTC",
            "attendee_ids": [org_b_user_id],
        },
        headers=org_a["admin_headers"],
    )
    assert response.status_code == 404


async def test_calendar_read_requires_permission(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "cal-permission")

    await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": "interviewer@cal-permission.dev",
            "password": "SomePassword1",
            "full_name": "Ivy Interviewer",
            "role": "INTERVIEWER",
        },
        headers=ctx["admin_headers"],
    )
    interviewer_tokens = await login(client, email="interviewer@cal-permission.dev", password="SomePassword1")
    interviewer_headers = {"Authorization": f"Bearer {interviewer_tokens['access_token']}"}

    # INTERVIEWER has calendar.read but not calendar.manage.
    now = datetime.now(UTC)
    read_resp = await client.get(
        "/api/v1/recruiter/calendar/events",
        params={"start": _iso(now), "end": _iso(now + timedelta(days=1))},
        headers=interviewer_headers,
    )
    assert read_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/recruiter/calendar/events",
        json={"title": "Nope", "start_at": _iso(now), "end_at": _iso(now + timedelta(hours=1)), "timezone": "UTC"},
        headers=interviewer_headers,
    )
    assert create_resp.status_code == 403


async def test_reminder_fires_exactly_once_and_notifies_organizer_and_attendees(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "cal-reminder")
    recruiter_me = await client.get("/api/v1/recruiter/auth/me", headers=ctx["recruiter_headers"])
    recruiter_id = recruiter_me.json()["id"]

    # A reminder "due" 1 minute from now, with a 60-minute lead time — due now.
    start = datetime.now(UTC) + timedelta(minutes=1)
    create_resp = await client.post(
        "/api/v1/recruiter/calendar/events",
        json={
            "title": "Interview with Priya",
            "start_at": _iso(start),
            "end_at": _iso(start + timedelta(hours=1)),
            "timezone": "UTC",
            "reminder_minutes_before": 60,
            "attendee_ids": [recruiter_id],
        },
        headers=ctx["admin_headers"],
    )
    assert create_resp.status_code == 201, create_resp.text

    # The reminder-check is piggybacked on the notification poll.
    admin_notifications = await client.get("/api/v1/recruiter/notifications", headers=ctx["admin_headers"])
    assert any(n["type"] == "CALENDAR_REMINDER" for n in admin_notifications.json())

    recruiter_notifications = await client.get("/api/v1/recruiter/notifications", headers=ctx["recruiter_headers"])
    assert any(n["type"] == "CALENDAR_REMINDER" for n in recruiter_notifications.json())

    # Polling again must never fire (and re-notify for) the same reminder.
    admin_notifications_second_poll = await client.get(
        "/api/v1/recruiter/notifications", headers=ctx["admin_headers"]
    )
    reminder_count = sum(
        1 for n in admin_notifications_second_poll.json() if n["type"] == "CALENDAR_REMINDER"
    )
    assert reminder_count == 1


async def test_reminder_does_not_fire_before_it_is_due(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "cal-reminder-not-due")
    start = datetime.now(UTC) + timedelta(days=7)

    await client.post(
        "/api/v1/recruiter/calendar/events",
        json={
            "title": "Far future interview",
            "start_at": _iso(start),
            "end_at": _iso(start + timedelta(hours=1)),
            "timezone": "UTC",
            "reminder_minutes_before": 15,
        },
        headers=ctx["admin_headers"],
    )

    notifications = await client.get("/api/v1/recruiter/notifications", headers=ctx["admin_headers"])
    assert not any(n["type"] == "CALENDAR_REMINDER" for n in notifications.json())

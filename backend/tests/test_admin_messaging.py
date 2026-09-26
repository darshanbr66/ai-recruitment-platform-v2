"""Talk to Admin (app/services/admin_messaging_service.py) — internal
staff <-> organization-admin messaging.

The security shape is the point of this file. A staff member reaches only
their own thread (the `/mine` routes accept no conversation id at all), an
ORG_ADMIN reaches every conversation *in their own organization*, and
neither side can reach across a tenant boundary. Authorization is by
permission, not by role name: `admin_message.send` (RECRUITER,
HIRING_MANAGER, INTERVIEWER) and `admin_message.manage` (ORG_ADMIN) are
disjoint, so each side is refused the other's routes.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login

pytestmark = pytest.mark.asyncio

_BASE = "/api/v1/recruiter/admin-messages"
_STAFF_PASSWORD = "StaffMemberPass1"


async def _bootstrap(client: AsyncClient, slug: str) -> dict:
    """An organization with its ORG_ADMIN."""
    super_tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    org_payload = {
        "name": "Acme Corp",
        "slug": slug,
        "admin_email": f"admin@{slug}.dev",
        "admin_password": "AcmeAdminPass1",
        "admin_full_name": "Acme Admin",
    }
    created = await client.post(
        "/api/v1/admin/organizations",
        json=org_payload,
        headers={"Authorization": f"Bearer {super_tokens['access_token']}"},
    )
    assert created.status_code == 201, created.text
    tokens = await login(
        client, email=org_payload["admin_email"], password=org_payload["admin_password"]
    )
    return {
        "slug": slug,
        "admin": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


async def _staff(client: AsyncClient, ctx: dict, *, name: str, role: str = "RECRUITER") -> dict:
    email = f"{name}@{ctx['slug']}.dev"
    created = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": email,
            "password": _STAFF_PASSWORD,
            "full_name": name.replace("-", " ").title(),
            "role": role,
        },
        headers=ctx["admin"],
    )
    assert created.status_code == 201, created.text
    tokens = await login(client, email=email, password=_STAFF_PASSWORD)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _send(client: AsyncClient, headers: dict, body: str):
    return await client.post(f"{_BASE}/mine", json={"body": body}, headers=headers)


async def _conversations(client: AsyncClient, admin: dict) -> list[dict]:
    response = await client.get(f"{_BASE}/conversations", headers=admin)
    assert response.status_code == 200, response.text
    return response.json()


# --- the staff side --------------------------------------------------------


async def test_staff_member_sends_and_reads_their_own_thread(
    client: AsyncClient, super_admin
) -> None:
    ctx = await _bootstrap(client, "talk-mine")
    riley = await _staff(client, ctx, name="riley")

    # Before writing anything there is no conversation yet, but the endpoint
    # still answers with an empty thread rather than 404.
    empty = await client.get(f"{_BASE}/mine", headers=riley)
    assert empty.status_code == 200, empty.text
    assert empty.json()["id"] is None
    assert empty.json()["messages"] == []

    sent = await _send(client, riley, "Could I get access to the campus drive reports?")
    assert sent.status_code == 201, sent.text
    assert sent.json()["from_admin"] is False

    thread = await client.get(f"{_BASE}/mine", headers=riley)
    assert thread.status_code == 200, thread.text
    bodies = [m["body"] for m in thread.json()["messages"]]
    assert bodies == ["Could I get access to the campus drive reports?"]


async def test_staff_members_threads_are_separate(client: AsyncClient, super_admin) -> None:
    """`/mine` is bound to the caller — one staff member never sees
    another's conversation, and there is no id to try."""
    ctx = await _bootstrap(client, "talk-separate")
    riley = await _staff(client, ctx, name="riley")
    morgan = await _staff(client, ctx, name="morgan", role="HIRING_MANAGER")

    assert (await _send(client, riley, "Riley's private question.")).status_code == 201
    assert (await _send(client, morgan, "Morgan's own question.")).status_code == 201

    riley_thread = await client.get(f"{_BASE}/mine", headers=riley)
    morgan_thread = await client.get(f"{_BASE}/mine", headers=morgan)
    riley_bodies = [m["body"] for m in riley_thread.json()["messages"]]
    morgan_bodies = [m["body"] for m in morgan_thread.json()["messages"]]

    assert riley_bodies == ["Riley's private question."]
    assert morgan_bodies == ["Morgan's own question."]
    assert riley_thread.json()["id"] != morgan_thread.json()["id"]


async def test_staff_member_cannot_open_a_colleagues_conversation_by_id(
    client: AsyncClient, super_admin
) -> None:
    """Even holding a real conversation id, a staff member has no
    permission for the admin routes."""
    ctx = await _bootstrap(client, "talk-by-id")
    riley = await _staff(client, ctx, name="riley")
    morgan = await _staff(client, ctx, name="morgan")
    assert (await _send(client, morgan, "Morgan's message.")).status_code == 201

    morgan_conversation = (await _conversations(client, ctx["admin"]))[0]["id"]

    peek = await client.get(f"{_BASE}/conversations/{morgan_conversation}", headers=riley)
    assert peek.status_code == 403, peek.text

    reply = await client.post(
        f"{_BASE}/conversations/{morgan_conversation}/messages",
        json={"body": "Not mine to answer."},
        headers=riley,
    )
    assert reply.status_code == 403, reply.text


# --- the admin side --------------------------------------------------------


async def test_admin_reads_and_replies_to_a_conversation_in_their_organization(
    client: AsyncClient, super_admin
) -> None:
    ctx = await _bootstrap(client, "talk-admin-reply")
    riley = await _staff(client, ctx, name="riley")
    assert (await _send(client, riley, "Can you approve the new job posting?")).status_code == 201

    summaries = await _conversations(client, ctx["admin"])
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["employee_name"] == "Riley"
    assert summary["unread_count"] == 1
    assert summary["last_message_preview"] == "Can you approve the new job posting?"

    reply = await client.post(
        f"{_BASE}/conversations/{summary['id']}/messages",
        json={"body": "Approved — go ahead."},
        headers=ctx["admin"],
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["from_admin"] is True
    assert reply.json()["sender_name"] == "Acme Admin"

    # The staff member sees the reply on their own thread.
    thread = await client.get(f"{_BASE}/mine", headers=riley)
    assert [m["body"] for m in thread.json()["messages"]] == [
        "Can you approve the new job posting?",
        "Approved — go ahead.",
    ]


async def test_admin_sees_every_conversation_in_their_organization(
    client: AsyncClient, super_admin
) -> None:
    ctx = await _bootstrap(client, "talk-admin-inbox")
    riley = await _staff(client, ctx, name="riley")
    morgan = await _staff(client, ctx, name="morgan", role="INTERVIEWER")
    assert (await _send(client, riley, "From Riley.")).status_code == 201
    assert (await _send(client, morgan, "From Morgan.")).status_code == 201

    summaries = await _conversations(client, ctx["admin"])
    assert {s["employee_name"] for s in summaries} == {"Riley", "Morgan"}


async def test_read_state_is_tracked_per_side(client: AsyncClient, super_admin) -> None:
    ctx = await _bootstrap(client, "talk-read-state")
    riley = await _staff(client, ctx, name="riley")
    assert (await _send(client, riley, "Unread until you open it.")).status_code == 201

    # The admin has one unread; the staff member has none (their own
    # message doesn't count against them).
    admin_count = await client.get(f"{_BASE}/unread-count", headers=ctx["admin"])
    assert admin_count.json()["unread"] == 1
    staff_count = await client.get(f"{_BASE}/unread-count", headers=riley)
    assert staff_count.json()["unread"] == 0

    summary = (await _conversations(client, ctx["admin"]))[0]
    marked = await client.post(f"{_BASE}/conversations/{summary['id']}/read", headers=ctx["admin"])
    assert marked.status_code == 200, marked.text
    assert marked.json()["updated"] == 1
    assert (await client.get(f"{_BASE}/unread-count", headers=ctx["admin"])).json()["unread"] == 0

    # Now the admin replies: the unread flips to the staff member's side.
    await client.post(
        f"{_BASE}/conversations/{summary['id']}/messages",
        json={"body": "Seen, thanks."},
        headers=ctx["admin"],
    )
    assert (await client.get(f"{_BASE}/unread-count", headers=riley)).json()["unread"] == 1
    await client.post(f"{_BASE}/mine/read", headers=riley)
    assert (await client.get(f"{_BASE}/unread-count", headers=riley)).json()["unread"] == 0


# --- security boundaries ---------------------------------------------------


async def test_admin_cannot_reach_another_organizations_conversation(
    client: AsyncClient, super_admin
) -> None:
    """The tenant boundary: org B's admin sees org A's conversation as
    absent, and it never appears in their inbox."""
    org_a = await _bootstrap(client, "talk-tenant-a")
    org_b = await _bootstrap(client, "talk-tenant-b")
    riley = await _staff(client, org_a, name="riley")
    assert (await _send(client, riley, "Internal to org A.")).status_code == 201

    conversation_id = (await _conversations(client, org_a["admin"]))[0]["id"]

    # Org B's inbox is empty...
    assert await _conversations(client, org_b["admin"]) == []

    # ...and the id from org A is simply not found for them.
    leaked = await client.get(f"{_BASE}/conversations/{conversation_id}", headers=org_b["admin"])
    assert leaked.status_code == 404, leaked.text

    leaked_reply = await client.post(
        f"{_BASE}/conversations/{conversation_id}/messages",
        json={"body": "Should never land."},
        headers=org_b["admin"],
    )
    assert leaked_reply.status_code == 404, leaked_reply.text

    leaked_read = await client.post(
        f"{_BASE}/conversations/{conversation_id}/read", headers=org_b["admin"]
    )
    assert leaked_read.status_code == 404, leaked_read.text

    # Org A's thread is untouched by any of it.
    thread = await client.get(f"{_BASE}/mine", headers=riley)
    assert [m["body"] for m in thread.json()["messages"]] == ["Internal to org A."]


async def test_unauthenticated_requests_are_rejected(client: AsyncClient, super_admin) -> None:
    ctx = await _bootstrap(client, "talk-anon")
    riley = await _staff(client, ctx, name="riley")
    assert (await _send(client, riley, "A real message.")).status_code == 201
    conversation_id = (await _conversations(client, ctx["admin"]))[0]["id"]

    for method, url, body in (
        ("GET", f"{_BASE}/mine", None),
        ("POST", f"{_BASE}/mine", {"body": "No token."}),
        ("GET", f"{_BASE}/unread-count", None),
        ("GET", f"{_BASE}/conversations", None),
        ("GET", f"{_BASE}/conversations/{conversation_id}", None),
        ("POST", f"{_BASE}/conversations/{conversation_id}/messages", {"body": "No token."}),
    ):
        response = await client.request(method, url, json=body)
        assert response.status_code == 401, f"{method} {url} -> {response.status_code}"


async def test_each_side_is_refused_the_others_routes(client: AsyncClient, super_admin) -> None:
    """`admin_message.send` and `admin_message.manage` are disjoint: an
    ORG_ADMIN has no personal thread, and staff have no inbox."""
    ctx = await _bootstrap(client, "talk-permissions")
    riley = await _staff(client, ctx, name="riley")

    # Staff -> the admin inbox.
    assert (await client.get(f"{_BASE}/conversations", headers=riley)).status_code == 403

    # Admin -> a personal thread.
    assert (await client.get(f"{_BASE}/mine", headers=ctx["admin"])).status_code == 403
    admin_send = await client.post(
        f"{_BASE}/mine", json={"body": "Admins don't message themselves."}, headers=ctx["admin"]
    )
    assert admin_send.status_code == 403, admin_send.text


async def test_platform_super_admin_has_no_organization_thread(
    client: AsyncClient, super_admin
) -> None:
    """A SUPER_ADMIN belongs to no organization, so Talk to Admin — which is
    entirely tenant-scoped — is closed to them rather than unscoped."""
    tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    assert (await client.get(f"{_BASE}/mine", headers=headers)).status_code == 403
    assert (await client.get(f"{_BASE}/conversations", headers=headers)).status_code == 403
    assert (await client.get(f"{_BASE}/unread-count", headers=headers)).status_code == 403


async def test_empty_message_is_rejected(client: AsyncClient, super_admin) -> None:
    ctx = await _bootstrap(client, "talk-empty")
    riley = await _staff(client, ctx, name="riley")

    assert (await _send(client, riley, "   ")).status_code == 422
    assert (await client.get(f"{_BASE}/mine", headers=riley)).json()["messages"] == []

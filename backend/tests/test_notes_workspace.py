"""The standalone personal Notes workspace (`/api/v1/recruiter/notes`) —
private-vs-shared visibility, ownership enforcement, candidate/job linking,
search/filter, and tenant isolation. The original application-scoped notes
feed is covered by tests/test_notes.py and is unaffected by this module.
"""

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


async def test_private_note_is_invisible_to_other_employees(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-private")

    create_resp = await client.post(
        "/api/v1/recruiter/notes",
        json={"body": "Discuss salary expectations.", "visibility": "PRIVATE"},
        headers=ctx["admin_headers"],
    )
    assert create_resp.status_code == 201, create_resp.text
    note_id = create_resp.json()["id"]

    own_list = await client.get("/api/v1/recruiter/notes", headers=ctx["admin_headers"])
    assert any(n["id"] == note_id for n in own_list.json())

    colleague_list = await client.get("/api/v1/recruiter/notes", headers=ctx["recruiter_headers"])
    assert not any(n["id"] == note_id for n in colleague_list.json())

    colleague_get = await client.get(f"/api/v1/recruiter/notes/{note_id}", headers=ctx["recruiter_headers"])
    assert colleague_get.status_code == 404


async def test_shared_note_is_visible_to_colleagues(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-shared")

    create_resp = await client.post(
        "/api/v1/recruiter/notes",
        json={"title": "Team update", "body": "Candidate has strong backend experience.", "visibility": "SHARED"},
        headers=ctx["admin_headers"],
    )
    note_id = create_resp.json()["id"]

    colleague_list = (await client.get("/api/v1/recruiter/notes", headers=ctx["recruiter_headers"])).json()
    assert any(n["id"] == note_id for n in colleague_list)


async def test_default_visibility_for_standalone_notes_is_private(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-default-visibility")

    create_resp = await client.post(
        "/api/v1/recruiter/notes", json={"body": "Follow up next Monday."}, headers=ctx["admin_headers"]
    )
    assert create_resp.json()["visibility"] == "PRIVATE"


async def test_only_the_author_can_edit_a_note_even_if_shared(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-edit-owner")

    create_resp = await client.post(
        "/api/v1/recruiter/notes",
        json={"body": "Original body.", "visibility": "SHARED"},
        headers=ctx["admin_headers"],
    )
    note_id = create_resp.json()["id"]

    forbidden = await client.patch(
        f"/api/v1/recruiter/notes/{note_id}",
        json={"body": "Edited by someone else."},
        headers=ctx["recruiter_headers"],
    )
    assert forbidden.status_code == 403

    allowed = await client.patch(
        f"/api/v1/recruiter/notes/{note_id}",
        json={"body": "Edited by the author."},
        headers=ctx["admin_headers"],
    )
    assert allowed.status_code == 200
    assert allowed.json()["body"] == "Edited by the author."


async def test_only_the_author_can_delete_a_note(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-delete-owner")

    create_resp = await client.post(
        "/api/v1/recruiter/notes",
        json={"body": "Delete me maybe.", "visibility": "SHARED"},
        headers=ctx["admin_headers"],
    )
    note_id = create_resp.json()["id"]

    forbidden = await client.delete(f"/api/v1/recruiter/notes/{note_id}", headers=ctx["recruiter_headers"])
    assert forbidden.status_code == 403

    allowed = await client.delete(f"/api/v1/recruiter/notes/{note_id}", headers=ctx["admin_headers"])
    assert allowed.status_code == 204

    gone = await client.get(f"/api/v1/recruiter/notes/{note_id}", headers=ctx["admin_headers"])
    assert gone.status_code == 404


async def test_update_can_explicitly_clear_a_link_field(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-clear-link")

    candidate_resp = await client.post(
        "/api/v1/recruiter/candidates",
        json={"email": "linked@example.com", "full_name": "Linked Candidate"},
        headers=ctx["admin_headers"],
    )
    candidate_id = candidate_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/recruiter/notes",
        json={"body": "About this candidate.", "candidate_id": candidate_id},
        headers=ctx["admin_headers"],
    )
    note_id = create_resp.json()["id"]
    assert create_resp.json()["candidate_id"] == candidate_id

    update_resp = await client.patch(
        f"/api/v1/recruiter/notes/{note_id}",
        json={"candidate_id": None},
        headers=ctx["admin_headers"],
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["candidate_id"] is None


async def test_linking_to_a_nonexistent_candidate_is_rejected(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-bad-link")

    response = await client.post(
        "/api/v1/recruiter/notes",
        json={"body": "Broken link.", "candidate_id": "00000000-0000-0000-0000-000000000000"},
        headers=ctx["admin_headers"],
    )
    assert response.status_code == 404


async def test_search_filters_by_title_and_body(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-search")

    await client.post(
        "/api/v1/recruiter/notes", json={"title": "Salary talk", "body": "Discuss compensation."},
        headers=ctx["admin_headers"],
    )
    await client.post(
        "/api/v1/recruiter/notes", json={"title": "Unrelated", "body": "Something else entirely."},
        headers=ctx["admin_headers"],
    )

    results = (await client.get("/api/v1/recruiter/notes?search=salary", headers=ctx["admin_headers"])).json()
    assert len(results) == 1
    assert results[0]["title"] == "Salary talk"


async def test_category_filter(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-category")

    await client.post(
        "/api/v1/recruiter/notes", json={"body": "Interview note.", "category": "Interview"},
        headers=ctx["admin_headers"],
    )
    await client.post(
        "/api/v1/recruiter/notes", json={"body": "General reminder.", "category": "General"},
        headers=ctx["admin_headers"],
    )

    results = (
        await client.get("/api/v1/recruiter/notes?category=Interview", headers=ctx["admin_headers"])
    ).json()
    assert len(results) == 1
    assert results[0]["category"] == "Interview"


async def test_pin_and_unpin_persist_and_sort_first(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-pin")

    older = await client.post(
        "/api/v1/recruiter/notes", json={"title": "Older note", "body": "First."}, headers=ctx["admin_headers"]
    )
    newer = await client.post(
        "/api/v1/recruiter/notes", json={"title": "Newer note", "body": "Second."}, headers=ctx["admin_headers"]
    )
    older_id, newer_id = older.json()["id"], newer.json()["id"]

    # Sort by title (deterministic regardless of same-transaction timestamps,
    # unlike created_at) to isolate what pinning alone changes: "Newer" < "Older"
    # alphabetically, so title order puts the newer note first before any pin.
    before = (
        await client.get("/api/v1/recruiter/notes?sort=title&order=asc", headers=ctx["admin_headers"])
    ).json()
    assert before[0]["id"] == newer_id

    pin_resp = await client.post(f"/api/v1/recruiter/notes/{older_id}/pin", headers=ctx["admin_headers"])
    assert pin_resp.status_code == 200
    assert pin_resp.json()["pinned"] is True
    assert pin_resp.json()["pinned_at"] is not None

    # Pinned sorts first regardless of the chosen sort field/direction.
    after = (
        await client.get("/api/v1/recruiter/notes?sort=title&order=asc", headers=ctx["admin_headers"])
    ).json()
    assert after[0]["id"] == older_id

    unpin_resp = await client.post(f"/api/v1/recruiter/notes/{older_id}/pin", headers=ctx["admin_headers"])
    assert unpin_resp.json()["pinned"] is False
    assert unpin_resp.json()["pinned_at"] is None

    restored = (
        await client.get("/api/v1/recruiter/notes?sort=title&order=asc", headers=ctx["admin_headers"])
    ).json()
    assert restored[0]["id"] == newer_id


async def test_only_the_author_can_pin_a_shared_note(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-pin-owner")

    create_resp = await client.post(
        "/api/v1/recruiter/notes",
        json={"body": "Shared note.", "visibility": "SHARED"},
        headers=ctx["admin_headers"],
    )
    note_id = create_resp.json()["id"]

    forbidden = await client.post(f"/api/v1/recruiter/notes/{note_id}/pin", headers=ctx["recruiter_headers"])
    assert forbidden.status_code == 403


async def test_search_matches_category_and_linked_candidate_name(client: AsyncClient, super_admin: User) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-search-extended")

    candidate_resp = await client.post(
        "/api/v1/recruiter/candidates",
        json={"email": "priya@notes-search-extended.dev", "full_name": "Priya Sharma"},
        headers=ctx["admin_headers"],
    )
    candidate_id = candidate_resp.json()["id"]

    await client.post(
        "/api/v1/recruiter/notes",
        json={"title": "Candidate follow-up", "body": "Discuss offer.", "candidate_id": candidate_id},
        headers=ctx["admin_headers"],
    )
    await client.post(
        "/api/v1/recruiter/notes", json={"title": "Unrelated", "body": "Nothing to do with this.", "category": "General"},
        headers=ctx["admin_headers"],
    )

    by_candidate_name = (
        await client.get("/api/v1/recruiter/notes?search=priya", headers=ctx["admin_headers"])
    ).json()
    assert len(by_candidate_name) == 1
    assert by_candidate_name[0]["title"] == "Candidate follow-up"

    by_category = (
        await client.get("/api/v1/recruiter/notes?search=general", headers=ctx["admin_headers"])
    ).json()
    assert len(by_category) == 1
    assert by_category[0]["title"] == "Unrelated"


async def test_note_lifecycle_is_recorded_in_activity_without_leaking_body(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_two_users(client, "notes-activity")

    create_resp = await client.post(
        "/api/v1/recruiter/notes",
        json={"title": "Sensitive", "body": "Secret compensation numbers.", "visibility": "PRIVATE"},
        headers=ctx["admin_headers"],
    )
    note_id = create_resp.json()["id"]

    await client.patch(
        f"/api/v1/recruiter/notes/{note_id}", json={"body": "Updated secret numbers."}, headers=ctx["admin_headers"]
    )
    await client.post(f"/api/v1/recruiter/notes/{note_id}/pin", headers=ctx["admin_headers"])
    await client.delete(f"/api/v1/recruiter/notes/{note_id}", headers=ctx["admin_headers"])

    activities = (await client.get("/api/v1/recruiter/activities", headers=ctx["admin_headers"])).json()
    actions = {a["action"] for a in activities}
    assert {"NOTE_CREATED", "NOTE_UPDATED", "NOTE_PINNED", "NOTE_DELETED"}.issubset(actions)
    for activity in activities:
        assert "Secret compensation" not in (activity.get("description") or "")
        assert "Secret compensation" not in (activity.get("entity_label") or "")


async def test_notes_are_tenant_isolated(client: AsyncClient, super_admin: User) -> None:
    org_a = await _bootstrap_org_with_two_users(client, "notes-tenant-a")
    org_b = await _bootstrap_org_with_two_users(client, "notes-tenant-b")

    create_resp = await client.post(
        "/api/v1/recruiter/notes",
        json={"body": "Org A secret note.", "visibility": "SHARED"},
        headers=org_a["admin_headers"],
    )
    note_id = create_resp.json()["id"]

    org_b_list = (await client.get("/api/v1/recruiter/notes", headers=org_b["admin_headers"])).json()
    assert not any(n["id"] == note_id for n in org_b_list)

    org_b_get = await client.get(f"/api/v1/recruiter/notes/{note_id}", headers=org_b["admin_headers"])
    assert org_b_get.status_code == 404

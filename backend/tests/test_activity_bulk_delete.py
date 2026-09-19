"""ORG_ADMIN bulk / "delete all" of activity entries: permission gating,
strict tenant scoping and honest counts."""

import uuid

from httpx import AsyncClient

from app.models.user import User
from tests.test_applications import _bootstrap_org, _org_admin_headers
from tests.test_email_workflow import _staff_headers

_BASE = "/api/v1/recruiter/activities"


async def _activities(client: AsyncClient, headers: dict) -> list[dict]:
    response = await client.get(_BASE, headers=headers, params={"limit": 500})
    assert response.status_code == 200, response.text
    return response.json()


async def _ids(client: AsyncClient, headers: dict) -> set[str]:
    return {a["id"] for a in await _activities(client, headers)}


async def _bulk_delete(client: AsyncClient, headers: dict, ids: list[str]):
    return await client.request(
        "DELETE", f"{_BASE}/bulk", json={"activity_ids": ids}, headers=headers
    )


async def _delete_all(client: AsyncClient, headers: dict, confirm: bool = True):
    return await client.request("DELETE", f"{_BASE}/all", json={"confirm": confirm}, headers=headers)


async def _org_with_activities(client: AsyncClient, slug: str, candidates: int = 4) -> dict:
    """An organization whose log holds a handful of CANDIDATE_CREATED entries
    (plus the login/bootstrap entries every org already has)."""
    org = await _bootstrap_org(client, slug)
    headers = await _org_admin_headers(client, org)
    for i in range(candidates):
        response = await client.post(
            "/api/v1/recruiter/candidates",
            json={"email": f"c{i}@{slug}.dev", "full_name": f"Candidate {i}"},
            headers=headers,
        )
        assert response.status_code == 201, response.text
    created = [a["id"] for a in await _activities(client, headers) if a["action"] == "CANDIDATE_CREATED"]
    assert len(created) == candidates
    return {"org": org, "headers": headers, "candidate_entry_ids": created}


async def test_org_admin_can_delete_selected_activities(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org_with_activities(client, "bulk-selected")
    before = await _ids(client, ctx["headers"])
    selected = ctx["candidate_entry_ids"][:3]

    response = await _bulk_delete(client, ctx["headers"], selected)

    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": 3}
    # Exactly the selection is gone; everything else is untouched.
    assert await _ids(client, ctx["headers"]) == before - set(selected)


async def test_single_selection_and_duplicates_are_counted_honestly(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org_with_activities(client, "bulk-honest")
    one = ctx["candidate_entry_ids"][0]

    response = await _bulk_delete(client, ctx["headers"], [one, one, one])

    assert response.json() == {"deleted": 1}


async def test_already_deleted_and_unknown_ids_are_ignored_safely(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org_with_activities(client, "bulk-stale")
    first, second = ctx["candidate_entry_ids"][:2]
    assert (await _bulk_delete(client, ctx["headers"], [first])).json() == {"deleted": 1}

    # `first` no longer exists, and the second id is random — only `second` counts.
    response = await _bulk_delete(client, ctx["headers"], [first, second, str(uuid.uuid4())])

    assert response.status_code == 200
    assert response.json() == {"deleted": 1}


async def test_empty_selection_deletes_nothing(client: AsyncClient, super_admin: User) -> None:
    ctx = await _org_with_activities(client, "bulk-empty")
    before = await _ids(client, ctx["headers"])

    response = await _bulk_delete(client, ctx["headers"], [])

    assert response.status_code == 200
    assert response.json() == {"deleted": 0}
    assert await _ids(client, ctx["headers"]) == before


async def test_oversized_and_malformed_selections_are_rejected(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org_with_activities(client, "bulk-limits", candidates=1)
    too_many = [str(uuid.uuid4()) for _ in range(501)]

    assert (await _bulk_delete(client, ctx["headers"], too_many)).status_code == 422
    assert (await _bulk_delete(client, ctx["headers"], ["not-a-uuid"])).status_code == 422


async def test_org_admin_can_delete_all_of_their_own_activities(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org_with_activities(client, "bulk-all")
    total = (await client.get(f"{_BASE}/count", headers=ctx["headers"])).json()["total"]
    assert total == len(await _ids(client, ctx["headers"])) > 0

    response = await _delete_all(client, ctx["headers"])

    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": total}
    assert await _ids(client, ctx["headers"]) == set()
    assert (await client.get(f"{_BASE}/count", headers=ctx["headers"])).json() == {"total": 0}
    # Deleting from an already-empty log is a clean no-op.
    assert (await _delete_all(client, ctx["headers"])).json() == {"deleted": 0}


async def test_delete_all_requires_explicit_confirmation(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org_with_activities(client, "bulk-confirm")
    before = await _ids(client, ctx["headers"])

    unconfirmed = await _delete_all(client, ctx["headers"], confirm=False)
    empty_body = await client.request("DELETE", f"{_BASE}/all", json={}, headers=ctx["headers"])

    assert unconfirmed.status_code == 422
    assert empty_body.status_code == 422
    assert await _ids(client, ctx["headers"]) == before


async def test_bulk_and_delete_all_never_touch_another_organization(
    client: AsyncClient, super_admin: User
) -> None:
    a = await _org_with_activities(client, "bulk-tenant-a")
    b = await _org_with_activities(client, "bulk-tenant-b")
    b_before = await _ids(client, b["headers"])

    # A's admin names B's activity ids explicitly, mixed with their own.
    mixed = a["candidate_entry_ids"][:1] + b["candidate_entry_ids"]
    response = await _bulk_delete(client, a["headers"], mixed)

    assert response.json() == {"deleted": 1}  # only A's own entry
    assert await _ids(client, b["headers"]) == b_before

    # "Delete all" is scoped to A's organization as well.
    await _delete_all(client, a["headers"])
    assert await _ids(client, a["headers"]) == set()
    assert await _ids(client, b["headers"]) == b_before
    assert (await client.get(f"{_BASE}/count", headers=b["headers"])).json()["total"] == len(b_before)


async def test_only_org_admin_can_bulk_delete_or_count(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _org_with_activities(client, "bulk-authz")
    before = await _ids(client, ctx["headers"])
    targets = ctx["candidate_entry_ids"]

    for role in ("RECRUITER", "HIRING_MANAGER", "INTERVIEWER"):
        headers = await _staff_headers(client, ctx["headers"], "bulk-authz", role)
        assert (await _bulk_delete(client, headers, targets)).status_code == 403, role
        assert (await _delete_all(client, headers)).status_code == 403, role
        assert (await client.get(f"{_BASE}/count", headers=headers)).status_code == 403, role

    # Nothing was removed by any of the refused requests (staff creation itself
    # adds entries, so compare against what existed before).
    assert before <= await _ids(client, ctx["headers"])


async def test_bulk_delete_requires_authentication(client: AsyncClient) -> None:
    assert (await _bulk_delete(client, {}, [str(uuid.uuid4())])).status_code == 401
    assert (await _delete_all(client, {})).status_code == 401

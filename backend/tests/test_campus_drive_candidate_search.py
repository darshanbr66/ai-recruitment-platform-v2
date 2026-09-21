"""Campus Drive detail page -> "Candidates in this drive": server-side search,
filters and pagination, scoped to one drive.

The page reads its candidates from the Applications list with `campus_drive_id`
(no separate API), so these tests pin down that a drive's list never leaks
another drive's, another organization's, or non-campus applications, and that
the recruiter view is unaffected by the drive's lifecycle state.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import ApplicationSource, ApplicationStatus
from app.models.user import User
from tests.application_seed import (
    APPLICATIONS_URL,
    bootstrap_org,
    names,
    seed_application,
    total,
    utc,
)
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login

_CAMPUS = {"source": ApplicationSource.CAMPUS_IMPORT}


async def _create_drive(client: AsyncClient, org: dict, name: str = "Fall 2026 Drive") -> str:
    response = await client.post(
        "/api/v1/recruiter/campus-drives",
        json={"name": name, "job_id": org["job_engineer"], "college_name": "MIT"},
        headers=org["headers"],
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _seed_drive(db: AsyncSession, org: dict, drive_id: str) -> None:
    common = {
        "org_id": org["org_id"],
        "job_id": org["job_engineer"],
        "campus_drive_id": drive_id,
        **_CAMPUS,
    }
    rows = [
        (
            "Aarav Mehta",
            "aarav@college.edu",
            "+91 90000 11111",
            ApplicationStatus.APPLIED,
            utc(2026, 9, 1),
            "B.Tech CSE",
        ),
        (
            "Diya Shah",
            "diya@college.edu",
            "80000-22222",
            ApplicationStatus.ASSESSMENT_INVITED,
            utc(2026, 9, 3),
            "B.Tech IT",
        ),
        (
            "Kabir Rao",
            "kabir@college.edu",
            None,
            ApplicationStatus.ASSESSMENT_COMPLETED,
            utc(2026, 9, 6),
            "BCA",
        ),
        (
            "Meera Iyer",
            "meera@college.edu",
            "70000 33333",
            ApplicationStatus.SHORTLISTED,
            utc(2026, 9, 8),
            "B.Tech CSE",
        ),
        (
            "Rohan Das",
            "rohan@college.edu",
            None,
            ApplicationStatus.REJECTED,
            utc(2026, 9, 15),
            "MCA",
        ),
        (
            "Sara Khan",
            "sara@college.edu",
            None,
            ApplicationStatus.SELECTED,
            utc(2026, 9, 20),
            "B.Tech CSE",
        ),
    ]
    for full_name, email, phone, status, applied_at, qualification in rows:
        await seed_application(
            db,
            **common,
            full_name=full_name,
            email=email,
            phone=phone,
            status=status,
            applied_at=applied_at,
            qualification=qualification,
        )
    await seed_application(
        db, **common, full_name="Deleted Drew", email="drew@college.edu", deleted=True
    )


@pytest.fixture
async def drive_ctx(client: AsyncClient, db_session: AsyncSession, super_admin: User) -> dict:
    org = await bootstrap_org(client, "campus-search")
    drive_id = await _create_drive(client, org)
    await _seed_drive(db_session, org, drive_id)

    # Rows that must never appear in this drive's list.
    other_drive = await _create_drive(client, org, name="Spring 2027 Drive")
    await seed_application(
        db_session,
        org_id=org["org_id"],
        job_id=org["job_engineer"],
        campus_drive_id=other_drive,
        full_name="Other Drive Student",
        email="other@college.edu",
        **_CAMPUS,
    )
    await seed_application(
        db_session,
        org_id=org["org_id"],
        job_id=org["job_engineer"],
        full_name="Walk In Wendy",
        email="wendy@example.com",
    )
    return {**org, "drive_id": drive_id, "other_drive_id": other_drive}


async def _get(client: AsyncClient, ctx: dict, **params):
    return await client.get(
        APPLICATIONS_URL,
        params={
            "campus_drive_id": ctx["drive_id"],
            "sort_by": "applied_at",
            "sort_dir": "asc",
            **params,
        },
        headers=ctx["headers"],
    )


_ALL = ["Aarav Mehta", "Diya Shah", "Kabir Rao", "Meera Iyer", "Rohan Das", "Sara Khan"]


async def test_only_this_drives_candidates_are_listed(client: AsyncClient, drive_ctx: dict) -> None:
    response = await _get(client, drive_ctx)
    assert names(response) == _ALL  # no other drive, no non-campus application, no deleted one
    assert total(response) == 6


# --- search ---------------------------------------------------------------------


async def test_search_by_name_email_and_phone(client: AsyncClient, drive_ctx: dict) -> None:
    assert names(await _get(client, drive_ctx, q="meera")) == ["Meera Iyer"]
    assert names(await _get(client, drive_ctx, q="RAO")) == ["Kabir Rao"]
    assert names(await _get(client, drive_ctx, q="diya@college")) == ["Diya Shah"]
    assert names(await _get(client, drive_ctx, q="@college.edu")) == _ALL
    assert names(await _get(client, drive_ctx, q="9000011111")) == ["Aarav Mehta"]
    assert names(await _get(client, drive_ctx, q="80000 22222")) == ["Diya Shah"]


async def test_search_never_reaches_outside_the_drive(client: AsyncClient, drive_ctx: dict) -> None:
    assert names(await _get(client, drive_ctx, q="wendy")) == []
    assert names(await _get(client, drive_ctx, q="Other Drive")) == []


# --- filters --------------------------------------------------------------------


async def test_filter_by_status(client: AsyncClient, drive_ctx: dict) -> None:
    assert names(await _get(client, drive_ctx, status="SHORTLISTED")) == ["Meera Iyer"]
    assert names(await _get(client, drive_ctx, status="APPLIED")) == ["Aarav Mehta"]
    assert names(await _get(client, drive_ctx, status="HIRED")) == []


async def test_filter_by_applied_date_range(client: AsyncClient, drive_ctx: dict) -> None:
    got = await _get(client, drive_ctx, applied_from="2026-09-03", applied_to="2026-09-08")
    assert names(got) == ["Diya Shah", "Kabir Rao", "Meera Iyer"]
    assert names(await _get(client, drive_ctx, applied_from="2026-09-16")) == ["Sara Khan"]
    assert names(await _get(client, drive_ctx, applied_to="2026-08-31")) == []


async def test_filter_by_qualification(client: AsyncClient, drive_ctx: dict) -> None:
    got = await _get(client, drive_ctx, qualification="b.tech")
    assert names(got) == ["Aarav Mehta", "Diya Shah", "Meera Iyer", "Sara Khan"]
    assert names(await _get(client, drive_ctx, qualification="mca")) == ["Rohan Das"]


async def test_filters_combine(client: AsyncClient, drive_ctx: dict) -> None:
    got = await _get(
        client,
        drive_ctx,
        q="college",
        qualification="cse",
        applied_from="2026-09-05",
        status="SHORTLISTED",
    )
    assert names(got) == ["Meera Iyer"]
    assert total(got) == 1
    # Same filters, different status: nothing.
    assert (
        names(
            await _get(
                client, drive_ctx, qualification="cse", applied_from="2026-09-05", status="APPLIED"
            )
        )
        == []
    )


# --- pagination -----------------------------------------------------------------


async def test_pagination_reports_the_drive_total(client: AsyncClient, drive_ctx: dict) -> None:
    first = await _get(client, drive_ctx, limit=4, offset=0)
    second = await _get(client, drive_ctx, limit=4, offset=4)
    assert names(first) == _ALL[:4] and names(second) == _ALL[4:]
    assert total(first) == total(second) == 6


async def test_pagination_happens_after_filtering(client: AsyncClient, drive_ctx: dict) -> None:
    first = await _get(client, drive_ctx, qualification="b.tech", limit=3, offset=0)
    second = await _get(client, drive_ctx, qualification="b.tech", limit=3, offset=3)
    assert names(first) == ["Aarav Mehta", "Diya Shah", "Meera Iyer"]
    assert names(second) == ["Sara Khan"]
    assert total(first) == total(second) == 4


# --- empty results ------------------------------------------------------------------


async def test_empty_results(client: AsyncClient, drive_ctx: dict) -> None:
    nothing = await _get(client, drive_ctx, q="zzz-no-such-student", limit=10)
    assert nothing.json() == [] and total(nothing) == 0
    unknown_drive = await client.get(
        APPLICATIONS_URL,
        params={"campus_drive_id": str(uuid.uuid4())},
        headers=drive_ctx["headers"],
    )
    assert unknown_drive.status_code == 200 and unknown_drive.json() == []
    assert total(unknown_drive) == 0


async def test_invalid_filters_are_rejected(client: AsyncClient, drive_ctx: dict) -> None:
    assert (await _get(client, drive_ctx, status="NOPE")).status_code == 422
    assert (
        await _get(client, drive_ctx, applied_from="2026-09-10", applied_to="2026-09-01")
    ).status_code == 422
    assert (await _get(client, drive_ctx, limit=500)).status_code == 422


# --- tenant isolation & permissions --------------------------------------------------


async def test_another_organization_cannot_see_the_drives_candidates(
    client: AsyncClient, db_session: AsyncSession, drive_ctx: dict
) -> None:
    other = await bootstrap_org(client, "campus-search-other")
    other_drive = await _create_drive(client, other, name="Their Drive")
    await seed_application(
        db_session,
        org_id=other["org_id"],
        job_id=other["job_engineer"],
        campus_drive_id=other_drive,
        full_name="Theirs Only",
        email="theirs@other.edu",
        **_CAMPUS,
    )

    # Asking for org A's drive id from org B's session finds nothing — not even a hint it exists.
    peek = await client.get(
        APPLICATIONS_URL,
        params={"campus_drive_id": drive_ctx["drive_id"], "q": "meera"},
        headers=other["headers"],
    )
    assert peek.status_code == 200 and peek.json() == [] and total(peek) == 0
    # Org B's own drive works, and shows only its own candidate.
    own = await client.get(
        APPLICATIONS_URL, params={"campus_drive_id": other_drive}, headers=other["headers"]
    )
    assert names(own) == ["Theirs Only"]
    # Org A never sees org B's.
    assert "Theirs Only" not in names(await _get(client, drive_ctx))


async def test_listing_requires_authentication_and_the_application_read_permission(
    client: AsyncClient, drive_ctx: dict
) -> None:
    tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    super_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    params = {"campus_drive_id": drive_ctx["drive_id"]}

    assert (
        await client.get(APPLICATIONS_URL, params=params, headers=super_headers)
    ).status_code == 403
    assert (await client.get(APPLICATIONS_URL, params=params)).status_code == 401

    created = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": "interviewer@campus-search.dev",
            "password": "InterviewerPass1",
            "full_name": "Ivy Interviewer",
            "role": "INTERVIEWER",
        },
        headers=drive_ctx["headers"],
    )
    assert created.status_code == 201, created.text
    ivy = await login(client, email="interviewer@campus-search.dev", password="InterviewerPass1")
    allowed = await client.get(
        APPLICATIONS_URL,
        params={**params, "q": "sara"},
        headers={"Authorization": f"Bearer {ivy['access_token']}"},
    )
    assert names(allowed) == ["Sara Khan"]


# --- drive lifecycle is untouched ---------------------------------------------------------


async def test_the_candidate_list_is_the_same_whatever_state_the_drive_is_in(
    client: AsyncClient, drive_ctx: dict
) -> None:
    """DRAFT -> ACTIVE -> PAUSED -> CLOSED only govern the *public* apply link.
    A recruiter must always be able to search a drive's candidates, closed or not."""
    assert names(await _get(client, drive_ctx, q="meera")) == ["Meera Iyer"]  # DRAFT
    for new_status in ("ACTIVE", "PAUSED", "CLOSED"):
        patched = await client.patch(
            f"/api/v1/recruiter/campus-drives/{drive_ctx['drive_id']}",
            json={"status": new_status},
            headers=drive_ctx["headers"],
        )
        assert patched.status_code == 200, patched.text
        response = await _get(client, drive_ctx, status="SHORTLISTED")
        assert names(response) == ["Meera Iyer"], new_status
        assert total(await _get(client, drive_ctx)) == 6

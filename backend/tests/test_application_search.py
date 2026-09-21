"""Applications list: server-side search, filters, sorting and pagination.

Everything is decided by the database — these tests seed known rows and assert
exactly which come back, that paging happens *after* filtering, that inputs are
validated, and that tenants and permissions are respected.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine
from app.models.application import ApplicationSource, ApplicationStatus
from app.models.candidate import CandidateType
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


async def _seed(db: AsyncSession, org: dict) -> None:
    """Five visible applications and one deleted one."""
    common = {"org_id": org["org_id"]}
    await seed_application(
        db,
        **common,
        job_id=org["job_analyst"],
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone="+91 98765 43210",
        status=ApplicationStatus.SHORTLISTED,
        source=ApplicationSource.PORTAL,
        applied_at=utc(2026, 9, 5),
        candidate_type=CandidateType.EXPERIENCED,
        years_experience=5,
        current_title="Senior Data Analyst",
        current_company="Acme Analytics",
        location="Bengaluru",
        preferred_location="Pune",
        qualification="B.Tech",
        notice_period_days=30,
        immediate_joiner=False,
    )
    await seed_application(
        db,
        **common,
        job_id=org["job_engineer"],
        full_name="John Smith",
        email="john@sample.org",
        phone="020-5550101",
        status=ApplicationStatus.APPLIED,
        source=ApplicationSource.RECRUITER_ADDED,
        applied_at=utc(2026, 9, 10),
        candidate_type=CandidateType.EXPERIENCED,
        years_experience=2,
        current_title="Backend Developer",
        current_company="Globex",
        location="Pune",
        preferred_location="Pune",
        qualification="M.Sc",
        notice_period_days=60,
        immediate_joiner=False,
    )
    await seed_application(
        db,
        **common,
        job_id=org["job_analyst"],
        full_name="Priya Nair",
        email="priya@example.com",
        phone="99999 11111",
        status=ApplicationStatus.SHORTLISTED,
        source=ApplicationSource.REFERRAL,
        applied_at=utc(2026, 9, 20, 23, 30),
        candidate_type=CandidateType.FRESHER,
        years_experience=0,
        location="Chennai",
        qualification="B.Sc",
        immediate_joiner=True,
    )
    await seed_application(
        db,
        **common,
        job_id=org["job_engineer"],
        full_name="Amit Kumar",
        email="amit@campus.edu",
        status=ApplicationStatus.REJECTED,
        source=ApplicationSource.CAMPUS_IMPORT,
        applied_at=utc(2026, 8, 15),
        candidate_type=CandidateType.FRESHER,
        qualification="B.Tech",
    )
    await seed_application(
        db,
        **common,
        job_id=org["job_analyst"],
        full_name="Maya Rao",
        email="maya@example.com",
        status=ApplicationStatus.UNDER_REVIEW,
        source=ApplicationSource.OTHER,
        applied_at=utc(2026, 9, 12),
    )
    await seed_application(
        db,
        **common,
        job_id=org["job_analyst"],
        full_name="Deleted Dan",
        email="dan@example.com",
        deleted=True,
    )


@pytest.fixture
async def org(client: AsyncClient, db_session: AsyncSession, super_admin: User) -> dict:
    context = await bootstrap_org(client, "app-search")
    await _seed(db_session, context)
    return context


async def _get(client: AsyncClient, org: dict, **params):
    return await client.get(APPLICATIONS_URL, params=params, headers=org["headers"])


# --- search ---------------------------------------------------------------------


async def test_search_by_name_is_case_insensitive_and_partial(
    client: AsyncClient, org: dict
) -> None:
    assert names(await _get(client, org, q="jAnE")) == ["Jane Doe"]
    assert names(await _get(client, org, q="mith")) == ["John Smith"]


async def test_search_by_email(client: AsyncClient, org: dict) -> None:
    response = await _get(client, org, q="example.com", sort_by="candidate_name", sort_dir="asc")
    assert names(response) == ["Jane Doe", "Maya Rao", "Priya Nair"]
    assert names(await _get(client, org, q="amit@campus")) == ["Amit Kumar"]


async def test_search_by_phone_ignores_spacing_and_punctuation(
    client: AsyncClient, org: dict
) -> None:
    # Stored as "+91 98765 43210".
    assert names(await _get(client, org, q="9876543210")) == ["Jane Doe"]
    assert names(await _get(client, org, q="98765 432")) == ["Jane Doe"]
    assert names(await _get(client, org, q="+91-98765-43210")) == ["Jane Doe"]
    # Stored as "020-5550101".
    assert names(await _get(client, org, q="0205550101")) == ["John Smith"]


async def test_search_also_matches_the_job_title(client: AsyncClient, org: dict) -> None:
    """The previous client-side search matched job titles too."""
    response = await _get(client, org, q="backend", sort_by="candidate_name", sort_dir="asc")
    assert names(response) == ["Amit Kumar", "John Smith"]


async def test_every_search_word_must_match(client: AsyncClient, org: dict) -> None:
    assert names(await _get(client, org, q="jane example")) == ["Jane Doe"]
    assert names(await _get(client, org, q="jane campus")) == []


async def test_search_wildcards_are_literal_characters(client: AsyncClient, org: dict) -> None:
    assert names(await _get(client, org, q="%")) == []
    assert names(await _get(client, org, q="j_ne")) == []
    assert names(await _get(client, org, q="   ")) != []  # blank search = no search


async def test_search_excludes_deleted_applications(client: AsyncClient, org: dict) -> None:
    assert names(await _get(client, org, q="Deleted")) == []
    assert total(await _get(client, org)) == 5


# --- individual filters ---------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"status": "SHORTLISTED"}, ["Jane Doe", "Priya Nair"]),
        ({"status": "REJECTED"}, ["Amit Kumar"]),
        ({"source": "REFERRAL"}, ["Priya Nair"]),
        ({"source": "CAMPUS_IMPORT"}, ["Amit Kumar"]),
        ({"candidate_type": "FRESHER"}, ["Amit Kumar", "Priya Nair"]),
        ({"candidate_type": "EXPERIENCED"}, ["Jane Doe", "John Smith"]),
        ({"current_title": "data analyst"}, ["Jane Doe"]),
        ({"current_company": "globex"}, ["John Smith"]),
        ({"location": "pune"}, ["John Smith"]),  # current location, not preferred
        ({"preferred_location": "pune"}, ["Jane Doe", "John Smith"]),
        ({"qualification": "b.tech"}, ["Amit Kumar", "Jane Doe"]),
        ({"min_experience": 2}, ["Jane Doe", "John Smith"]),
        ({"max_experience": 2}, ["John Smith", "Priya Nair"]),
        ({"min_experience": 3, "max_experience": 10}, ["Jane Doe"]),
        # Notice period is "up to N days"; freshers with none recorded are excluded.
        ({"max_notice_period_days": 30}, ["Jane Doe"]),
        ({"max_notice_period_days": 60}, ["Jane Doe", "John Smith"]),
        ({"immediate_joiner": "true"}, ["Priya Nair"]),
        ({"immediate_joiner": "false"}, ["Jane Doe", "John Smith"]),
    ],
)
async def test_individual_filters(
    client: AsyncClient, org: dict, params: dict, expected: list[str]
) -> None:
    response = await _get(client, org, sort_by="candidate_name", sort_dir="asc", **params)
    assert names(response) == expected
    assert total(response) == len(expected)


async def test_job_filter(client: AsyncClient, org: dict) -> None:
    response = await _get(
        client, org, job_id=org["job_analyst"], sort_by="candidate_name", sort_dir="asc"
    )
    assert names(response) == ["Jane Doe", "Maya Rao", "Priya Nair"]


# --- dates ---------------------------------------------------------------------


async def test_applied_date_range_is_inclusive_on_both_ends(client: AsyncClient, org: dict) -> None:
    def in_range(**p):
        return _get(client, org, sort_by="applied_at", sort_dir="asc", **p)

    assert names(await in_range(applied_from="2026-09-10", applied_to="2026-09-12")) == [
        "John Smith",
        "Maya Rao",
    ]
    # Priya applied 2026-09-20 23:30 UTC — still "on" the 20th.
    assert names(await in_range(applied_to="2026-09-20")) == [
        "Amit Kumar",
        "Jane Doe",
        "John Smith",
        "Maya Rao",
        "Priya Nair",
    ]
    assert "Priya Nair" not in names(await in_range(applied_to="2026-09-19"))
    assert names(await in_range(applied_from="2026-09-20")) == ["Priya Nair"]
    assert names(await in_range(applied_from="2026-09-21")) == []


# --- combined --------------------------------------------------------------------


async def test_filters_combine_with_and(client: AsyncClient, org: dict) -> None:
    """Job = Data Analyst AND Shortlisted AND experience >= 2 AND a date range."""
    response = await _get(
        client,
        org,
        job_id=org["job_analyst"],
        status="SHORTLISTED",
        min_experience=2,
        applied_from="2026-09-01",
        applied_to="2026-09-21",
        source="PORTAL",
    )
    assert names(response) == ["Jane Doe"]
    assert total(response) == 1

    # Dropping the experience bound admits the fresher too; changing the source excludes Jane.
    loosened = await _get(
        client,
        org,
        job_id=org["job_analyst"],
        status="SHORTLISTED",
        sort_by="candidate_name",
        sort_dir="asc",
    )
    assert names(loosened) == ["Jane Doe", "Priya Nair"]
    assert names(
        await _get(client, org, job_id=org["job_analyst"], status="SHORTLISTED", source="REFERRAL")
    ) == ["Priya Nair"]


async def test_search_combines_with_filters(client: AsyncClient, org: dict) -> None:
    assert names(
        await _get(client, org, q="example.com", status="SHORTLISTED", min_experience=1)
    ) == ["Jane Doe"]
    assert names(await _get(client, org, q="example.com", status="REJECTED")) == []


# --- sorting ---------------------------------------------------------------------


async def test_sorting(client: AsyncClient, org: dict) -> None:
    by_name = await _get(client, org, sort_by="candidate_name", sort_dir="asc")
    assert names(by_name) == ["Amit Kumar", "Jane Doe", "John Smith", "Maya Rao", "Priya Nair"]
    assert (
        names(await _get(client, org, sort_by="candidate_name", sort_dir="desc"))[0] == "Priya Nair"
    )
    assert names(await _get(client, org, sort_by="applied_at", sort_dir="desc"))[0] == "Priya Nair"
    assert names(await _get(client, org, sort_by="applied_at", sort_dir="asc"))[0] == "Amit Kumar"
    # Workflow order, not alphabetical: APPLIED < UNDER_REVIEW < SHORTLISTED < REJECTED.
    by_status = await _get(client, org, sort_by="status", sort_dir="asc")
    assert names(by_status)[0] == "John Smith" and names(by_status)[-1] == "Amit Kumar"
    # "Backend Engineer" sorts before "Data Analyst" (ties broken by id, so compare as sets).
    by_job = names(await _get(client, org, sort_by="job_title", sort_dir="asc"))
    assert set(by_job[:2]) == {"John Smith", "Amit Kumar"}
    assert set(by_job[2:]) == {"Jane Doe", "Priya Nair", "Maya Rao"}


async def test_default_order_is_newest_first(client: AsyncClient, org: dict) -> None:
    assert names(await _get(client, org))[0] == "Priya Nair"


# --- pagination ------------------------------------------------------------------


async def test_pagination_is_applied_after_filtering(
    client: AsyncClient, db_session: AsyncSession, org: dict
) -> None:
    for n in range(12):
        await seed_application(
            db_session,
            org_id=org["org_id"],
            job_id=org["job_analyst"],
            full_name=f"Bulk {n:02d}",
            email=f"bulk{n:02d}@example.com",
            status=ApplicationStatus.INTERVIEW,
            applied_at=utc(2026, 9, 1, 8, n),
        )

    seen: list[str] = []
    for offset, expected_len in ((0, 5), (5, 5), (10, 2), (15, 0)):
        page = await _get(
            client,
            org,
            status="INTERVIEW",
            limit=5,
            offset=offset,
            sort_by="candidate_name",
            sort_dir="asc",
        )
        assert len(names(page)) == expected_len
        assert total(page) == 12  # the filtered total, not 17 rows in the org
        seen += names(page)

    # Every matching row exactly once, none of the other 5 applications mixed in.
    assert seen == [f"Bulk {n:02d}" for n in range(12)]


async def test_pages_never_repeat_or_skip_rows_that_tie_on_the_sort_key(
    client: AsyncClient, db_session: AsyncSession, org: dict
) -> None:
    for n in range(9):
        await seed_application(
            db_session,
            org_id=org["org_id"],
            job_id=org["job_engineer"],
            full_name=f"Tie {n}",
            email=f"tie{n}@example.com",
            status=ApplicationStatus.INTERVIEW,
            applied_at=utc(2026, 9, 2),  # identical timestamps
        )
    ids: list[str] = []
    for offset in (0, 3, 6):
        page = await _get(
            client, org, status="INTERVIEW", limit=3, offset=offset, sort_by="applied_at"
        )
        ids += [row["id"] for row in page.json()]
    assert len(ids) == len(set(ids)) == 9


async def test_unpaged_request_returns_everything_with_a_matching_total(
    client: AsyncClient, org: dict
) -> None:
    response = await _get(client, org)
    assert len(response.json()) == 5
    assert total(response) == 5


async def test_paging_past_the_end_is_empty_but_still_reports_the_total(
    client: AsyncClient, org: dict
) -> None:
    response = await _get(client, org, limit=10, offset=50)
    assert response.json() == []
    assert total(response) == 5


# --- empty results ---------------------------------------------------------------


async def test_no_matches_is_an_empty_list_with_zero_total(client: AsyncClient, org: dict) -> None:
    response = await _get(client, org, q="nobody-has-this-name", limit=25)
    assert response.status_code == 200
    assert response.json() == []
    assert total(response) == 0
    assert names(await _get(client, org, status="HIRED")) == []


# --- validation ------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"status": "NOT_A_STATUS"},
        {"source": "LINKEDIN"},  # not a source this system has
        {"candidate_type": "STUDENT"},
        {"immediate_joiner": "maybe"},
        {"min_experience": -1},
        {"max_experience": 81},
        {"max_notice_period_days": -5},
        {"max_notice_period_days": 366},
        {"min_experience": "abc"},
        {"applied_from": "not-a-date"},
        {"applied_to": "2026-13-45"},
        {"sort_by": "password"},
        {"sort_dir": "sideways"},
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"q": "x" * 101},
        {"job_id": "not-a-uuid"},
    ],
)
async def test_invalid_values_are_rejected_with_422(
    client: AsyncClient, org: dict, params: dict
) -> None:
    response = await _get(client, org, **params)
    assert response.status_code == 422, response.text


async def test_inverted_ranges_are_rejected_with_a_clear_message(
    client: AsyncClient, org: dict
) -> None:
    experience = await _get(client, org, min_experience=5, max_experience=2)
    assert experience.status_code == 422
    assert "Minimum experience" in experience.json()["error"]["message"]

    dates = await _get(client, org, applied_from="2026-09-21", applied_to="2026-09-01")
    assert dates.status_code == 422
    assert "applied from" in dates.json()["error"]["message"]


# --- tenant isolation & permissions ------------------------------------------------


async def test_another_organization_sees_none_of_it(
    client: AsyncClient, db_session: AsyncSession, org: dict
) -> None:
    other = await bootstrap_org(client, "app-search-other")
    await seed_application(
        db_session,
        org_id=other["org_id"],
        job_id=other["job_analyst"],
        full_name="Olivia Other",
        email="olivia@other.dev",
        status=ApplicationStatus.SHORTLISTED,
    )

    # The other org sees only its own application, however it searches or filters.
    assert names(await _get(client, other)) == ["Olivia Other"]
    assert total(await _get(client, other)) == 1
    assert names(await _get(client, other, q="jane")) == []
    assert names(await _get(client, other, q="example.com")) == []
    assert names(await _get(client, other, status="SHORTLISTED")) == ["Olivia Other"]
    # Even with the first org's own job id in the filter.
    leaked = await _get(client, other, job_id=org["job_analyst"])
    assert leaked.json() == [] and total(leaked) == 0
    # And the first org never sees the other's.
    assert "Olivia Other" not in names(await _get(client, org, q="olivia"))
    assert names(await _get(client, org, q="olivia")) == []


async def test_listing_requires_authentication(client: AsyncClient, org: dict) -> None:
    assert (await client.get(APPLICATIONS_URL)).status_code == 401


async def test_a_platform_super_admin_without_recruiter_permissions_is_refused(
    client: AsyncClient, org: dict
) -> None:
    tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
    response = await client.get(
        APPLICATIONS_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 403


async def test_a_read_only_interviewer_can_search(client: AsyncClient, org: dict) -> None:
    created = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": "interviewer@app-search.dev",
            "password": "InterviewerPass1",
            "full_name": "Ivy Interviewer",
            "role": "INTERVIEWER",
        },
        headers=org["headers"],
    )
    assert created.status_code == 201, created.text
    tokens = await login(client, email="interviewer@app-search.dev", password="InterviewerPass1")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await client.get(APPLICATIONS_URL, params={"q": "jane"}, headers=headers)
    assert names(response) == ["Jane Doe"]


# --- shape & efficiency ---------------------------------------------------------------


async def test_rows_carry_the_candidate_phone_for_display(client: AsyncClient, org: dict) -> None:
    rows = (await _get(client, org, q="jane")).json()
    assert rows[0]["candidate_phone"] == "+91 98765 43210"
    assert rows[0]["candidate_email"] == "jane.doe@example.com"
    assert rows[0]["job_title"] == "Data Analyst"


async def test_a_bigger_page_costs_no_extra_queries(client: AsyncClient, org: dict) -> None:
    """No N+1: the candidate, job and resume come back inside the one list
    query, so a 5-row page runs the same statements as a 1-row page — the list
    query plus one count."""
    statements: list[str] = []

    def record(conn, cursor, statement, *args):  # noqa: ANN001
        # The test client wraps each request in a savepoint; that is harness
        # bookkeeping, not application queries.
        if not statement.startswith(("SAVEPOINT", "RELEASE")):
            statements.append(" ".join(statement.split()))

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        await _get(client, org, limit=1)
        one_row = list(statements)
        statements.clear()
        await _get(client, org, limit=25)
        many_rows = list(statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)

    assert len(one_row) == len(many_rows)
    # Of those, exactly one reads applications rows (with candidate/job/resume
    # joined in) and one counts them.
    counting = [q for q in many_rows if q.startswith("SELECT count(applications.id)")]
    listing = [q for q in many_rows if "FROM applications" in q and q not in counting]
    assert len(listing) == 1 and len(counting) == 1
    assert "JOIN candidates" in listing[0] and "JOIN jobs" in listing[0]
    assert "JOIN resumes" in listing[0]

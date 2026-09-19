"""The public application form's extended candidate profile: candidate
type, experience, notice period, availability, current/preferred location,
qualification and LinkedIn/GitHub links."""

from httpx import AsyncClient

from app.models.user import User
from tests.test_public_applications import _bootstrap_org_with_open_job, _resume_file


def _apply_url(ctx: dict) -> str:
    return f"/api/v1/public/organizations/{ctx['slug']}/jobs/{ctx['job_id']}/apply"


async def _candidate_by_email(client: AsyncClient, ctx: dict, email: str) -> dict:
    listing = await client.get("/api/v1/recruiter/candidates", headers=ctx["admin_headers"])
    (candidate,) = [c for c in listing.json() if c["email"] == email]
    return candidate


async def test_experienced_applicant_profile_is_stored(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_open_job(client, "profile-experienced")

    response = await client.post(
        _apply_url(ctx),
        data={
            "full_name": "Eli Experienced",
            "email": "eli@profile-experienced.dev",
            "candidate_type": "EXPERIENCED",
            "years_experience": "6",
            "notice_period_days": "30",
            "current_title": "Senior Engineer",
            "current_company": "Globex",
            "current_location": "Pune",
            "preferred_location": "Bengaluru",
            "qualification": "B.Tech Computer Science",
            "linkedin_url": "linkedin.com/in/eli",
            "github_url": "https://github.com/eli",
        },
        files=_resume_file(),
    )
    assert response.status_code == 201, response.text

    candidate = await _candidate_by_email(client, ctx, "eli@profile-experienced.dev")
    assert candidate["candidate_type"] == "EXPERIENCED"
    assert candidate["years_experience"] == 6
    assert candidate["notice_period_days"] == 30
    assert candidate["current_title"] == "Senior Engineer"
    assert candidate["current_company"] == "Globex"
    assert candidate["location"] == "Pune"
    assert candidate["preferred_location"] == "Bengaluru"
    assert candidate["qualification"] == "B.Tech Computer Science"
    assert candidate["linkedin_url"] == "https://linkedin.com/in/eli"
    assert candidate["github_url"] == "https://github.com/eli"


async def test_immediate_joiner_has_zero_notice_period(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_open_job(client, "profile-immediate")

    response = await client.post(
        _apply_url(ctx),
        data={
            "full_name": "Ida Immediate",
            "email": "ida@profile-immediate.dev",
            "candidate_type": "EXPERIENCED",
            "years_experience": "3",
            "immediate_joiner": "true",
        },
        files=_resume_file(),
    )
    assert response.status_code == 201, response.text

    candidate = await _candidate_by_email(client, ctx, "ida@profile-immediate.dev")
    assert candidate["immediate_joiner"] is True
    assert candidate["notice_period_days"] == 0


async def test_fresher_defaults_to_zero_experience_and_no_notice_period(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_open_job(client, "profile-fresher")

    response = await client.post(
        _apply_url(ctx),
        data={
            "full_name": "Fay Fresher",
            "email": "fay@profile-fresher.dev",
            "candidate_type": "FRESHER",
            "qualification": "B.Sc",
            "notice_period_days": "60",
        },
        files=_resume_file(),
    )
    assert response.status_code == 201, response.text

    candidate = await _candidate_by_email(client, ctx, "fay@profile-fresher.dev")
    assert candidate["candidate_type"] == "FRESHER"
    assert candidate["years_experience"] == 0
    assert candidate["notice_period_days"] is None


async def test_experienced_applicant_must_provide_experience_and_notice_period(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_open_job(client, "profile-required")

    missing_experience = await client.post(
        _apply_url(ctx),
        data={
            "full_name": "No Experience",
            "email": "a@profile-required.dev",
            "candidate_type": "EXPERIENCED",
            "notice_period_days": "30",
        },
        files=_resume_file(),
    )
    assert missing_experience.status_code == 422

    missing_notice = await client.post(
        _apply_url(ctx),
        data={
            "full_name": "No Notice",
            "email": "b@profile-required.dev",
            "candidate_type": "EXPERIENCED",
            "years_experience": "4",
        },
        files=_resume_file(),
    )
    assert missing_notice.status_code == 422

    # Nothing was created by either rejected submission.
    listing = await client.get("/api/v1/recruiter/candidates", headers=ctx["admin_headers"])
    assert listing.json() == []


async def test_profile_urls_must_point_at_the_expected_site(
    client: AsyncClient, super_admin: User
) -> None:
    ctx = await _bootstrap_org_with_open_job(client, "profile-urls")

    for field, bad_value in (
        ("linkedin_url", "https://evil.example.com/in/eli"),
        ("linkedin_url", "javascript:alert(1)"),
        ("github_url", "https://notgithub.com/eli"),
    ):
        response = await client.post(
            _apply_url(ctx),
            data={"full_name": "Eli", "email": "eli@profile-urls.dev", field: bad_value},
            files=_resume_file(),
        )
        assert response.status_code == 422, (field, bad_value, response.text)
        assert field in response.text


async def test_reapplying_never_overwrites_an_existing_candidates_profile(
    client: AsyncClient, super_admin: User
) -> None:
    """The endpoint is anonymous — knowing someone's email must not let
    you rewrite what is already recorded about them."""
    ctx = await _bootstrap_org_with_open_job(client, "profile-no-overwrite")
    await client.post(
        "/api/v1/recruiter/candidates",
        json={
            "email": "kim@profile-no-overwrite.dev",
            "full_name": "Kim Existing",
            "current_company": "Initech",
        },
        headers=ctx["admin_headers"],
    )

    response = await client.post(
        _apply_url(ctx),
        data={
            "full_name": "Kim Existing",
            "email": "kim@profile-no-overwrite.dev",
            "candidate_type": "EXPERIENCED",
            "years_experience": "9",
            "notice_period_days": "15",
            "current_company": "Attacker Corp",
        },
        files=_resume_file(),
    )
    assert response.status_code == 201, response.text

    candidate = await _candidate_by_email(client, ctx, "kim@profile-no-overwrite.dev")
    assert candidate["current_company"] == "Initech"  # kept
    assert candidate["years_experience"] == 9  # empty field was filled in

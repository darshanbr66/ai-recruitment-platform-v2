"""Seeding helpers for the Applications / Campus Drive candidate search tests.

The public API can't set a candidate's phone, experience, notice period or an
application's `applied_at`, so these tests insert rows directly (under an RLS
bypass, exactly like `super_admin` in conftest) and then exercise the real HTTP
list endpoint against them.
"""

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.rls import rls_bypass
from app.models.application import Application, ApplicationSource, ApplicationStatus
from app.models.candidate import Candidate, CandidateSource, CandidateType
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login

APPLICATIONS_URL = "/api/v1/recruiter/applications"


def utc(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


async def bootstrap_org(client: AsyncClient, slug: str) -> dict:
    """An organization with its admin, plus two jobs. Returns auth headers,
    the org id and the job ids."""
    super_admin_tokens = await login(client, email=SUPER_ADMIN_EMAIL, password=SUPER_ADMIN_PASSWORD)
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
        headers={"Authorization": f"Bearer {super_admin_tokens['access_token']}"},
    )
    assert created.status_code == 201, created.text
    admin_tokens = await login(
        client, email=org_payload["admin_email"], password=org_payload["admin_password"]
    )
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    jobs = {}
    for key, title in (("analyst", "Data Analyst"), ("engineer", "Backend Engineer")):
        job = await client.post(
            "/api/v1/recruiter/jobs",
            json={"title": title, "description": f"{title} role."},
            headers=headers,
        )
        assert job.status_code == 201, job.text
        jobs[key] = job.json()
    return {
        "headers": headers,
        "org_id": uuid.UUID(jobs["analyst"]["organization_id"]),
        "job_analyst": jobs["analyst"]["id"],
        "job_engineer": jobs["engineer"]["id"],
        "admin": org_payload,
    }


async def seed_application(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    job_id: str,
    full_name: str,
    email: str,
    status: ApplicationStatus = ApplicationStatus.APPLIED,
    source: ApplicationSource = ApplicationSource.PORTAL,
    applied_at: datetime | None = None,
    campus_drive_id: str | None = None,
    deleted: bool = False,
    phone: str | None = None,
    candidate_type: CandidateType | None = None,
    years_experience: int | None = None,
    current_title: str | None = None,
    current_company: str | None = None,
    location: str | None = None,
    preferred_location: str | None = None,
    qualification: str | None = None,
    notice_period_days: int | None = None,
    immediate_joiner: bool | None = None,
) -> Application:
    applied_at = applied_at or utc(2026, 9, 1)
    async with rls_bypass(db):
        candidate = Candidate(
            organization_id=org_id,
            email=email,
            full_name=full_name,
            phone=phone,
            location=location,
            current_title=current_title,
            years_experience=years_experience,
            candidate_type=candidate_type,
            current_company=current_company,
            preferred_location=preferred_location,
            notice_period_days=notice_period_days,
            immediate_joiner=immediate_joiner,
            qualification=qualification,
            source=CandidateSource.RECRUITER_ADDED,
        )
        db.add(candidate)
        await db.flush()
        application = Application(
            organization_id=org_id,
            candidate_id=candidate.id,
            job_id=uuid.UUID(job_id),
            campus_drive_id=uuid.UUID(campus_drive_id) if campus_drive_id else None,
            status=status,
            source=source,
            applied_at=applied_at,
            created_at=applied_at,
            deleted_at=utc(2026, 9, 21) if deleted else None,
        )
        db.add(application)
        await db.flush()
    return application


def names(response) -> list[str]:
    """Candidate names of a list response, in returned order."""
    assert response.status_code == 200, response.text
    return [row["candidate_full_name"] for row in response.json()]


def total(response) -> int:
    return int(response.headers["X-Total-Count"])

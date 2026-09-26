"""The 3-month self-apply window and HR's "Allow Reapply" override
(app/services/reapply_service.py).

The window is measured from the candidate's last *self-service* application,
so these tests seed applications with a controlled `applied_at` and drive the
real HTTP endpoints against them. A seeded application is only self-service
when it says so: `is_self_service` is what the rule counts, not `source`.

Covers the lock, expiry, the single-use HR grant, and the two security
boundaries CLAUDE.md § 5 requires — tenant isolation and authorization.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.rls import rls_bypass
from app.models.application import Application, ApplicationSource, ApplicationStatus
from app.models.candidate import Candidate, CandidateSource
from app.models.candidate_reapply_grant import CandidateReapplyGrant
from app.services import reapply_service
from tests.conftest import SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, login

pytestmark = pytest.mark.asyncio


def _months_ago(months: int) -> datetime:
    """Comfortably inside/outside a 3-month window without depending on
    calendar arithmetic at the boundary (that is unit-tested separately by
    `test_add_months_clamps_to_shorter_month`)."""
    return datetime.now(UTC) - timedelta(days=31 * months)


async def _bootstrap(client: AsyncClient, slug: str) -> dict:
    """An organization, its ORG_ADMIN, and one job."""
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
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    job = await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Backend Engineer", "description": "Builds services."},
        headers=headers,
    )
    assert job.status_code == 201, job.text
    return {
        "headers": headers,
        "org_id": uuid.UUID(job.json()["organization_id"]),
        "job_id": job.json()["id"],
        "admin": org_payload,
    }


async def _seed_applicant(
    db: AsyncSession,
    ctx: dict,
    *,
    email: str,
    applied_at: datetime,
    is_self_service: bool = True,
) -> uuid.UUID:
    """A candidate with one application at `applied_at`. Written directly
    under an RLS bypass because no API can backdate an application.

    Committed, not just flushed: the `client` fixture rolls the shared
    session back whenever a request errors (a 401/403/404 this file asserts
    on), which would otherwise discard the seed before the next request.
    The commit only releases a savepoint — the test's outer transaction is
    still rolled back by `db_connection`, so nothing survives the test.

    Returns the id rather than the instance: a rollback expires every
    loaded object, and reading an attribute off one afterwards would try to
    refresh it outside the async context.
    """
    async with rls_bypass(db):
        candidate = Candidate(
            organization_id=ctx["org_id"],
            email=email,
            full_name="Cara Candidate",
            source=CandidateSource.PORTAL if is_self_service else CandidateSource.RECRUITER_ADDED,
        )
        db.add(candidate)
        await db.flush()
        candidate_id = candidate.id
        db.add(
            Application(
                organization_id=ctx["org_id"],
                candidate_id=candidate_id,
                job_id=uuid.UUID(ctx["job_id"]),
                status=ApplicationStatus.APPLIED,
                source=(
                    ApplicationSource.PORTAL if is_self_service else ApplicationSource.RECRUITER_ADDED
                ),
                applied_at=applied_at,
                created_at=applied_at,
                is_self_service=is_self_service,
            )
        )
        await db.flush()
    await db.commit()
    return candidate_id


async def _status(client: AsyncClient, ctx: dict, candidate_id: uuid.UUID, **kw) -> dict:
    response = await client.get(
        f"/api/v1/recruiter/candidates/{candidate_id}/reapply-status",
        headers=kw.get("headers", ctx["headers"]),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _create_staff(client: AsyncClient, ctx: dict, *, email: str, role: str) -> dict:
    created = await client.post(
        "/api/v1/recruiter/users",
        json={
            "email": email,
            "password": "StaffMemberPass1",
            "full_name": f"{role.title()} User",
            "role": role,
        },
        headers=ctx["headers"],
    )
    assert created.status_code == 201, created.text
    tokens = await login(client, email=email, password="StaffMemberPass1")
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# --- the window ------------------------------------------------------------


async def test_recent_self_application_locks_the_candidate_out(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    ctx = await _bootstrap(client, "reapply-locked")
    candidate_id = await _seed_applicant(
        db_session, ctx, email="recent@reapply-locked.dev", applied_at=_months_ago(1)
    )

    status = await _status(client, ctx, candidate_id)
    assert status["can_self_apply_now"] is False
    assert status["cooldown_months"] == 3
    assert status["open_grant"] is None
    # The window opens three months after the application, not after "now".
    assert status["eligible_from"] > status["last_self_applied_at"]


async def test_candidate_may_self_apply_again_after_three_months(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    ctx = await _bootstrap(client, "reapply-expired")
    candidate_id = await _seed_applicant(
        db_session, ctx, email="old@reapply-expired.dev", applied_at=_months_ago(4)
    )

    status = await _status(client, ctx, candidate_id)
    assert status["can_self_apply_now"] is True
    assert status["last_self_applied_at"] is not None


async def test_hr_created_application_never_locks_the_candidate_out(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    """Only self-service applications count. A candidate HR added moments
    ago can still apply themselves."""
    ctx = await _bootstrap(client, "reapply-hr-added")
    candidate_id = await _seed_applicant(
        db_session,
        ctx,
        email="hr-added@reapply-hr-added.dev",
        applied_at=_months_ago(0),
        is_self_service=False,
    )

    status = await _status(client, ctx, candidate_id)
    assert status["can_self_apply_now"] is True
    assert status["last_self_applied_at"] is None


def test_add_months_clamps_to_shorter_month() -> None:
    """30 November + 3 months has no 30 February to land on."""
    assert reapply_service.add_months(datetime(2025, 11, 30, tzinfo=UTC), 3) == datetime(
        2026, 2, 28, tzinfo=UTC
    )
    assert reapply_service.add_months(datetime(2025, 10, 15, tzinfo=UTC), 3) == datetime(
        2026, 1, 15, tzinfo=UTC
    )


# --- the HR grant ----------------------------------------------------------


async def test_hr_grant_lets_a_locked_candidate_apply_again(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    ctx = await _bootstrap(client, "reapply-grant")
    candidate_id = await _seed_applicant(
        db_session, ctx, email="locked@reapply-grant.dev", applied_at=_months_ago(1)
    )

    granted = await client.post(
        f"/api/v1/recruiter/candidates/{candidate_id}/reapply-grants",
        json={"reason": "Completed a relevant certification since applying."},
        headers=ctx["headers"],
    )
    assert granted.status_code == 201, granted.text
    body = granted.json()
    assert body["used_at"] is None
    # Who granted it, and why, is part of the record — not only the activity.
    assert body["granted_by_name"] == "Acme Admin"
    assert body["reason"].startswith("Completed a relevant certification")

    status = await _status(client, ctx, candidate_id)
    assert status["can_self_apply_now"] is True
    assert status["open_grant"]["id"] == body["id"]


async def test_grant_is_refused_when_there_is_no_restriction_to_lift(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    ctx = await _bootstrap(client, "reapply-grant-noop")
    candidate_id = await _seed_applicant(
        db_session, ctx, email="free@reapply-grant-noop.dev", applied_at=_months_ago(4)
    )

    response = await client.post(
        f"/api/v1/recruiter/candidates/{candidate_id}/reapply-grants",
        json={"reason": "Not needed."},
        headers=ctx["headers"],
    )
    assert response.status_code == 409, response.text


async def test_only_one_grant_may_be_open_at_a_time(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    ctx = await _bootstrap(client, "reapply-grant-twice")
    candidate_id = await _seed_applicant(
        db_session, ctx, email="twice@reapply-grant-twice.dev", applied_at=_months_ago(1)
    )
    url = f"/api/v1/recruiter/candidates/{candidate_id}/reapply-grants"

    first = await client.post(url, json={"reason": "First."}, headers=ctx["headers"])
    assert first.status_code == 201, first.text

    second = await client.post(url, json={"reason": "Second."}, headers=ctx["headers"])
    assert second.status_code == 409, second.text


async def test_grant_is_single_use_and_preserves_history(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    """Consuming the grant stamps it and points at the application that
    spent it; the earlier application is left untouched, and the candidate
    is locked again afterwards."""
    ctx = await _bootstrap(client, "reapply-grant-consumed")
    candidate_id = await _seed_applicant(
        db_session, ctx, email="consume@reapply-grant-consumed.dev", applied_at=_months_ago(1)
    )
    granted = await client.post(
        f"/api/v1/recruiter/candidates/{candidate_id}/reapply-grants",
        json={"reason": "Allowed once."},
        headers=ctx["headers"],
    )
    assert granted.status_code == 201, granted.text

    # The candidate's next self-service application spends the grant.
    second_job = await client.post(
        "/api/v1/recruiter/jobs",
        json={"title": "Platform Engineer", "description": "Runs the platform."},
        headers=ctx["headers"],
    )
    async with rls_bypass(db_session):
        new_application = Application(
            organization_id=ctx["org_id"],
            candidate_id=candidate_id,
            job_id=uuid.UUID(second_job.json()["id"]),
            status=ApplicationStatus.APPLIED,
            source=ApplicationSource.PORTAL,
            applied_at=datetime.now(UTC),
            is_self_service=True,
        )
        db_session.add(new_application)
        await db_session.flush()
    async with rls_bypass(db_session):
        candidate = await db_session.get(Candidate, candidate_id)
        assert candidate is not None
        await reapply_service.consume_open_grant(
            db_session,
            organization_id=ctx["org_id"],
            candidate=candidate,
            application_id=new_application.id,
        )

    async with rls_bypass(db_session):
        grant = await db_session.scalar(
            select(CandidateReapplyGrant).where(
                CandidateReapplyGrant.candidate_id == candidate_id
            )
        )
        assert grant is not None
        assert grant.used_at is not None
        assert grant.used_by_application_id == new_application.id
        # Nothing was destroyed: both applications are still there.
        applications = (
            await db_session.scalars(
                select(Application).where(Application.candidate_id == candidate_id)
            )
        ).all()
        assert len(applications) == 2

    # Spent: the window applies again, measured from the new application.
    status = await _status(client, ctx, candidate_id)
    assert status["open_grant"] is None
    assert status["can_self_apply_now"] is False


# --- security boundaries ---------------------------------------------------


async def test_reapply_endpoints_are_tenant_isolated(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    """Another organization's admin sees a candidate id as simply absent —
    404, exactly like an id that never existed."""
    org_a = await _bootstrap(client, "reapply-tenant-a")
    org_b = await _bootstrap(client, "reapply-tenant-b")
    candidate_id = await _seed_applicant(
        db_session, org_a, email="theirs@reapply-tenant-a.dev", applied_at=_months_ago(1)
    )

    leaked_status = await client.get(
        f"/api/v1/recruiter/candidates/{candidate_id}/reapply-status",
        headers=org_b["headers"],
    )
    assert leaked_status.status_code == 404, leaked_status.text

    leaked_grant = await client.post(
        f"/api/v1/recruiter/candidates/{candidate_id}/reapply-grants",
        json={"reason": "Not mine to give."},
        headers=org_b["headers"],
    )
    assert leaked_grant.status_code == 404, leaked_grant.text

    # ...and nothing was written for the other tenant's candidate.
    async with rls_bypass(db_session):
        assert (
            await db_session.scalar(
                select(CandidateReapplyGrant).where(
                    CandidateReapplyGrant.candidate_id == candidate_id
                )
            )
            is None
        )

    # The 404s above are isolation, not a missing row: the owning
    # organization still reads the very same candidate.
    owner_view = await _status(client, org_a, candidate_id)
    assert owner_view["can_self_apply_now"] is False


async def test_granting_reapply_requires_the_permission(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    """`candidate.reapply.grant` is held by ORG_ADMIN and RECRUITER only."""
    ctx = await _bootstrap(client, "reapply-authz")
    candidate_id = await _seed_applicant(
        db_session, ctx, email="authz@reapply-authz.dev", applied_at=_months_ago(1)
    )
    url = f"/api/v1/recruiter/candidates/{candidate_id}/reapply-grants"

    anonymous = await client.post(url, json={"reason": "No token."})
    assert anonymous.status_code == 401, anonymous.text

    interviewer = await _create_staff(
        client, ctx, email="interviewer@reapply-authz.dev", role="INTERVIEWER"
    )
    forbidden = await client.post(url, json={"reason": "Not my call."}, headers=interviewer)
    assert forbidden.status_code == 403, forbidden.text

    recruiter = await _create_staff(
        client, ctx, email="recruiter@reapply-authz.dev", role="RECRUITER"
    )
    allowed = await client.post(url, json={"reason": "Recruiter's call."}, headers=recruiter)
    assert allowed.status_code == 201, allowed.text


async def test_grant_requires_a_reason(
    client: AsyncClient, db_session: AsyncSession, super_admin
) -> None:
    """The reason is what the audit trail shows, so it can't be blank."""
    ctx = await _bootstrap(client, "reapply-reason")
    candidate_id = await _seed_applicant(
        db_session, ctx, email="reason@reapply-reason.dev", applied_at=_months_ago(1)
    )

    response = await client.post(
        f"/api/v1/recruiter/candidates/{candidate_id}/reapply-grants",
        json={"reason": "   "},
        headers=ctx["headers"],
    )
    assert response.status_code == 422, response.text

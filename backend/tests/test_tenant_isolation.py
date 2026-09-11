"""Tenant isolation is a hard security requirement (CLAUDE.md § 2,
docs/security.md § 3): Tenant A must never be able to read or write Tenant
B's data, enforced at the database layer via Postgres Row-Level Security —
not merely by application code remembering to filter.

These tests exercise the raw RLS policies directly (bypassing any
application-layer filtering), because the point is to prove the *database*
itself refuses cross-tenant access even if a future application bug forgot
to scope a query.
"""

import uuid

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.rls import set_rls_bypass, set_tenant_context
from app.models.organization import Organization
from app.models.user import User


async def _create_org_with_user(session: AsyncSession, slug: str) -> tuple[uuid.UUID, uuid.UUID]:
    await set_rls_bypass(session, enabled=True)
    org = Organization(name=slug, slug=slug)
    session.add(org)
    await session.flush()

    user = User(
        organization_id=org.id,
        email=f"user@{slug}.test",
        hashed_password="x",
        full_name="Test User",
    )
    session.add(user)
    await session.flush()
    await set_rls_bypass(session, enabled=False)
    return org.id, user.id


async def test_no_tenant_context_returns_zero_rows(db_session: AsyncSession) -> None:
    """Fail-closed: if the application ever forgets to set the tenant
    context, the database must return nothing rather than everything.
    """
    await _create_org_with_user(db_session, "fail-closed-co")

    result = await db_session.execute(select(User))
    assert result.scalars().all() == []


async def test_tenant_cannot_see_another_tenants_users(db_session: AsyncSession) -> None:
    org_a_id, user_a_id = await _create_org_with_user(db_session, "org-a-iso")
    org_b_id, user_b_id = await _create_org_with_user(db_session, "org-b-iso")

    await set_tenant_context(db_session, org_a_id)
    visible_as_a = (await db_session.execute(select(User.id))).scalars().all()
    assert visible_as_a == [user_a_id]

    await set_tenant_context(db_session, org_b_id)
    visible_as_b = (await db_session.execute(select(User.id))).scalars().all()
    assert visible_as_b == [user_b_id]


async def test_tenant_cannot_write_into_another_tenant(db_session: AsyncSession) -> None:
    """The RLS policy's WITH CHECK clause, not just USING, must block a
    cross-tenant write (e.g. a bug that inserts a row with the wrong
    organization_id while the session is scoped to a different tenant).
    """
    org_a_id, _ = await _create_org_with_user(db_session, "org-a-write")
    org_b_id, _ = await _create_org_with_user(db_session, "org-b-write")

    await set_tenant_context(db_session, org_a_id)
    rogue_user = User(
        organization_id=org_b_id,
        email="rogue@org-b-write.test",
        hashed_password="x",
        full_name="Rogue",
    )
    db_session.add(rogue_user)

    try:
        await db_session.flush()
        raised = False
    except DBAPIError:
        raised = True
        await db_session.rollback()

    assert raised, "inserting a row for another tenant must be rejected by RLS"


async def test_bypass_sees_all_tenants(db_session: AsyncSession) -> None:
    await _create_org_with_user(db_session, "org-a-bypass")
    await _create_org_with_user(db_session, "org-b-bypass")

    await set_rls_bypass(db_session, enabled=True)
    count = (await db_session.execute(text("SELECT count(*) FROM users"))).scalar_one()
    assert count == 2

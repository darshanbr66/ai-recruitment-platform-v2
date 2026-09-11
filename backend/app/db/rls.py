"""Row-Level Security helpers.

Two things live here:

1. `enable_tenant_rls` / `disable_tenant_rls` — used from Alembic migrations
   to attach the standard tenant-isolation policy to a table. Every
   migration that creates a tenant-owned table calls this instead of
   hand-writing policy SQL, so the isolation rule is identical everywhere.

2. `set_tenant_context` / `set_rls_bypass` — used at request time (wired in
   from Phase 2 onward, once an authenticated principal exists) to set the
   Postgres session variables the policies key off. Session variables are
   set with `SET LOCAL`, so they only apply for the current transaction.

Fail-closed by design: if `app.current_org_id` is never set (e.g. a bug
skips it), `current_setting(..., true)` returns NULL, the equality check in
the policy evaluates to NULL/false, and the query returns zero rows rather
than every tenant's data.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CURRENT_ORG_SETTING = "app.current_org_id"
BYPASS_SETTING = "app.bypass_rls"


def enable_tenant_rls(
    op: object,
    table_name: str,
    *,
    org_column: str = "organization_id",
    null_visible_to_all_tenants: bool = False,
) -> None:
    """Enable + force RLS on `table_name` and attach a fail-closed tenant
    isolation policy.

    `null_visible_to_all_tenants`: set True only for tables where a NULL
    `org_column` legitimately means "shared across all tenants" (e.g. system
    roles). Leave False (default) when NULL means something restricted, like
    a platform-level user row that must stay invisible to ordinary tenants.

    `FORCE ROW LEVEL SECURITY` is required in addition to `ENABLE`, because
    the application DB role owns the tables it migrates and table owners
    bypass RLS by default unless forced.
    """
    null_clause = f"{org_column} IS NULL OR " if null_visible_to_all_tenants else ""
    predicate = (
        f"current_setting('{BYPASS_SETTING}', true) = 'on' "
        f"OR {null_clause}{org_column} = "
        f"NULLIF(current_setting('{CURRENT_ORG_SETTING}', true), '')::uuid"
    )

    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")  # type: ignore[attr-defined]
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")  # type: ignore[attr-defined]
    op.execute(  # type: ignore[attr-defined]
        f"CREATE POLICY tenant_isolation ON {table_name} "
        f"FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
    )


def enable_indirect_tenant_rls(
    op: object,
    table_name: str,
    *,
    exists_subquery: str,
) -> None:
    """For join tables with no `organization_id` of their own (e.g.
    `role_permissions`, `user_roles`), where tenancy is derived through a
    foreign key to a table that does have one.

    `exists_subquery` must be a full `EXISTS (...)` clause referencing the
    outer table's columns (e.g. `role_id`).
    """
    predicate = f"current_setting('{BYPASS_SETTING}', true) = 'on' OR {exists_subquery}"

    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")  # type: ignore[attr-defined]
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")  # type: ignore[attr-defined]
    op.execute(  # type: ignore[attr-defined]
        f"CREATE POLICY tenant_isolation ON {table_name} "
        f"FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
    )


def disable_tenant_rls(op: object, table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}")  # type: ignore[attr-defined]
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")  # type: ignore[attr-defined]


async def set_tenant_context(session: AsyncSession, organization_id: uuid.UUID | None) -> None:
    """Scope the current transaction to one tenant. Pass None to clear
    (queries will then see zero rows on any RLS-protected table).

    Uses `set_config(..., true)` rather than `SET LOCAL <name> = :param`
    because plain `SET` does not accept a bind parameter — only a literal —
    while `set_config` is a normal function call and takes one safely.
    """
    await session.execute(
        text(f"SELECT set_config('{CURRENT_ORG_SETTING}', :org_id, true)"),
        {"org_id": str(organization_id) if organization_id else ""},
    )


async def set_rls_bypass(session: AsyncSession, *, enabled: bool) -> None:
    """Only for verified SUPER_ADMIN / platform-admin code paths. The caller
    is responsible for the authorization check — this function does not
    perform one.
    """
    await session.execute(
        text(f"SELECT set_config('{BYPASS_SETTING}', :value, true)"),
        {"value": "on" if enabled else "off"},
    )


@asynccontextmanager
async def rls_bypass(session: AsyncSession) -> AsyncIterator[None]:
    """Scope a Postgres RLS bypass to a single block of code, then restore
    the previous state.

    Used ONLY for the narrow, well-precedented cases the RLS design already
    anticipated: resolving *who a caller is* before a tenant is known (e.g.
    looking up a user by id from a JWT subject, or by email/refresh-token
    hash at login — none of which can be scoped to a tenant in advance), and
    genuine platform-admin operations (e.g. creating an Organization, which
    by definition cannot be scoped to a tenant that doesn't exist yet). Every
    call site using this must be able to point at one of those two
    justifications — it is not a general-purpose "skip RLS" escape hatch.

    Restores bypass to OFF afterward (not to whatever it was before), which
    is correct for every current call site — none of them are nested.
    """
    await set_rls_bypass(session, enabled=True)
    try:
        yield
    finally:
        await set_rls_bypass(session, enabled=False)

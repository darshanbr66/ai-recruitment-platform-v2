"""Data-safety guards of the candidate-intake migration (b4c5d6e7f8a9):

- existing phones are normalized to E.164, but a collision that only appears
  *after* normalization ("98765 43210" vs "+919876543210" in one
  organization) stops the migration with nothing rewritten, instead of
  letting the unique index be built over a hidden duplicate;
- the downgrade refuses to run while data uses AI_SCREENED_OUT / HR_MATCH,
  rather than rewriting application status history.

Runs the real migration module's helpers against the test transaction, which
the fixtures roll back, so no data survives the test.
"""

import importlib.util
import uuid
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.db.rls import rls_bypass
from app.models.user import User
from app.services import screening_service
from tests.public_apply import apply_publicly
from tests.test_candidate_intake import _StubScreeningProvider
from tests.test_public_applications import _bootstrap_org_with_open_job

MIGRATION_FILE = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "b4c5d6e7f8a9_candidate_intake_hr_requirements.py"
)


def _load_migration() -> Any:
    spec = importlib.util.spec_from_file_location("candidate_intake_migration", MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run_helper(db_connection: AsyncConnection, helper: str) -> None:
    """Runs one migration helper the way `upgrade()`/`downgrade()` do: with
    the RLS bypass on (transaction-local here, so it can't leak)."""
    module = _load_migration()

    def run(sync_connection: Any) -> None:
        sync_connection.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        try:
            with Operations.context(MigrationContext.configure(sync_connection)):
                getattr(module, helper)()
        finally:
            sync_connection.execute(text("SELECT set_config('app.bypass_rls', 'off', true)"))

    await db_connection.run_sync(run)


async def _org_id(db_session: AsyncSession, slug: str) -> uuid.UUID:
    async with rls_bypass(db_session):
        org_id = await db_session.scalar(
            text("SELECT id FROM organizations WHERE slug = :slug"), {"slug": slug}
        )
    assert org_id is not None
    return uuid.UUID(str(org_id))


async def _insert_candidate(
    db_session: AsyncSession, org_id: uuid.UUID, email: str, phone: str | None
) -> uuid.UUID:
    """A pre-migration row: phone stored exactly as legacy data had it."""
    async with rls_bypass(db_session):
        candidate_id = await db_session.scalar(
            text(
                "INSERT INTO candidates (organization_id, email, full_name, phone) "
                "VALUES (:org, :email, 'Legacy Candidate', :phone) RETURNING id"
            ),
            {"org": org_id, "email": email, "phone": phone},
        )
    return uuid.UUID(str(candidate_id))


async def _phones(db_session: AsyncSession, ids: list[uuid.UUID]) -> list[str | None]:
    async with rls_bypass(db_session):
        rows = await db_session.execute(
            text("SELECT id, phone FROM candidates WHERE id = ANY(:ids)"), {"ids": ids}
        )
    by_id = {uuid.UUID(str(row_id)): phone for row_id, phone in rows.tuples().all()}
    return [by_id[candidate_id] for candidate_id in ids]


async def test_collision_after_normalization_stops_the_migration_and_rewrites_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
    db_connection: AsyncConnection,
    super_admin: User,
) -> None:
    ctx = await _bootstrap_org_with_open_job(client, "migration-phone-collision")
    org = await _org_id(db_session, ctx["slug"])
    ids = [
        await _insert_candidate(db_session, org, "legacy-a@example.com", "98765 43210"),
        await _insert_candidate(db_session, org, "legacy-b@example.com", "+919876543210"),
        await _insert_candidate(db_session, org, "legacy-c@example.com", "(080) 2222-3333"),
    ]

    with pytest.raises(RuntimeError) as failure:
        await _run_helper(db_connection, "_normalize_existing_phones")

    message = str(failure.value)
    assert "1 mobile number(s)" in message
    assert str(ids[0]) in message and str(ids[1]) in message
    assert "9876543210" not in message  # candidate ids only, never the number
    # All-or-nothing: not even the unrelated row was rewritten.
    assert await _phones(db_session, ids) == ["98765 43210", "+919876543210", "(080) 2222-3333"]


async def test_phones_are_normalized_when_no_collision_exists(
    client: AsyncClient,
    db_session: AsyncSession,
    db_connection: AsyncConnection,
    super_admin: User,
) -> None:
    org_a = await _org_id(
        db_session, (await _bootstrap_org_with_open_job(client, "migration-phone-a"))["slug"]
    )
    org_b = await _org_id(
        db_session, (await _bootstrap_org_with_open_job(client, "migration-phone-b"))["slug"]
    )
    ids = [
        await _insert_candidate(db_session, org_a, "legacy-a@example.com", "98765 43210"),
        # The same number in a *different* organization is not a collision.
        await _insert_candidate(db_session, org_b, "legacy-b@example.com", "0091 98765-43210"),
        # No digits at all can't identify anyone.
        await _insert_candidate(db_session, org_a, "legacy-c@example.com", "  n/a "),
        await _insert_candidate(db_session, org_a, "legacy-d@example.com", None),
    ]

    await _run_helper(db_connection, "_normalize_existing_phones")

    assert await _phones(db_session, ids) == ["+919876543210", "+919876543210", None, None]


async def _screened_out_counts(db_session: AsyncSession) -> tuple[int, int]:
    """The two counts the downgrade guard reports, read the same way it does:
    across the whole database, not scoped to one organization."""
    async with rls_bypass(db_session):
        applications = await db_session.scalar(
            text("SELECT count(*) FROM applications WHERE status = 'AI_SCREENED_OUT'")
        )
        history = await db_session.scalar(
            text(
                "SELECT count(*) FROM application_status_history "
                "WHERE from_status = 'AI_SCREENED_OUT' OR to_status = 'AI_SCREENED_OUT'"
            )
        )
    return int(applications or 0), int(history or 0)


async def test_downgrade_refuses_while_ai_screened_out_is_in_use_and_rewrites_nothing(
    client: AsyncClient,
    db_session: AsyncSession,
    db_connection: AsyncConnection,
    super_admin: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard counts AI_SCREENED_OUT/HR_MATCH rows across the whole
    database, so this test cannot assume it starts at zero: any application
    ever screened out — including rows committed outside the test suite
    against the same database — already trips it, correctly. What is asserted
    is therefore that the guard's report *tracks the data*, that it refuses,
    and that it rewrites nothing.
    """
    before_applications, before_history = await _screened_out_counts(db_session)

    provider = _StubScreeningProvider("NOT_MATCH")
    monkeypatch.setattr(screening_service, "get_llm_provider", lambda: provider)
    ctx = await _bootstrap_org_with_open_job(client, "migration-downgrade-guard")
    applied = await apply_publicly(client, ctx["slug"], ctx["job_id"], email="vic@example.com")
    assert applied.status_code == 201, applied.text

    # Our screened-out application added exactly one row to each.
    after = await _screened_out_counts(db_session)
    assert after == (before_applications + 1, before_history + 1)

    with pytest.raises(RuntimeError) as failure:
        await _run_helper(db_connection, "_refuse_downgrade_if_new_enum_values_in_use")

    message = str(failure.value)
    assert f"applications.status = AI_SCREENED_OUT: {after[0]} row(s)" in message
    assert f"application_status_history uses AI_SCREENED_OUT: {after[1]} row(s)" in message
    assert "never rewritten automatically" in message

    # Nothing rewritten: this application's status, its append-only status
    # history, and the database-wide counts are all exactly as before.
    async with rls_bypass(db_session):
        statuses = (
            await db_session.execute(
                text(
                    "SELECT a.status::text FROM applications a "
                    "JOIN organizations o ON o.id = a.organization_id WHERE o.slug = :slug"
                ),
                {"slug": ctx["slug"]},
            )
        ).scalars().all()
        history = (
            await db_session.execute(
                text(
                    "SELECT h.to_status::text FROM application_status_history h "
                    "JOIN applications a ON a.id = h.application_id "
                    "JOIN organizations o ON o.id = a.organization_id "
                    "WHERE o.slug = :slug ORDER BY h.created_at"
                ),
                {"slug": ctx["slug"]},
            )
        ).scalars().all()
    assert statuses == ["AI_SCREENED_OUT"]  # untouched
    assert history[-1] == "AI_SCREENED_OUT"  # history still ends at the screen-out
    assert await _screened_out_counts(db_session) == after

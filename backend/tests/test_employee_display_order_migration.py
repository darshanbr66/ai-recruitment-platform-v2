"""The `employees.display_order` migration numbers pre-existing employees in
the order they were created — not alphabetically — and is reversible.

Runs the real migration module (its `downgrade()` then `upgrade()`) against
the test transaction, which the fixtures roll back, so no schema change or
data survives the test."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.db.rls import rls_bypass
from app.models.user import User
from tests.test_employee_ordering import _add_all, _department, _org

MIGRATION_FILE = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "a7b8c9d0e1f2_employee_display_order.py"
)
DOMAIN = "migration.dev"


def _load_migration():
    spec = importlib.util.spec_from_file_location("employee_display_order_migration", MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run_migration(db_connection: AsyncConnection, direction: str) -> None:
    module = _load_migration()

    def run(sync_connection) -> None:
        with Operations.context(MigrationContext.configure(sync_connection)):
            getattr(module, direction)()

    await db_connection.run_sync(run)


async def _clear_rls_context(db_session: AsyncSession) -> None:
    """A request earlier in the test leaves its tenant context set for the
    rest of the (outer) transaction. Clear it so the migration is exercised
    the way a real `alembic upgrade` runs: no tenant, no bypass."""
    await db_session.execute(
        text("SELECT set_config('app.current_org_id', '', true), set_config('app.bypass_rls', 'off', true)")
    )


async def _column_state(db_session: AsyncSession) -> tuple[bool, bool, bool]:
    """(column exists, column is NOT NULL, index exists)"""
    column = (
        await db_session.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'employees' AND column_name = 'display_order'"
            )
        )
    ).first()
    index = await db_session.scalar(
        text("SELECT count(*) FROM pg_indexes WHERE indexname = 'ix_employees_org_dept_display_order'")
    )
    return column is not None, column is not None and column[0] == "NO", bool(index)


async def _orders_by_name(db_session: AsyncSession) -> dict[str, int]:
    async with rls_bypass(db_session):
        rows = await db_session.execute(
            text("SELECT full_name, display_order FROM employees WHERE email LIKE :pattern"),
            {"pattern": f"%@{DOMAIN}"},
        )
    return dict(rows.tuples().all())


async def test_existing_employees_are_numbered_in_creation_order_and_the_migration_is_reversible(
    client: AsyncClient, db_session: AsyncSession, db_connection: AsyncConnection, super_admin: User
) -> None:
    _, headers = await _org(client, "ordering-migration")
    engineering = await _department(client, headers, "Engineering")
    data = await _department(client, headers, "Data")

    ids: dict[str, str] = {}
    ids |= await _add_all(client, headers, ["Rajesh", "Yashaswini", "Rajkumar", "Darshan"], engineering, DOMAIN)
    ids |= await _add_all(client, headers, ["Abe", "Zoe"], None, DOMAIN)
    ids |= await _add_all(client, headers, ["Tom", "Tia"], data, DOMAIN)
    # Inactive employees are numbered too, so a reactivation keeps their place.
    await client.post(f"/api/v1/recruiter/employees/{ids['Yashaswini']}/deactivate", json={}, headers=headers)

    # Every row of this test was inserted in one transaction and so shares a
    # `created_at`; give them the "legacy" creation history the migration must
    # honour. It is neither alphabetical nor the order the rows were inserted.
    base = datetime(2026, 1, 1, tzinfo=UTC)
    creation_sequence = ["Yashaswini", "Darshan", "Rajkumar", "Rajesh", "Zoe", "Abe"]
    async with rls_bypass(db_session):
        for step, name in enumerate(creation_sequence):
            await db_session.execute(
                text("UPDATE employees SET created_at = :at WHERE id = :id"),
                {"at": base + timedelta(days=step), "id": ids[name]},
            )
        # Tom and Tia share a timestamp: the tie-break must be deterministic (id).
        for name in ("Tom", "Tia"):
            await db_session.execute(
                text("UPDATE employees SET created_at = :at WHERE id = :id"),
                {"at": base, "id": ids[name]},
            )
    await db_session.flush()

    expected_tie_order = sorted(["Tom", "Tia"], key=lambda name: ids[name])
    expected = {
        "Yashaswini": 1, "Darshan": 2, "Rajkumar": 3, "Rajesh": 4,  # Engineering
        "Zoe": 1, "Abe": 2,  # Unassigned
        expected_tie_order[0]: 1, expected_tie_order[1]: 2,  # Data
    }

    for _ in range(2):  # downgrade -> upgrade twice: reversible, and repeatable
        await _run_migration(db_connection, "downgrade")
        assert await _column_state(db_session) == (False, False, False)

        await _clear_rls_context(db_session)
        await _run_migration(db_connection, "upgrade")

        assert await _column_state(db_session) == (True, True, True)
        assert await _orders_by_name(db_session) == expected

    # The list API then serves that order (rather than A-Z).
    listed = await client.get(f"/api/v1/recruiter/employees?department_id={engineering}", headers=headers)
    assert [row["full_name"] for row in listed.json()] == ["Yashaswini", "Darshan", "Rajkumar", "Rajesh"]

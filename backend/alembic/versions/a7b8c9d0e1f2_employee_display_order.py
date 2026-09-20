"""employee display order for the organization chart

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-20 12:00:00.000000

Adds `employees.display_order`, the hidden position an employee holds among
the others in the same (organization, department) — `department_id IS NULL`
being the "Unassigned" group. The org chart used to sort employees by name;
it now sorts by this column, which admins can rearrange.

Existing rows are numbered 1..n per (organization_id, department_id) in the
order they were created (`created_at`, with `id` as a deterministic
tie-break) — deliberately not alphabetically — and every row is numbered,
including inactive/soft-deleted ones, so a later reactivation keeps its
place. Additive and reversible; the table is never dropped or recreated.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX_NAME = "ix_employees_org_dept_display_order"


def upgrade() -> None:
    # `employees` has FORCE ROW LEVEL SECURITY, which applies to the table
    # owner (the role running this migration) too: without the bypass the
    # backfill below would match zero rows and silently number nothing.
    # Transaction-local, same as de0362764818. The NOT NULL step after the
    # backfill is the safety net — it fails loudly if any row was missed.
    op.execute("SET LOCAL app.bypass_rls = 'on'")

    op.add_column("employees", sa.Column("display_order", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE employees AS e
        SET display_order = ranked.position
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY organization_id, department_id
                       ORDER BY created_at, id
                   ) AS position
            FROM employees
        ) AS ranked
        WHERE e.id = ranked.id
        """
    )
    op.alter_column("employees", "display_order", nullable=False)
    op.create_index(
        _INDEX_NAME, "employees", ["organization_id", "department_id", "display_order"], unique=False
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="employees")
    op.drop_column("employees", "display_order")

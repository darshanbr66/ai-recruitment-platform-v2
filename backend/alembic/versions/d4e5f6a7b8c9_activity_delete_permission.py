"""activity delete permission

Revision ID: d4e5f6a7b8c9
Revises: b1c2d3e4f5a6
Create Date: 2026-09-19 15:00:00.000000

Adds `activity.delete`, granted to ORG_ADMIN only (the same role that holds
`activity.read`). Data-only migration — no schema change. Activity rows
were previously append-only; ORG_ADMIN may now remove entries from their
own organization's log (see app/services/activity_service.py).
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSION_CODE = "activity.delete"
_PERMISSION_DESCRIPTION = "Delete entries from the organization's activity/audit log."
_GRANTED_TO = ("ORG_ADMIN",)


def upgrade() -> None:
    bind = op.get_bind()

    permission_id = str(uuid.uuid4())
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("id", sa.UUID()),
            sa.column("code", sa.String()),
            sa.column("description", sa.Text()),
        ),
        [{"id": permission_id, "code": _PERMISSION_CODE, "description": _PERMISSION_DESCRIPTION}],
    )

    role_ids = [
        row[0]
        for role_name in _GRANTED_TO
        for row in bind.execute(
            sa.text("SELECT id FROM roles WHERE organization_id IS NULL AND name = :name"),
            {"name": role_name},
        )
    ]
    op.bulk_insert(
        sa.table(
            "role_permissions",
            sa.column("role_id", sa.UUID()),
            sa.column("permission_id", sa.UUID()),
        ),
        [{"role_id": role_id, "permission_id": permission_id} for role_id in role_ids],
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = :code)"
        ),
        {"code": _PERMISSION_CODE},
    )
    bind.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": _PERMISSION_CODE})

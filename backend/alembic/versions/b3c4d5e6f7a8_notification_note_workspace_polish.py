"""Notification center + notes workspace polish — broadcast grouping,
target descriptions, note pinning

Revision ID: b3c4d5e6f7a8
Revises: a8b9c0d1e2f3
Create Date: 2026-09-22 21:00:00.000000

Extends the existing `notifications` and `notes` tables (never a parallel
system):

- `notifications.broadcast_group_id` + `.target_description`: let the
  sender's "Sent" tab show one entry per announcement instead of one per
  fanned-out recipient row, and remember who was actually targeted even if
  a department is later renamed/removed.
- `notes.pinned` / `.pinned_at`: persisted pin state for the Notes
  workspace (never faked in browser storage).

No RLS changes — both tables already have tenant RLS enabled by their
original migrations; new columns inherit it automatically.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("broadcast_group_id", sa.UUID(), nullable=True))
    op.create_index(
        "ix_notifications_broadcast_group_id", "notifications", ["broadcast_group_id"]
    )
    op.add_column(
        "notifications", sa.Column("target_description", sa.String(length=255), nullable=True)
    )

    op.add_column(
        "notes",
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("notes", sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_notes_org_pinned", "notes", ["organization_id", "pinned"])


def downgrade() -> None:
    op.drop_index("ix_notes_org_pinned", table_name="notes")
    op.drop_column("notes", "pinned_at")
    op.drop_column("notes", "pinned")

    op.drop_column("notifications", "target_description")
    op.drop_index("ix_notifications_broadcast_group_id", table_name="notifications")
    op.drop_column("notifications", "broadcast_group_id")

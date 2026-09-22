"""Internal notification center — announcements, direct messages, generic
entity links

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-22 19:00:00.000000

Extends the existing `notifications` table/`NotificationType` enum (never a
parallel notification system, per the product direction) with:

- ANNOUNCEMENT / DIRECT_MESSAGE / CALENDAR_REMINDER enum values (the last
  one for Phase E, added here since the enum is already being altered)
- `sender_user_id` (NULL = system-generated, e.g. existing assessment events)
- `related_entity_type` / `related_entity_id` — a generic entity reference,
  the same polymorphic pattern `activities.entity_type`/`entity_id` already
  uses, so "open the related item" works for any notification type
- `notification.announce` (ORG_ADMIN only) and `notification.send` (every
  system role) permissions

`ALTER TYPE ... ADD VALUE` runs fine inside Alembic's transactional DDL on
PG12+ as long as the new value isn't used in the same transaction (it isn't
here) — no type-rename dance needed, unlike removing a value.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSIONS = (
    ("notification.announce", "Send an announcement to everyone, a department, or selected employees."),
    ("notification.send", "Send a direct internal message to another portal user."),
)
_ROLE_PERMISSIONS = {
    "ORG_ADMIN": ("notification.announce", "notification.send"),
    "RECRUITER": ("notification.send",),
    "HIRING_MANAGER": ("notification.send",),
    "INTERVIEWER": ("notification.send",),
}


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'ANNOUNCEMENT'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'DIRECT_MESSAGE'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'CALENDAR_REMINDER'")

    op.add_column("notifications", sa.Column("sender_user_id", sa.UUID(), nullable=True))
    op.add_column("notifications", sa.Column("related_entity_type", sa.String(length=50), nullable=True))
    op.add_column("notifications", sa.Column("related_entity_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_notifications_sender_user_id_users"),
        "notifications", "users", ["sender_user_id"], ["id"], ondelete="SET NULL",
    )

    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.UUID()),
        sa.column("code", sa.String()),
        sa.column("description", sa.Text()),
    )
    permission_ids = {code: str(uuid.uuid4()) for code, _ in _PERMISSIONS}
    op.bulk_insert(
        permissions_table,
        [
            {"id": permission_ids[code], "code": code, "description": description}
            for code, description in _PERMISSIONS
        ],
    )

    role_ids = {
        name: row[0]
        for name in _ROLE_PERMISSIONS
        for row in bind.execute(
            sa.text("SELECT id FROM roles WHERE organization_id IS NULL AND name = :name"),
            {"name": name},
        )
    }

    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.UUID()),
        sa.column("permission_id", sa.UUID()),
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {"role_id": role_ids[role_name], "permission_id": permission_ids[code]}
            for role_name, codes in _ROLE_PERMISSIONS.items()
            for code in codes
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = ANY(:codes))"
        ),
        {"codes": [code for code, _ in _PERMISSIONS]},
    )
    connection.execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"),
        {"codes": [code for code, _ in _PERMISSIONS]},
    )

    op.drop_constraint(op.f("fk_notifications_sender_user_id_users"), "notifications", type_="foreignkey")
    op.drop_column("notifications", "related_entity_id")
    op.drop_column("notifications", "related_entity_type")
    op.drop_column("notifications", "sender_user_id")

    # New enum VALUES are intentionally left in place on downgrade: Postgres
    # has no ALTER TYPE ... DROP VALUE, and removing them would require the
    # same rename-recreate dance c1a2f3b4d5e6 uses for a real value merge —
    # out of proportion for reverting this one additive migration.

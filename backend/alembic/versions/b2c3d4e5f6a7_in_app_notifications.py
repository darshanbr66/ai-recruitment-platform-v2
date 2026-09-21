"""in-app notifications (assessment started / submitted)

Revision ID: b2c3d4e5f6a7
Revises: a7b8c9d0e1f2
Create Date: 2026-09-21 10:00:00.000000

Adds `notifications`: an in-app notification addressed to one staff user (the
inviter of an assessment invitation). Tenant-owned (`organization_id`, standard
`tenant_isolation` RLS policy). The unique index on
`(assessment_invitation_id, type)` is what makes "notify once per event" a
database guarantee. No existing table is altered.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import disable_tenant_rls, enable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOTIFICATION_TYPES = ("ASSESSMENT_STARTED", "ASSESSMENT_SUBMITTED")


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("recipient_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(*_NOTIFICATION_TYPES, name="notification_type"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("assessment_invitation_id", sa.UUID(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_notifications_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"], ["users.id"],
            name=op.f("fk_notifications_recipient_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_invitation_id"], ["assessment_invitations.id"],
            name=op.f("fk_notifications_assessment_invitation_id_assessment_invitations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        op.f("ix_notifications_organization_id"), "notifications", ["organization_id"], unique=False
    )
    op.create_index(
        "uq_notifications_invitation_type",
        "notifications", ["assessment_invitation_id", "type"], unique=True,
    )
    op.create_index(
        "ix_notifications_recipient_unread",
        "notifications", ["recipient_user_id", "created_at"], unique=False,
        postgresql_where=sa.text("read_at IS NULL"),
    )

    enable_tenant_rls(op, "notifications")


def downgrade() -> None:
    connection = op.get_bind()
    disable_tenant_rls(op, "notifications")
    op.drop_index("ix_notifications_recipient_unread", table_name="notifications")
    op.drop_index("uq_notifications_invitation_type", table_name="notifications")
    op.drop_index(op.f("ix_notifications_organization_id"), table_name="notifications")
    op.drop_table("notifications")
    sa.Enum(name="notification_type").drop(connection, checkfirst=True)

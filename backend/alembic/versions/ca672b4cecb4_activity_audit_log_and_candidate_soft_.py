"""activity audit log and candidate soft delete

Revision ID: ca672b4cecb4
Revises: de0362764818
Create Date: 2026-09-17 13:30:30.238548

Adds the `activities` table (append-only audit trail — see
app/models/activity.py) and soft-delete columns on `candidates` (deleting a
candidate must not destroy historical Application/Note/AssessmentInvitation
records that point at them, and applications.candidate_id is ON DELETE
RESTRICT anyway the moment a candidate has any application).
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.db.rls import enable_tenant_rls, disable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = 'ca672b4cecb4'
down_revision: Union[str, None] = 'de0362764818'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSIONS = (
    ("candidate.delete", "Delete (archive) a candidate, with a required reason."),
    ("activity.read", "View the organization's activity/audit log."),
)
_ROLE_PERMISSIONS = {
    "ORG_ADMIN": ("candidate.delete", "activity.read"),
    "RECRUITER": ("candidate.delete",),
}


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("candidates", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidates", sa.Column("deleted_by_user_id", sa.UUID(), nullable=True))
    op.add_column("candidates", sa.Column("deletion_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_candidates_deleted_by_user_id_users"),
        "candidates",
        "users",
        ["deleted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "activities",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("entity_label", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_activities_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"],
            name=op.f("fk_activities_actor_user_id_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activities")),
    )
    op.create_index(op.f("ix_activities_organization_id"), "activities", ["organization_id"], unique=False)
    op.create_index(op.f("ix_activities_action"), "activities", ["action"], unique=False)
    op.create_index(op.f("ix_activities_entity_type"), "activities", ["entity_type"], unique=False)
    op.create_index("ix_activities_org_created_at", "activities", ["organization_id", "created_at"], unique=False)

    enable_tenant_rls(op, "activities")

    # --- Permissions ---
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

    disable_tenant_rls(op, "activities")
    op.drop_table("activities")

    op.drop_constraint(
        op.f("fk_candidates_deleted_by_user_id_users"), "candidates", type_="foreignkey"
    )
    op.drop_column("candidates", "deletion_reason")
    op.drop_column("candidates", "deleted_by_user_id")
    op.drop_column("candidates", "deleted_at")

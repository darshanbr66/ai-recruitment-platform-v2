"""delete/archive columns for jobs, applications, assessments, campus drives; team management permission

Revision ID: 7b8857298c92
Revises: fedb70899161
Create Date: 2026-09-17 18:00:00.000000

Extends the soft-delete pattern already used by `candidates`
(ca672b4cecb4) to `jobs`, `applications`, `assessments` and
`campus_drives` — each of these has downstream history (applications,
assessment invitations/results, application status history, notes) that
must survive a "Delete" click in the UI, so this is archive-in-place, not
a real DROP. See each model's updated docstring in app/models/.

Also adds `user.update`, the permission gating team-member
deactivate/reactivate/role-change (app/services/user_service.py) — kept
ORG_ADMIN-only, unlike the `*.delete` permissions below which mirror
`candidate.delete`'s ORG_ADMIN + RECRUITER grant.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7b8857298c92'
down_revision: Union[str, None] = 'fedb70899161'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SOFT_DELETE_TABLES = ("jobs", "applications", "assessments", "campus_drives")

_PERMISSIONS = (
    ("job.delete", "Delete (archive) a job requisition, with a required reason."),
    ("application.delete", "Delete (archive) an application, with a required reason."),
    ("assessment.delete", "Delete (archive) an assessment, with a required reason."),
    ("campus_drive.delete", "Delete (archive) a campus drive, with a required reason."),
    ("user.update", "Deactivate/reactivate a team member or change their role."),
)
_ROLE_PERMISSIONS = {
    "ORG_ADMIN": (
        "job.delete", "application.delete", "assessment.delete", "campus_drive.delete",
        "user.update",
    ),
    "RECRUITER": (
        "job.delete", "application.delete", "assessment.delete", "campus_drive.delete",
    ),
}


def upgrade() -> None:
    bind = op.get_bind()

    for table in _SOFT_DELETE_TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("deleted_by_user_id", sa.UUID(), nullable=True))
        op.add_column(table, sa.Column("deletion_reason", sa.Text(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_deleted_by_user_id_users"),
            table,
            "users",
            ["deleted_by_user_id"],
            ["id"],
            ondelete="SET NULL",
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

    for table in _SOFT_DELETE_TABLES:
        op.drop_constraint(op.f(f"fk_{table}_deleted_by_user_id_users"), table, type_="foreignkey")
        op.drop_column(table, "deletion_reason")
        op.drop_column(table, "deleted_by_user_id")
        op.drop_column(table, "deleted_at")

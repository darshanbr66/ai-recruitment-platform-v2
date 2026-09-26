"""Candidate 3-month reapply window + HR early-reapply grants; Talk to Admin

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-09-25 10:00:00.000000

- `applications.is_self_service` — true only for an application the
  candidate submitted through the email-verified self-service flow. The
  3-month self-apply rule counts only these. Backfilled conservatively:
  an existing row is marked self-service only when its source is PORTAL or
  CAMPUS_IMPORT *and* its initial status-history row was written by the
  system (no staff actor) — exactly what the self-service flow produces.
  Staff-created applications (a named actor), HR matches and recruiter-added
  rows stay false, so HR-created candidates are never locked out by history
  they didn't create. No existing application is otherwise modified.
- New tenant-scoped `candidate_reapply_grants` (HR allowing one candidate an
  early, single-use reapply; RLS enabled with the standard policy).
- New tenant-scoped `admin_conversations` / `admin_messages` (Talk to Admin;
  RLS enabled with the standard policy).
- Permissions: `candidate.reapply.grant` (ORG_ADMIN, RECRUITER),
  `admin_message.send` (RECRUITER, HIRING_MANAGER, INTERVIEWER),
  `admin_message.manage` (ORG_ADMIN).
"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import disable_tenant_rls, enable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "candidate.reapply.grant",
        "Allow a candidate to self-apply again before the reapply window has passed.",
        ("ORG_ADMIN", "RECRUITER"),
    ),
    (
        "admin_message.send",
        "Message the organization's admins through Talk to Admin.",
        ("RECRUITER", "HIRING_MANAGER", "INTERVIEWER"),
    ),
    (
        "admin_message.manage",
        "Read and reply to staff Talk to Admin conversations.",
        ("ORG_ADMIN",),
    ),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            name,
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        )
        for name in ("created_at", "updated_at")
    ]


def _seed_permissions() -> None:
    bind = op.get_bind()
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.UUID()),
        sa.column("code", sa.String()),
        sa.column("description", sa.Text()),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.UUID()),
        sa.column("permission_id", sa.UUID()),
    )
    for code, description, roles in _PERMISSIONS:
        permission_id = str(uuid.uuid4())
        op.bulk_insert(
            permissions, [{"id": permission_id, "code": code, "description": description}]
        )
        role_ids = [
            row[0]
            for role_name in roles
            for row in bind.execute(
                sa.text("SELECT id FROM roles WHERE organization_id IS NULL AND name = :name"),
                {"name": role_name},
            )
        ]
        op.bulk_insert(
            role_permissions,
            [{"role_id": role_id, "permission_id": permission_id} for role_id in role_ids],
        )


def upgrade() -> None:
    # Every tenant-owned table FORCEs RLS, which applies to this migration's
    # own backfill too (same as b4c5d6e7f8a9).
    op.execute("SET app.bypass_rls = 'on'")

    op.add_column(
        "applications",
        sa.Column("is_self_service", sa.Boolean(), server_default="false", nullable=False),
    )
    op.execute(
        """
        UPDATE applications a SET is_self_service = true
        WHERE a.source IN ('PORTAL', 'CAMPUS_IMPORT')
          AND EXISTS (
              SELECT 1 FROM application_status_history h
              WHERE h.application_id = a.id
                AND h.from_status IS NULL
                AND h.changed_by_user_id IS NULL
          )
        """
    )
    # The reapply check: a candidate's self-service applications, newest first.
    op.create_index(
        "ix_applications_candidate_self_service",
        "applications",
        ["candidate_id", "applied_at"],
        postgresql_where=sa.text("is_self_service"),
    )

    op.create_table(
        "candidate_reapply_grants",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_application_id", sa.UUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["used_by_application_id"], ["applications.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_reapply_grants_organization_id",
        "candidate_reapply_grants",
        ["organization_id"],
    )
    op.create_index(
        "ix_candidate_reapply_grants_candidate_id", "candidate_reapply_grants", ["candidate_id"]
    )
    op.create_index(
        "uq_candidate_reapply_grants_open",
        "candidate_reapply_grants",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL"),
    )
    enable_tenant_rls(op, "candidate_reapply_grants")

    op.create_table(
        "admin_conversations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("employee_user_id", sa.UUID(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_conversations_organization_id", "admin_conversations", ["organization_id"]
    )
    op.create_index(
        "uq_admin_conversations_org_employee",
        "admin_conversations",
        ["organization_id", "employee_user_id"],
        unique=True,
    )
    enable_tenant_rls(op, "admin_conversations")

    op.create_table(
        "admin_messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("sender_user_id", sa.UUID(), nullable=True),
        sa.Column("from_admin", sa.Boolean(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_by_user_id", sa.UUID(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["admin_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["read_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_messages_organization_id", "admin_messages", ["organization_id"])
    op.create_index(
        "ix_admin_messages_conversation_created",
        "admin_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_admin_messages_unread",
        "admin_messages",
        ["conversation_id", "from_admin"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    enable_tenant_rls(op, "admin_messages")

    _seed_permissions()

    op.execute("SET app.bypass_rls = 'off'")


def downgrade() -> None:
    """Drops the new tables — their rows (grants, staff messages) exist only
    in this revision and go with them — and the backfilled column. No
    application or candidate row is touched."""
    op.execute("SET app.bypass_rls = 'on'")

    bind = op.get_bind()
    for code, _description, _roles in _PERMISSIONS:
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE code = :code)"
            ),
            {"code": code},
        )
        bind.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})

    disable_tenant_rls(op, "admin_messages")
    op.drop_index("ix_admin_messages_unread", table_name="admin_messages")
    op.drop_index("ix_admin_messages_conversation_created", table_name="admin_messages")
    op.drop_index("ix_admin_messages_organization_id", table_name="admin_messages")
    op.drop_table("admin_messages")

    disable_tenant_rls(op, "admin_conversations")
    op.drop_index("uq_admin_conversations_org_employee", table_name="admin_conversations")
    op.drop_index("ix_admin_conversations_organization_id", table_name="admin_conversations")
    op.drop_table("admin_conversations")

    disable_tenant_rls(op, "candidate_reapply_grants")
    op.drop_index("uq_candidate_reapply_grants_open", table_name="candidate_reapply_grants")
    op.drop_index(
        "ix_candidate_reapply_grants_candidate_id", table_name="candidate_reapply_grants"
    )
    op.drop_index(
        "ix_candidate_reapply_grants_organization_id", table_name="candidate_reapply_grants"
    )
    op.drop_table("candidate_reapply_grants")

    op.drop_index("ix_applications_candidate_self_service", table_name="applications")
    op.drop_column("applications", "is_self_service")

    op.execute("SET app.bypass_rls = 'off'")

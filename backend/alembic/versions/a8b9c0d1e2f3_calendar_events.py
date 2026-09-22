"""Calendar events + attendees + reminders

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-22 21:00:00.000000

New tables only — no existing table is touched. `calendar_events` follows
the same tenant-scoped + RLS pattern as every other table; `calendar_event_
attendees` is a plain join table with tenancy derived through the event
(indirect RLS, same pattern as `role_permissions`/`user_roles`).
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import enable_indirect_tenant_rls, enable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSIONS = (
    ("calendar.manage", "Create, edit and delete calendar events."),
    ("calendar.read", "View calendar events."),
)
_ROLE_PERMISSIONS = {
    "ORG_ADMIN": ("calendar.manage", "calendar.read"),
    "RECRUITER": ("calendar.manage", "calendar.read"),
    "HIRING_MANAGER": ("calendar.manage", "calendar.read"),
    "INTERVIEWER": ("calendar.read",),
}


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "calendar_events",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "INTERVIEW", "HR_MEETING", "TEAM_MEETING", "ASSESSMENT_DEADLINE", "FOLLOW_UP",
                "RECRUITMENT_EVENT", "CAMPUS_EVENT", "GENERAL_REMINDER",
                name="calendar_event_type",
            ),
            server_default="GENERAL_REMINDER",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("SCHEDULED", "COMPLETED", "CANCELLED", name="calendar_event_status"),
            server_default="SCHEDULED",
            nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("organizer_user_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=True),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("reminder_minutes_before", sa.Integer(), nullable=True),
        sa.Column("reminder_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_calendar_events_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organizer_user_id"], ["users.id"],
            name=op.f("fk_calendar_events_organizer_user_id_users"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"],
            name=op.f("fk_calendar_events_candidate_id_candidates"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_calendar_events_job_id_jobs"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"],
            name=op.f("fk_calendar_events_application_id_applications"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_events")),
    )
    op.create_index(op.f("ix_calendar_events_organization_id"), "calendar_events", ["organization_id"], unique=False)
    op.create_index(op.f("ix_calendar_events_start_at"), "calendar_events", ["start_at"], unique=False)
    op.create_index(op.f("ix_calendar_events_candidate_id"), "calendar_events", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_calendar_events_job_id"), "calendar_events", ["job_id"], unique=False)
    op.create_index(op.f("ix_calendar_events_application_id"), "calendar_events", ["application_id"], unique=False)
    # The reminder poll's own query: due, unfired reminders across all orgs.
    op.create_index(
        "ix_calendar_events_due_reminders",
        "calendar_events",
        ["start_at"],
        postgresql_where=sa.text("reminder_minutes_before IS NOT NULL AND reminder_fired_at IS NULL"),
    )

    op.create_table(
        "calendar_event_attendees",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["calendar_events.id"],
            name=op.f("fk_calendar_event_attendees_event_id_calendar_events"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_calendar_event_attendees_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "user_id", name=op.f("pk_calendar_event_attendees")),
    )

    enable_tenant_rls(op, "calendar_events")
    enable_indirect_tenant_rls(
        op, "calendar_event_attendees",
        exists_subquery=(
            "EXISTS (SELECT 1 FROM calendar_events ce WHERE ce.id = calendar_event_attendees.event_id "
            "AND ce.organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)"
        ),
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

    op.drop_table("calendar_event_attendees")
    op.drop_table("calendar_events")
    sa.Enum(name="calendar_event_status").drop(connection, checkfirst=True)
    sa.Enum(name="calendar_event_type").drop(connection, checkfirst=True)

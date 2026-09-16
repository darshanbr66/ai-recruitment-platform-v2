"""recruitment core: jobs, candidates, applications

Revision ID: 0fd94f8966f1
Revises: 679c8590af57
Create Date: 2026-09-15 10:56:13.181583

Phase 3 (docs/architecture.md § 13): Job, Candidate, Application +
ApplicationStatusHistory, with the same two-layer tenant isolation as
Phase 2 (application-layer `organization_id` scoping + Postgres RLS).

Deliberately not included yet (see docs/database.md § 3 and the model
docstrings): `job_requirements` (no consumer until AI screening),
`resumes`/`resume_id` on applications (Resume domain not built), and
`campus_drive_id` on applications (Campus Hiring domain not built). Added
when those domains are actually built, not speculatively now.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import disable_tenant_rls, enable_indirect_tenant_rls, enable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = '0fd94f8966f1'
down_revision: Union[str, None] = '679c8590af57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_APPLICATION_STATUS_VALUES = (
    "APPLIED",
    "UNDER_REVIEW",
    "SCREENING",
    "ASSESSMENT_INVITED",
    "ASSESSMENT_STARTED",
    "ASSESSMENT_COMPLETED",
    "SHORTLISTED",
    "INTERVIEW",
    "SELECTED",
    "REJECTED",
    "WITHDRAWN",
)

# New permission codes this phase's recruiter endpoints actually check, and
# which system roles are granted each (docs/architecture.md § 4). ORG_ADMIN
# and RECRUITER get full operational CRUD; HIRING_MANAGER can review and
# move the pipeline forward but not create jobs/candidates; INTERVIEWER can
# only view what they're interviewing for.
_PERMISSIONS = (
    ("job.create", "Create a job requisition."),
    ("job.read", "View jobs within one's own organization."),
    ("job.update", "Edit a job requisition."),
    ("candidate.create", "Add a candidate."),
    ("candidate.read", "View candidates within one's own organization."),
    ("candidate.update", "Edit a candidate's profile."),
    ("application.create", "Create an application linking a candidate to a job."),
    ("application.read", "View applications within one's own organization."),
    ("application.status.change", "Move an application through the hiring workflow."),
)
_ROLE_PERMISSIONS = {
    "ORG_ADMIN": (
        "job.create", "job.read", "job.update",
        "candidate.create", "candidate.read", "candidate.update",
        "application.create", "application.read", "application.status.change",
    ),
    "RECRUITER": (
        "job.create", "job.read", "job.update",
        "candidate.create", "candidate.read", "candidate.update",
        "application.create", "application.read", "application.status.change",
    ),
    "HIRING_MANAGER": ("job.read", "candidate.read", "application.read", "application.status.change"),
    "INTERVIEWER": ("application.read",),
}


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "candidates",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("current_title", sa.String(length=255), nullable=True),
        sa.Column("years_experience", sa.Integer(), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "PORTAL", "RECRUITER_ADDED", "CAMPUS_IMPORT", "REFERRAL", "OTHER",
                name="candidate_source",
            ),
            server_default="RECRUITER_ADDED",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_candidates_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
    )
    op.create_index(op.f("ix_candidates_organization_id"), "candidates", ["organization_id"], unique=False)
    op.create_index(
        "uq_candidates_org_email", "candidates", ["organization_id", "email"], unique=True,
    )

    op.create_table(
        "jobs",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("employment_type", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "OPEN", "ON_HOLD", "CLOSED", "WITHDRAWN", name="job_status"),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column("openings_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_jobs_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_jobs_created_by_users"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index(op.f("ix_jobs_organization_id"), "jobs", ["organization_id"], unique=False)

    application_status_enum = postgresql.ENUM(*_APPLICATION_STATUS_VALUES, name="application_status")
    application_status_enum.create(bind, checkfirst=True)
    application_status_column = postgresql.ENUM(
        *_APPLICATION_STATUS_VALUES, name="application_status", create_type=False
    )

    op.create_table(
        "applications",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("status", application_status_column, server_default="APPLIED", nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "PORTAL", "RECRUITER_ADDED", "CAMPUS_IMPORT", "REFERRAL", "OTHER",
                name="application_source",
            ),
            server_default="RECRUITER_ADDED",
            nullable=False,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_applications_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"],
            name=op.f("fk_applications_candidate_id_candidates"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_applications_job_id_jobs"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
    )
    op.create_index(op.f("ix_applications_organization_id"), "applications", ["organization_id"], unique=False)
    op.create_index(op.f("ix_applications_candidate_id"), "applications", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_applications_job_id"), "applications", ["job_id"], unique=False)
    op.create_index(
        "uq_applications_candidate_job", "applications", ["candidate_id", "job_id"], unique=True,
    )

    op.create_table(
        "application_status_history",
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("from_status", application_status_column, nullable=True),
        sa.Column("to_status", application_status_column, nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"],
            name=op.f("fk_application_status_history_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"], ["users.id"],
            name=op.f("fk_application_status_history_changed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_status_history")),
    )
    op.create_index(
        op.f("ix_application_status_history_application_id"),
        "application_status_history", ["application_id"], unique=False,
    )

    # --- Row-Level Security ---
    enable_tenant_rls(op, "candidates")
    enable_tenant_rls(op, "jobs")
    enable_tenant_rls(op, "applications")
    # No organization_id of its own — tenancy derived through
    # application_id -> applications.organization_id, same pattern as
    # user_roles (see app/db/rls.py).
    enable_indirect_tenant_rls(
        op,
        "application_status_history",
        exists_subquery=(
            "EXISTS (SELECT 1 FROM applications a WHERE a.id = application_status_history.application_id "
            "AND a.organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)"
        ),
    )

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

    disable_tenant_rls(op, "application_status_history")
    disable_tenant_rls(op, "applications")
    disable_tenant_rls(op, "jobs")
    disable_tenant_rls(op, "candidates")

    op.drop_table("application_status_history")
    op.drop_index(op.f("ix_applications_job_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_candidate_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_organization_id"), table_name="applications")
    op.drop_table("applications")
    sa.Enum(name="application_status").drop(connection, checkfirst=True)

    op.drop_index(op.f("ix_jobs_organization_id"), table_name="jobs")
    op.drop_table("jobs")
    sa.Enum(name="job_status").drop(connection, checkfirst=True)

    op.drop_index(op.f("ix_candidates_organization_id"), table_name="candidates")
    op.drop_table("candidates")
    sa.Enum(name="candidate_source").drop(connection, checkfirst=True)
    sa.Enum(name="application_source").drop(connection, checkfirst=True)

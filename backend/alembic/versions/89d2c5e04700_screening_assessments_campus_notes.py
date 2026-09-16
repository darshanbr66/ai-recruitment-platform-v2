"""AI screening, assessments, campus drives, notes

Revision ID: 89d2c5e04700
Revises: a5afbdf6f1b5
Create Date: 2026-09-17 09:00:00.000000

Adds four domains in one migration since they're all additive and none
depends on data from the others except through existing tables
(applications, jobs, users):

- screening_runs (docs/ai-screening.md, simplified per that model's own
  docstring — no pgvector/embedding tables, which the doc itself defers)
- assessments / questions / question_options / assessment_invitations /
  candidate_answers / assessment_results (docs/assessment.md, MCQ-only)
- campus_drives + applications.campus_drive_id (docs/campus-hiring.md)
- notes (recruiter commentary on an application)
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import disable_tenant_rls, enable_indirect_tenant_rls, enable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = '89d2c5e04700'
down_revision: Union[str, None] = 'a5afbdf6f1b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSIONS = (
    ("screening.create", "Run AI screening on an application."),
    ("screening.read", "View AI screening results."),
    ("assessment.manage", "Create/edit assessments and send invitations."),
    ("assessment.read", "View assessments and results."),
    ("campus_drive.manage", "Create/edit campus drives."),
    ("campus_drive.read", "View campus drives."),
    ("note.manage", "Add notes on an application."),
    ("note.read", "View notes on an application."),
)
_ROLE_PERMISSIONS = {
    "ORG_ADMIN": (
        "screening.create", "screening.read",
        "assessment.manage", "assessment.read",
        "campus_drive.manage", "campus_drive.read",
        "note.manage", "note.read",
    ),
    "RECRUITER": (
        "screening.create", "screening.read",
        "assessment.manage", "assessment.read",
        "campus_drive.manage", "campus_drive.read",
        "note.manage", "note.read",
    ),
    "HIRING_MANAGER": (
        "screening.read", "assessment.read", "campus_drive.read",
        "note.manage", "note.read",
    ),
    "INTERVIEWER": ("screening.read", "note.read"),
}


def upgrade() -> None:
    bind = op.get_bind()

    # --- screening_runs ---
    op.create_table(
        "screening_runs",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "COMPLETED", "FAILED", name="screening_status"),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("recommendation", sa.String(length=50), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("matching_skills", postgresql.JSONB(), nullable=True),
        sa.Column("missing_skills", postgresql.JSONB(), nullable=True),
        sa.Column("strengths", postgresql.JSONB(), nullable=True),
        sa.Column("concerns", postgresql.JSONB(), nullable=True),
        sa.Column("experience_assessment", sa.Text(), nullable=True),
        sa.Column("education_assessment", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_screening_runs_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"],
            name=op.f("fk_screening_runs_application_id_applications"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"],
            name=op.f("fk_screening_runs_requested_by_user_id_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening_runs")),
    )
    op.create_index(op.f("ix_screening_runs_organization_id"), "screening_runs", ["organization_id"], unique=False)
    op.create_index(op.f("ix_screening_runs_application_id"), "screening_runs", ["application_id"], unique=False)

    # --- campus_drives ---
    op.create_table(
        "campus_drives",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("college_name", sa.String(length=255), nullable=False),
        sa.Column("batch_year", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PLANNED", "ACTIVE", "CLOSED", "CANCELLED", name="campus_drive_status"),
            server_default="PLANNED",
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_campus_drives_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_campus_drives_job_id_jobs"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_campus_drives_created_by_users"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campus_drives")),
    )
    op.create_index(op.f("ix_campus_drives_organization_id"), "campus_drives", ["organization_id"], unique=False)
    op.create_index(op.f("ix_campus_drives_job_id"), "campus_drives", ["job_id"], unique=False)

    # --- applications.campus_drive_id ---
    op.add_column("applications", sa.Column("campus_drive_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_applications_campus_drive_id"), "applications", ["campus_drive_id"], unique=False,
    )
    op.create_foreign_key(
        op.f("fk_applications_campus_drive_id_campus_drives"),
        "applications", "campus_drives", ["campus_drive_id"], ["id"], ondelete="SET NULL",
    )

    # --- assessments ---
    op.create_table(
        "assessments",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), server_default="30", nullable=False),
        sa.Column("pass_score", sa.Integer(), server_default="60", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_assessments_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_assessments_created_by_users"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessments")),
    )
    op.create_index(op.f("ix_assessments_organization_id"), "assessments", ["organization_id"], unique=False)

    # --- questions ---
    op.create_table(
        "questions",
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("type", sa.Enum("MCQ_SINGLE", "MCQ_MULTI", name="question_type"), nullable=False),
        sa.Column("points", sa.Integer(), server_default="1", nullable=False),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"],
            name=op.f("fk_questions_assessment_id_assessments"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
    )
    op.create_index(op.f("ix_questions_assessment_id"), "questions", ["assessment_id"], unique=False)

    # --- question_options ---
    op.create_table(
        "question_options",
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"],
            name=op.f("fk_question_options_question_id_questions"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_options")),
    )
    op.create_index(op.f("ix_question_options_question_id"), "question_options", ["question_id"], unique=False)

    # --- assessment_invitations ---
    op.create_table(
        "assessment_invitations",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("invited_by_user_id", sa.UUID(), nullable=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "SENT", "STARTED", "SUBMITTED", "EXPIRED", "CANCELLED",
                name="assessment_invitation_status",
            ),
            server_default="SENT",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_assessment_invitations_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"], ["assessments.id"],
            name=op.f("fk_assessment_invitations_assessment_id_assessments"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"],
            name=op.f("fk_assessment_invitations_application_id_applications"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["users.id"],
            name=op.f("fk_assessment_invitations_invited_by_user_id_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_invitations")),
        sa.UniqueConstraint("application_id", name=op.f("uq_assessment_invitations_application_id")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_assessment_invitations_token_hash")),
    )
    op.create_index(
        op.f("ix_assessment_invitations_organization_id"), "assessment_invitations", ["organization_id"], unique=False,
    )
    op.create_index(
        op.f("ix_assessment_invitations_assessment_id"), "assessment_invitations", ["assessment_id"], unique=False,
    )

    # --- candidate_answers ---
    op.create_table(
        "candidate_answers",
        sa.Column("invitation_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("selected_option_ids", postgresql.JSONB(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["invitation_id"], ["assessment_invitations.id"],
            name=op.f("fk_candidate_answers_invitation_id_assessment_invitations"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"],
            name=op.f("fk_candidate_answers_question_id_questions"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_answers")),
    )
    op.create_index(
        op.f("ix_candidate_answers_invitation_id"), "candidate_answers", ["invitation_id"], unique=False,
    )
    op.create_index(
        op.f("ix_candidate_answers_question_id"), "candidate_answers", ["question_id"], unique=False,
    )

    # --- assessment_results ---
    op.create_table(
        "assessment_results",
        sa.Column("invitation_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("percentage", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["invitation_id"], ["assessment_invitations.id"],
            name=op.f("fk_assessment_results_invitation_id_assessment_invitations"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_results")),
        sa.UniqueConstraint("invitation_id", name=op.f("uq_assessment_results_invitation_id")),
    )

    # --- notes ---
    op.create_table(
        "notes",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_notes_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"],
            name=op.f("fk_notes_application_id_applications"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name=op.f("fk_notes_author_id_users"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notes")),
    )
    op.create_index(op.f("ix_notes_organization_id"), "notes", ["organization_id"], unique=False)
    op.create_index(op.f("ix_notes_application_id"), "notes", ["application_id"], unique=False)

    # --- Row-Level Security ---
    enable_tenant_rls(op, "screening_runs")
    enable_tenant_rls(op, "campus_drives")
    enable_tenant_rls(op, "assessments")
    enable_tenant_rls(op, "assessment_invitations")
    enable_tenant_rls(op, "notes")
    enable_indirect_tenant_rls(
        op, "questions",
        exists_subquery=(
            "EXISTS (SELECT 1 FROM assessments a WHERE a.id = questions.assessment_id "
            "AND a.organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)"
        ),
    )
    enable_indirect_tenant_rls(
        op, "question_options",
        exists_subquery=(
            "EXISTS (SELECT 1 FROM questions q JOIN assessments a ON a.id = q.assessment_id "
            "WHERE q.id = question_options.question_id "
            "AND a.organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)"
        ),
    )
    enable_indirect_tenant_rls(
        op, "candidate_answers",
        exists_subquery=(
            "EXISTS (SELECT 1 FROM assessment_invitations ai WHERE ai.id = candidate_answers.invitation_id "
            "AND ai.organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)"
        ),
    )
    enable_indirect_tenant_rls(
        op, "assessment_results",
        exists_subquery=(
            "EXISTS (SELECT 1 FROM assessment_invitations ai WHERE ai.id = assessment_results.invitation_id "
            "AND ai.organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)"
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

    disable_tenant_rls(op, "assessment_results")
    disable_tenant_rls(op, "candidate_answers")
    disable_tenant_rls(op, "question_options")
    disable_tenant_rls(op, "questions")
    disable_tenant_rls(op, "notes")
    disable_tenant_rls(op, "assessment_invitations")
    disable_tenant_rls(op, "assessments")
    disable_tenant_rls(op, "campus_drives")
    disable_tenant_rls(op, "screening_runs")

    op.drop_table("notes")

    op.drop_table("assessment_results")
    op.drop_table("candidate_answers")
    op.drop_table("assessment_invitations")
    sa.Enum(name="assessment_invitation_status").drop(connection, checkfirst=True)
    op.drop_table("question_options")
    op.drop_table("questions")
    sa.Enum(name="question_type").drop(connection, checkfirst=True)
    op.drop_table("assessments")

    op.drop_constraint(
        op.f("fk_applications_campus_drive_id_campus_drives"), "applications", type_="foreignkey"
    )
    op.drop_index(op.f("ix_applications_campus_drive_id"), table_name="applications")
    op.drop_column("applications", "campus_drive_id")

    op.drop_table("campus_drives")
    sa.Enum(name="campus_drive_status").drop(connection, checkfirst=True)

    op.drop_table("screening_runs")
    sa.Enum(name="screening_status").drop(connection, checkfirst=True)

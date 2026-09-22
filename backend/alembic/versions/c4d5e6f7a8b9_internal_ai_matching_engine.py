"""Internal AI matching engine + RAG retrieval foundation

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-22 12:00:00.000000

Adds the tables docs/ai-screening.md § 6 deferred ("which embedding
provider/model... deferred to Phase 5, when it's chosen" — now chosen:
Gemini, gemini-embedding-001, 768 dims) plus the structured matching engine
the product brief's "AI matching/scoring engine" section requires:

- resume_chunks (pgvector-embedded slices of resume text; requires the
  `vector` Postgres extension, enabled here defensively)
- job_requirements (deterministically extracted, normalized job requirements)
- candidate_resume_profiles (deterministically extracted candidate signal)
- match_results (persisted, explainable, append-only candidate<->job scores)
- the `internal_ai.use` permission, granted to ORG_ADMIN/RECRUITER/
  HIRING_MANAGER

None of this touches ScreeningRun, Sigvi, or any existing table.
"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import disable_tenant_rls, enable_tenant_rls
from app.models.resume_chunk import EMBEDDING_DIMENSIONS

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSIONS = (
    ("internal_ai.use", "Ask the internal AI (Recruitment Intelligence) about candidates, applications and jobs."),
)
_ROLE_PERMISSIONS = {
    "ORG_ADMIN": ("internal_ai.use",),
    "RECRUITER": ("internal_ai.use",),
    "HIRING_MANAGER": ("internal_ai.use",),
}


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- resume_chunks ---
    op.create_table(
        "resume_chunks",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("resume_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_resume_chunks_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"], ["resumes.id"],
            name=op.f("fk_resume_chunks_resume_id_resumes"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"],
            name=op.f("fk_resume_chunks_candidate_id_candidates"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resume_chunks")),
    )
    op.create_index(op.f("ix_resume_chunks_organization_id"), "resume_chunks", ["organization_id"], unique=False)
    op.create_index(op.f("ix_resume_chunks_resume_id"), "resume_chunks", ["resume_id"], unique=False)
    op.create_index(op.f("ix_resume_chunks_candidate_id"), "resume_chunks", ["candidate_id"], unique=False)

    # --- job_requirements ---
    op.create_table(
        "job_requirements",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "SKILL", "EXPERIENCE", "EDUCATION", "LOCATION", "NOTICE_PERIOD", "OTHER",
                name="job_requirement_category",
            ),
            nullable=False,
        ),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("weight", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("raw_source_text", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_job_requirements_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"],
            name=op.f("fk_job_requirements_job_id_jobs"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_requirements")),
    )
    op.create_index(op.f("ix_job_requirements_organization_id"), "job_requirements", ["organization_id"], unique=False)
    op.create_index(op.f("ix_job_requirements_job_id"), "job_requirements", ["job_id"], unique=False)

    # --- candidate_resume_profiles ---
    op.create_table(
        "candidate_resume_profiles",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("source_resume_id", sa.UUID(), nullable=True),
        sa.Column("skills", postgresql.JSONB(), nullable=False),
        sa.Column("total_experience_years", sa.Integer(), nullable=True),
        sa.Column("education", postgresql.JSONB(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("notice_period_days", sa.Integer(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_candidate_resume_profiles_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"],
            name=op.f("fk_candidate_resume_profiles_candidate_id_candidates"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_resume_id"], ["resumes.id"],
            name=op.f("fk_candidate_resume_profiles_source_resume_id_resumes"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidate_resume_profiles")),
        sa.UniqueConstraint("candidate_id", name=op.f("uq_candidate_resume_profiles_candidate_id")),
    )
    op.create_index(
        op.f("ix_candidate_resume_profiles_organization_id"), "candidate_resume_profiles", ["organization_id"], unique=False,
    )

    # --- match_results ---
    op.create_table(
        "match_results",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "COMPLETED", "FAILED", name="match_status"),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("overall_match_score", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.String(length=20), nullable=True),
        sa.Column("matching_skills", postgresql.JSONB(), nullable=True),
        sa.Column("missing_skills", postgresql.JSONB(), nullable=True),
        sa.Column("matching_experience", postgresql.JSONB(), nullable=True),
        sa.Column("matching_education", postgresql.JSONB(), nullable=True),
        sa.Column("matching_location", postgresql.JSONB(), nullable=True),
        sa.Column("notice_period_fit", postgresql.JSONB(), nullable=True),
        sa.Column("role_alignment", sa.Text(), nullable=True),
        sa.Column("potential_concerns", postgresql.JSONB(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("scoring_breakdown", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_match_results_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"],
            name=op.f("fk_match_results_candidate_id_candidates"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"],
            name=op.f("fk_match_results_job_id_jobs"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"],
            name=op.f("fk_match_results_application_id_applications"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"],
            name=op.f("fk_match_results_requested_by_user_id_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match_results")),
    )
    op.create_index(op.f("ix_match_results_organization_id"), "match_results", ["organization_id"], unique=False)
    op.create_index(op.f("ix_match_results_candidate_id"), "match_results", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_match_results_job_id"), "match_results", ["job_id"], unique=False)

    # --- Row-Level Security ---
    enable_tenant_rls(op, "resume_chunks")
    enable_tenant_rls(op, "job_requirements")
    enable_tenant_rls(op, "candidate_resume_profiles")
    enable_tenant_rls(op, "match_results")

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

    disable_tenant_rls(op, "match_results")
    disable_tenant_rls(op, "candidate_resume_profiles")
    disable_tenant_rls(op, "job_requirements")
    disable_tenant_rls(op, "resume_chunks")

    op.drop_table("match_results")
    sa.Enum(name="match_status").drop(connection, checkfirst=True)

    op.drop_table("candidate_resume_profiles")

    op.drop_table("job_requirements")
    sa.Enum(name="job_requirement_category").drop(connection, checkfirst=True)

    op.drop_table("resume_chunks")

    # The `vector` extension is left installed on downgrade — other objects
    # (or a concurrent deployment) may depend on it, and dropping an
    # extension is a destructive, cluster-wide action out of proportion to
    # reverting this one migration.

"""resume storage

Revision ID: a5afbdf6f1b5
Revises: 0fd94f8966f1
Create Date: 2026-09-16 12:00:00.000000

Adds the Resume domain (CLAUDE.md § 2: "Resume storage != DB blob") — file
bytes live on local disk (app/integrations/storage), this table is metadata
only. One resume per application (unique on `application_id`), consistent
with the public apply flow that creates both together.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.db.rls import disable_tenant_rls, enable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = 'a5afbdf6f1b5'
down_revision: Union[str, None] = '0fd94f8966f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resumes",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"],
            name=op.f("fk_resumes_organization_id_organizations"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"],
            name=op.f("fk_resumes_candidate_id_candidates"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"],
            name=op.f("fk_resumes_application_id_applications"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resumes")),
    )
    op.create_index(op.f("ix_resumes_organization_id"), "resumes", ["organization_id"], unique=False)
    op.create_index(op.f("ix_resumes_candidate_id"), "resumes", ["candidate_id"], unique=False)
    op.create_index(
        op.f("ix_resumes_application_id"), "resumes", ["application_id"], unique=True,
    )

    enable_tenant_rls(op, "resumes")


def downgrade() -> None:
    disable_tenant_rls(op, "resumes")
    op.drop_index(op.f("ix_resumes_application_id"), table_name="resumes")
    op.drop_index(op.f("ix_resumes_candidate_id"), table_name="resumes")
    op.drop_index(op.f("ix_resumes_organization_id"), table_name="resumes")
    op.drop_table("resumes")

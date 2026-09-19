"""candidate profile fields for the public application form

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-19 15:10:00.000000

Additive, all nullable — existing candidates keep working unchanged.
Reuses the existing `location` (current location), `current_title` and
`years_experience` columns; adds the rest of what the public application
form now collects.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

candidate_type = postgresql.ENUM("FRESHER", "EXPERIENCED", name="candidate_type", create_type=False)


def upgrade() -> None:
    candidate_type.create(op.get_bind(), checkfirst=True)

    op.add_column("candidates", sa.Column("candidate_type", candidate_type, nullable=True))
    op.add_column("candidates", sa.Column("current_company", sa.String(length=255), nullable=True))
    op.add_column("candidates", sa.Column("preferred_location", sa.String(length=255), nullable=True))
    op.add_column("candidates", sa.Column("notice_period_days", sa.Integer(), nullable=True))
    op.add_column("candidates", sa.Column("immediate_joiner", sa.Boolean(), nullable=True))
    op.add_column("candidates", sa.Column("qualification", sa.String(length=255), nullable=True))
    op.add_column("candidates", sa.Column("linkedin_url", sa.String(length=500), nullable=True))
    op.add_column("candidates", sa.Column("github_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "github_url")
    op.drop_column("candidates", "linkedin_url")
    op.drop_column("candidates", "qualification")
    op.drop_column("candidates", "immediate_joiner")
    op.drop_column("candidates", "notice_period_days")
    op.drop_column("candidates", "preferred_location")
    op.drop_column("candidates", "current_company")
    op.drop_column("candidates", "candidate_type")
    candidate_type.drop(op.get_bind(), checkfirst=True)

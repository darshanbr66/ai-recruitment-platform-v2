"""Candidate resume word count (evidence-density scoring fix)

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-22 18:00:00.000000

Adds `candidate_resume_profiles.resume_word_count` — the evidence-density
signal the matching engine now uses so a near-empty resume that happens to
list exactly the required skills doesn't score the same as a fully
documented one (app/services/matching/deterministic_scorer.py's
`_evidence_density_factor`). Nullable: existing rows are recomputed by
`candidate_profile_extraction.sync_candidate_profile` the next time a match
runs against them (it always sets this field going forward), so no backfill
is required.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidate_resume_profiles",
        sa.Column("resume_word_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_resume_profiles", "resume_word_count")

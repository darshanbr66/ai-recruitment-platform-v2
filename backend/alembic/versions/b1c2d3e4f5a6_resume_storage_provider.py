"""resume storage provider

Revision ID: b1c2d3e4f5a6
Revises: f4a5b6c7d8e9
Create Date: 2026-09-19 12:00:00.000000

Adds `resumes.storage_provider` so a Resume row records which
`ResumeStorage` implementation its (opaque) `storage_path` resolves
against — needed now that MongoDB GridFS exists alongside local-disk
storage (app/integrations/storage). Every existing row was written by
`LocalResumeStorage`, so the backfill is unconditionally "local"; new
uploads set it from whichever provider `RESUME_STORAGE_PROVIDER` selects
at write time.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column(
            "storage_provider",
            sa.String(length=50),
            nullable=False,
            server_default="local",
        ),
    )


def downgrade() -> None:
    op.drop_column("resumes", "storage_provider")

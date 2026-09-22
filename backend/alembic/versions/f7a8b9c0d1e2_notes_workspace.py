"""Notes workspace — title, category, color, visibility, candidate/job links

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-22 20:00:00.000000

Extends the existing `notes` table (never a parallel Notes module, per the
product direction) so it works both as today's application-scoped shared
commentary and as a standalone personal note in the new `/recruiter/notes`
workspace:

- `application_id` becomes nullable (a personal note need not reference one)
- `candidate_id` / `job_id`: optional alternative/additional links
- `title` / `category` / `color`: the workspace's card fields
- `visibility` (PRIVATE/SHARED): governs reads only, never writes (only the
  author may ever edit/delete). Existing rows are backfilled to SHARED,
  which is exactly what every note already behaved as — no existing note
  becomes newly visible or newly hidden to anyone.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.alter_column("notes", "application_id", nullable=True)

    op.add_column("notes", sa.Column("candidate_id", sa.UUID(), nullable=True))
    op.add_column("notes", sa.Column("job_id", sa.UUID(), nullable=True))
    op.add_column("notes", sa.Column("title", sa.String(length=255), nullable=True))
    op.add_column("notes", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column("notes", sa.Column("color", sa.String(length=30), nullable=True))

    # `add_column` (unlike `create_table`) does not implicitly create a new
    # Enum type used for the first time — it must be created explicitly.
    note_visibility = sa.Enum("PRIVATE", "SHARED", name="note_visibility")
    note_visibility.create(bind, checkfirst=True)
    op.add_column(
        "notes",
        sa.Column("visibility", note_visibility, server_default="SHARED", nullable=False),
    )

    op.create_foreign_key(
        op.f("fk_notes_candidate_id_candidates"), "notes", "candidates", ["candidate_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_notes_job_id_jobs"), "notes", "jobs", ["job_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index(op.f("ix_notes_candidate_id"), "notes", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_notes_job_id"), "notes", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notes_job_id"), table_name="notes")
    op.drop_index(op.f("ix_notes_candidate_id"), table_name="notes")
    op.drop_constraint(op.f("fk_notes_job_id_jobs"), "notes", type_="foreignkey")
    op.drop_constraint(op.f("fk_notes_candidate_id_candidates"), "notes", type_="foreignkey")

    op.drop_column("notes", "visibility")
    op.drop_column("notes", "color")
    op.drop_column("notes", "category")
    op.drop_column("notes", "title")
    op.drop_column("notes", "job_id")
    op.drop_column("notes", "candidate_id")

    connection = op.get_bind()
    op.alter_column("notes", "application_id", nullable=False)
    sa.Enum(name="note_visibility").drop(connection, checkfirst=True)

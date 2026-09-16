"""campus drive redesign: DRAFT/ACTIVE/PAUSED/CLOSED lifecycle, public
link token, default assessment, description/registration deadline

Revision ID: de0362764818
Revises: 89d2c5e04700
Create Date: 2026-09-17 10:00:00.000000

Campus drives move from PLANNED/ACTIVE/CLOSED/CANCELLED to
DRAFT/ACTIVE/PAUSED/CLOSED (docs/campus-hiring.md's redesigned UX):
PLANNED -> DRAFT and CANCELLED -> CLOSED are the closest semantic matches,
applied to any pre-existing rows rather than losing data. Adds a
dedicated, hashed public application link (same pattern as
AssessmentInvitation.token_hash) and an optional default assessment to
auto-invite candidates who apply through it.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'de0362764818'
down_revision: Union[str, None] = '89d2c5e04700'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- new columns (nullable first; link_token_hash tightened below) ---
    op.add_column("campus_drives", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "campus_drives", sa.Column("registration_deadline", sa.Date(), nullable=True)
    )
    op.add_column(
        "campus_drives", sa.Column("default_assessment_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_campus_drives_default_assessment_id_assessments"),
        "campus_drives", "assessments", ["default_assessment_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column(
        "campus_drives", sa.Column("link_token_hash", sa.String(length=128), nullable=True)
    )
    # Placeholder unique hash for any pre-existing rows — they predate this
    # feature and never had a real shareable link; a recruiter regenerates
    # a real one via POST .../regenerate-link. `campus_drives` FORCEs RLS
    # even for the table owner (see app/db/rls.py), so this update needs
    # an explicit bypass or it silently matches zero rows.
    op.execute("SET LOCAL app.bypass_rls = 'on'")
    op.execute(
        "UPDATE campus_drives SET link_token_hash = md5(gen_random_uuid()::text || id::text) "
        "WHERE link_token_hash IS NULL"
    )
    op.alter_column("campus_drives", "link_token_hash", nullable=False)
    op.create_unique_constraint(
        op.f("uq_campus_drives_link_token_hash"), "campus_drives", ["link_token_hash"]
    )

    # --- status enum: PLANNED/ACTIVE/CLOSED/CANCELLED -> DRAFT/ACTIVE/PAUSED/CLOSED ---
    op.execute("ALTER TYPE campus_drive_status RENAME TO campus_drive_status_old")
    new_status = sa.Enum("DRAFT", "ACTIVE", "PAUSED", "CLOSED", name="campus_drive_status")
    new_status.create(op.get_bind())
    op.execute(
        "ALTER TABLE campus_drives ALTER COLUMN status DROP DEFAULT"
    )
    op.execute(
        "ALTER TABLE campus_drives ALTER COLUMN status TYPE campus_drive_status USING ("
        "CASE status::text "
        "WHEN 'PLANNED' THEN 'DRAFT' "
        "WHEN 'CANCELLED' THEN 'CLOSED' "
        "ELSE status::text "
        "END)::campus_drive_status"
    )
    op.execute(
        "ALTER TABLE campus_drives ALTER COLUMN status SET DEFAULT 'DRAFT'"
    )
    op.execute("DROP TYPE campus_drive_status_old")


def downgrade() -> None:
    op.execute("ALTER TYPE campus_drive_status RENAME TO campus_drive_status_new")
    old_status = sa.Enum("PLANNED", "ACTIVE", "CLOSED", "CANCELLED", name="campus_drive_status")
    old_status.create(op.get_bind())
    op.execute("ALTER TABLE campus_drives ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE campus_drives ALTER COLUMN status TYPE campus_drive_status USING ("
        "CASE status::text "
        "WHEN 'DRAFT' THEN 'PLANNED' "
        "WHEN 'PAUSED' THEN 'CANCELLED' "
        "ELSE status::text "
        "END)::campus_drive_status"
    )
    op.execute("ALTER TABLE campus_drives ALTER COLUMN status SET DEFAULT 'PLANNED'")
    op.execute("DROP TYPE campus_drive_status_new")

    op.drop_constraint(
        op.f("uq_campus_drives_link_token_hash"), "campus_drives", type_="unique"
    )
    op.drop_column("campus_drives", "link_token_hash")
    op.drop_constraint(
        op.f("fk_campus_drives_default_assessment_id_assessments"), "campus_drives", type_="foreignkey"
    )
    op.drop_column("campus_drives", "default_assessment_id")
    op.drop_column("campus_drives", "registration_deadline")
    op.drop_column("campus_drives", "description")

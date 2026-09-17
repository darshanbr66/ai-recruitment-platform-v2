"""assessment retest attempts

Revision ID: fedb70899161
Revises: ca672b4cecb4
Create Date: 2026-09-17 15:10:00.000000

Allows more than one AssessmentInvitation row per Application: each row is
now one attempt (`attempt_number`), so a retest is an additive new row
rather than a mutation of the original — the failed attempt's row (and its
linked AssessmentResult/CandidateAnswers, both still FK'd to their own
invitation_id) is never touched. See app/models/assessment.py's updated
docstring and app/services/assessment_service.py::create_retest.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fedb70899161'
down_revision: Union[str, None] = 'ca672b4cecb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("uq_assessment_invitations_application_id"),
        "assessment_invitations",
        type_="unique",
    )
    op.create_index(
        op.f("ix_assessment_invitations_application_id"),
        "assessment_invitations",
        ["application_id"],
        unique=False,
    )
    op.add_column(
        "assessment_invitations",
        sa.Column("attempt_number", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "assessment_invitations", sa.Column("retest_reason", sa.Text(), nullable=True)
    )

    # ASSESSMENT_COMPLETED -> ASSESSMENT_INVITED is not a DB-level enum
    # concern (the enum already has both values) — the legal-transition
    # table lives in app/workflows/application_workflow.py, in code, not
    # in the schema. Nothing to migrate there.


def downgrade() -> None:
    op.drop_column("assessment_invitations", "retest_reason")
    op.drop_column("assessment_invitations", "attempt_number")
    op.drop_index(
        op.f("ix_assessment_invitations_application_id"), table_name="assessment_invitations"
    )
    op.create_unique_constraint(
        op.f("uq_assessment_invitations_application_id"),
        "assessment_invitations",
        ["application_id"],
    )

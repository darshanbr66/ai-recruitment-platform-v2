"""manual email workflow: emailed_at and application.email.send

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-19 18:00:00.000000

Candidate email is now strictly manual (composed and sent by a recruiter
from the application page). Two additive changes support that:

* `assessment_invitations.emailed_at` — an invitation is *prepared* when an
  assessment is assigned and only *emailed* when a recruiter sends it. The
  existing `status = SENT` value predates this and no longer implies an
  email went out, so the real delivery time is recorded separately.
* `application.email.send` — its own permission for sending candidate
  email, granted to ORG_ADMIN and RECRUITER only.
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSION_CODE = "application.email.send"
_PERMISSION_DESCRIPTION = "Compose and send emails to candidates from an application."
_GRANTED_TO = ("ORG_ADMIN", "RECRUITER")


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "assessment_invitations",
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
    )

    permission_id = str(uuid.uuid4())
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("id", sa.UUID()),
            sa.column("code", sa.String()),
            sa.column("description", sa.Text()),
        ),
        [{"id": permission_id, "code": _PERMISSION_CODE, "description": _PERMISSION_DESCRIPTION}],
    )

    role_ids = [
        row[0]
        for role_name in _GRANTED_TO
        for row in bind.execute(
            sa.text("SELECT id FROM roles WHERE organization_id IS NULL AND name = :name"),
            {"name": role_name},
        )
    ]
    op.bulk_insert(
        sa.table(
            "role_permissions",
            sa.column("role_id", sa.UUID()),
            sa.column("permission_id", sa.UUID()),
        ),
        [{"role_id": role_id, "permission_id": permission_id} for role_id in role_ids],
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = :code)"
        ),
        {"code": _PERMISSION_CODE},
    )
    bind.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": _PERMISSION_CODE})
    op.drop_column("assessment_invitations", "emailed_at")

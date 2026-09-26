"""Candidate intake (first HR meeting): email verification, identity fields,
mobile uniqueness, AI screening gate, HR job matching, careers contact

Revision ID: b4c5d6e7f8a9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-24 10:00:00.000000

Extends existing tables wherever they already model the concept (never a
parallel system):

- `application_status` += `AI_SCREENED_OUT` (placed right after APPLIED so
  status ordering stays pipeline order); `application_source` += `HR_MATCH`.
- `organizations.careers_contact_email` — the recruitment team's public
  contact address, configured per organization (never hardcoded).
- `candidates`: `date_of_birth`, `place_of_birth`, `languages` (text[] +
  GIN index), `email_verified_at`; existing phone numbers normalized to
  E.164 where they parse, then a unique (organization_id, phone) index; a
  CHECK that an email-verified (self-service) candidate always has phone,
  DOB, place of birth and at least one language.
- `screening_runs`: `decision` (MATCH / NOT_MATCH), `matched_requirements`,
  `missing_requirements`.
- New tenant-scoped `email_verifications` table (RLS enabled with the
  standard policy).

`ALTER TYPE ... ADD VALUE` is safe inside the migration transaction because
the new values are not used in the same transaction (see e6f7a8b9c0d1).
"""
import os
from typing import Sequence, Union

import phonenumbers
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.rls import disable_tenant_rls, enable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _canonical_phone(raw: str, region: str) -> str | None:
    """Frozen copy of app/core/phone.py::canonical_phone_or_none as of this
    revision — a migration must not change meaning if that module evolves."""
    value = raw.strip()
    if not value:
        return None
    candidate = "+" + value[2:] if value.startswith("00") else value
    try:
        parsed = phonenumbers.parse(candidate, region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    international = value.startswith(("+", "00"))
    digits = "".join(ch for ch in (value[2:] if value.startswith("00") else value) if ch.isdigit())
    if not digits:
        return None
    return f"+{digits}" if international else digits


def _normalize_existing_phones() -> None:
    """Rewrites existing phones to their canonical form, but only after
    checking that canonicalization produces no collision: if two candidates
    in one organization canonicalize to the same number (e.g. "98765 43210"
    and "+919876543210"), nothing is written and the migration stops with an
    explicit message for a human to resolve, rather than guessing which
    record is the real person. No candidate is ever merged or dropped here.
    A phone with no digits at all canonicalizes to NULL (it can't identify
    anyone)."""
    bind = op.get_bind()
    region = os.environ.get("DEFAULT_PHONE_REGION", "IN")
    rows = bind.execute(
        sa.text(
            "SELECT id, organization_id, phone FROM candidates "
            "WHERE phone IS NOT NULL ORDER BY organization_id, created_at, id"
        )
    ).all()
    groups: dict[tuple[str, str], list[str]] = {}
    updates: list[dict[str, object]] = []
    for row in rows:
        canonical = _canonical_phone(row.phone, region)
        if canonical is not None:
            groups.setdefault((str(row.organization_id), canonical), []).append(str(row.id))
        if canonical != row.phone:
            updates.append({"id": row.id, "phone": canonical})

    collisions = [ids for ids in groups.values() if len(ids) > 1]
    if collisions:
        # Candidate ids only — never the phone numbers themselves (PII in logs).
        detail = "; ".join(
            f"organization {org_id}: candidates {', '.join(ids)}"
            for (org_id, _), ids in groups.items()
            if len(ids) > 1
        )
        raise RuntimeError(
            f"{len(collisions)} mobile number(s) are shared by more than one candidate in the "
            "same organization once normalized to E.164 (formatting differences such as "
            "spaces, dashes, a 0 trunk prefix or a +91 country code count as the same "
            "number). Resolve them (edit or clear the phone on the duplicate candidate "
            f"records) and re-run the migration. Affected: {detail}"
        )

    for update in updates:
        bind.execute(sa.text("UPDATE candidates SET phone = :phone WHERE id = :id"), update)


def upgrade() -> None:
    # Every tenant-owned table FORCEs RLS, which applies to this migration's
    # own DML too — bypass it for the data normalization below (same as
    # c1a2f3b4d5e6).
    op.execute("SET app.bypass_rls = 'on'")

    op.execute("ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'AI_SCREENED_OUT' AFTER 'APPLIED'")
    op.execute("ALTER TYPE application_source ADD VALUE IF NOT EXISTS 'HR_MATCH'")

    op.add_column(
        "organizations", sa.Column("careers_contact_email", sa.String(length=320), nullable=True)
    )

    op.add_column("candidates", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("candidates", sa.Column("place_of_birth", sa.String(length=255), nullable=True))
    op.add_column(
        "candidates",
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "candidates", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_candidates_languages", "candidates", ["languages"], postgresql_using="gin"
    )

    _normalize_existing_phones()
    op.create_index(
        "uq_candidates_org_phone",
        "candidates",
        ["organization_id", "phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )
    op.create_check_constraint(
        "ck_candidates_verified_identity_complete",
        "candidates",
        "email_verified_at IS NULL OR (phone IS NOT NULL AND date_of_birth IS NOT NULL "
        "AND place_of_birth IS NOT NULL AND cardinality(languages) > 0)",
    )

    screening_decision = postgresql.ENUM("MATCH", "NOT_MATCH", name="screening_decision")
    screening_decision.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "screening_runs",
        sa.Column(
            "decision",
            postgresql.ENUM(name="screening_decision", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "screening_runs",
        sa.Column("matched_requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "screening_runs",
        sa.Column("missing_requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    purpose = postgresql.ENUM("CANDIDATE_APPLICATION", name="email_verification_purpose")
    purpose.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "email_verifications",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "purpose",
            postgresql.ENUM(name="email_verification_purpose", create_type=False),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=128), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("send_window_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sends_in_window", sa.Integer(), server_default="0", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_verifications_organization_id", "email_verifications", ["organization_id"]
    )
    op.create_index(
        "uq_email_verifications_org_email_purpose",
        "email_verifications",
        ["organization_id", "email", "purpose"],
        unique=True,
    )
    op.create_index(
        "uq_email_verifications_token_hash", "email_verifications", ["token_hash"], unique=True
    )
    enable_tenant_rls(op, "email_verifications")

    op.execute("SET app.bypass_rls = 'off'")


def _refuse_downgrade_if_new_enum_values_in_use() -> None:
    """Postgres cannot drop an enum value, so `AI_SCREENED_OUT` / `HR_MATCH`
    stay valid in the types after a downgrade — but the previous revision's
    code cannot read them, and no pre-existing value means the same thing
    (rewriting a screen-out to APPLIED, or an HR match to RECRUITER_ADDED,
    would falsify the workflow and its audit history). So the downgrade
    refuses to run while any row uses them, leaving a human to decide."""
    bind = op.get_bind()
    in_use = {
        "applications.status = AI_SCREENED_OUT": (
            "SELECT count(*) FROM applications WHERE status = 'AI_SCREENED_OUT'"
        ),
        "applications.source = HR_MATCH": (
            "SELECT count(*) FROM applications WHERE source = 'HR_MATCH'"
        ),
        "application_status_history uses AI_SCREENED_OUT": (
            "SELECT count(*) FROM application_status_history "
            "WHERE from_status = 'AI_SCREENED_OUT' OR to_status = 'AI_SCREENED_OUT'"
        ),
    }
    found = {
        label: count
        for label, query in in_use.items()
        if (count := bind.execute(sa.text(query)).scalar_one())
    }
    if found:
        summary = ", ".join(f"{label}: {count} row(s)" for label, count in found.items())
        raise RuntimeError(
            "Cannot downgrade b4c5d6e7f8a9: data uses values the previous revision does not "
            f"understand ({summary}). They are never rewritten automatically, because that "
            "would falsify application status history. Resolve them deliberately first."
        )


def downgrade() -> None:
    op.execute("SET app.bypass_rls = 'on'")

    _refuse_downgrade_if_new_enum_values_in_use()

    disable_tenant_rls(op, "email_verifications")
    op.drop_index("uq_email_verifications_token_hash", table_name="email_verifications")
    op.drop_index("uq_email_verifications_org_email_purpose", table_name="email_verifications")
    op.drop_index("ix_email_verifications_organization_id", table_name="email_verifications")
    op.drop_table("email_verifications")
    op.execute("DROP TYPE IF EXISTS email_verification_purpose")

    op.drop_column("screening_runs", "missing_requirements")
    op.drop_column("screening_runs", "matched_requirements")
    op.drop_column("screening_runs", "decision")
    op.execute("DROP TYPE IF EXISTS screening_decision")

    op.drop_constraint("ck_candidates_verified_identity_complete", "candidates", type_="check")
    op.drop_index("uq_candidates_org_phone", table_name="candidates")
    op.drop_index("ix_candidates_languages", table_name="candidates")
    op.drop_column("candidates", "email_verified_at")
    op.drop_column("candidates", "languages")
    op.drop_column("candidates", "place_of_birth")
    op.drop_column("candidates", "date_of_birth")

    op.drop_column("organizations", "careers_contact_email")

    # The new enum values stay in their types (Postgres cannot drop one) —
    # unused, since the guard above ran first, and harmless; `ADD VALUE IF
    # NOT EXISTS` makes a re-upgrade a no-op.

    op.execute("SET app.bypass_rls = 'off'")

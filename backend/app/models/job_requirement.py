import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RequirementCategory(StrEnum):
    SKILL = "SKILL"
    EXPERIENCE = "EXPERIENCE"
    EDUCATION = "EDUCATION"
    LOCATION = "LOCATION"
    NOTICE_PERIOD = "NOTICE_PERIOD"
    OTHER = "OTHER"


class JobRequirement(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """One structured, categorized requirement deterministically extracted
    from a Job's free-text `description` (app/services/matching/
    requirement_extraction.py) — the "Normalize requirements" step of the
    matching engine pipeline. Deliberately kept out of `Job` itself (see
    that model's docstring: modeled here, not there, now that a real
    consumer — the matching engine — exists).

    Regenerated wholesale whenever the owning Job's description/fields
    change: extraction deletes every existing row for a `job_id` and
    re-inserts, so stale and fresh requirements can never coexist. Never
    hand-edited by a recruiter in this phase — that's a natural Phase B/UI
    enhancement, not built here.
    """

    __tablename__ = "job_requirements"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[RequirementCategory] = mapped_column(
        Enum(RequirementCategory, name="job_requirement_category", native_enum=True),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Relative importance within its category, for the deterministic scorer's
    # weighted aggregation (app/services/matching/deterministic_scorer.py).
    # A plain float 0-1 rather than an integer "points" scale, so weights
    # within a category can always be normalized to sum to 1 regardless of
    # how many requirements were extracted.
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    # The description fragment this was extracted from — required for the
    # brief's explainability demand ("store the individual scoring factors
    # so the recruiter can understand WHY").
    raw_source_text: Mapped[str] = mapped_column(Text, nullable=False)

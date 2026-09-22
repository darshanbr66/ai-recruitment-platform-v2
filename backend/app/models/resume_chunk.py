import uuid
from typing import Final

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

#: The fixed width of every vector in this table — a schema fact, not a
#: runtime setting (pgvector requires every row in a column to share one
#: width). `Settings.gemini_embedding_dimensions` (app/core/config.py)
#: defaults to this same number for the value requested from the embedding
#: API; the two must be changed together, via a migration that widens this
#: column and re-embeds every existing row — never independently.
EMBEDDING_DIMENSIONS: Final[int] = 768


class ResumeChunk(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """One embedded slice of one Resume's extracted text — the pgvector-
    backed retrieval unit docs/ai-screening.md § 2 named and deferred
    ("embedding provider was never chosen"). Built for the internal AI
    matching/RAG engine (app/services/matching/, app/services/internal_ai/),
    not for `ScreeningRun` (app/models/screening.py), which stays on its
    existing whole-resume-in-one-call approach — this is additive.

    `candidate_id` is denormalized from `resume.candidate_id`, matching the
    same rationale `Resume` itself documents (app/models/resume.py): a
    candidate's chunks can be queried directly without joining through
    Resume every time (the matching engine's hot path).

    Regenerated wholesale, never patched: `resume_chunking_service.py`
    deletes every existing chunk for a `resume_id` before inserting the new
    set, so a re-chunk (e.g. after a resume re-upload) can't leave stale and
    fresh chunks mixed together.
    """

    __tablename__ = "resume_chunks"

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)

"""The matching engine's semantic-retrieval stage: pgvector similarity
between a Job's requirement text and a Candidate's embedded resume chunks —
an auxiliary signal that catches skills/experience phrased differently than
`skill_taxonomy.py`'s keyword matching does (e.g. a resume that says "built
REST services with Node" for a job requiring "Node.js"), used as supporting
`evidence` for the matching engine's explanation, never as the primary score
(deterministic_scorer.py owns that).

Best-effort: returns no evidence (never raises) if the embedding provider is
unconfigured or the candidate has no chunked resume yet — the deterministic
score and a templated explanation remain fully usable without it.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.ai import AIProviderError, get_embedding_provider
from app.models.job_requirement import JobRequirement
from app.models.resume_chunk import ResumeChunk

logger = get_logger(__name__)

_TOP_K_PER_REQUIREMENT = 2
#: Below this cosine similarity, a "match" is noise, not evidence — pgvector
#: cosine_distance is 1 - cosine_similarity, so a smaller distance is a
#: closer match; this bound was chosen conservatively (real, related text
#: for the resumes/roles this platform handles clusters well under it).
_MAX_DISTANCE = 0.55


@dataclass(frozen=True)
class SemanticEvidence:
    requirement_label: str
    resume_chunk_id: uuid.UUID
    excerpt: str
    similarity: float  # 0.0-1.0, higher is more similar


async def find_semantic_evidence(
    db: AsyncSession, *, candidate_id: uuid.UUID, requirements: list[JobRequirement]
) -> list[SemanticEvidence]:
    chunk_exists = await db.scalar(
        select(ResumeChunk.id).where(ResumeChunk.candidate_id == candidate_id).limit(1)
    )
    if chunk_exists is None:
        return []

    # Only categories where phrasing genuinely varies benefit from a
    # semantic search — location/notice-period are exact-value comparisons
    # already handled deterministically.
    queryable = [r for r in requirements if r.category.value in ("SKILL", "EXPERIENCE")]
    if not queryable:
        return []

    try:
        provider = get_embedding_provider()
        vectors = await provider.embed([r.label for r in queryable], task_type="RETRIEVAL_QUERY")
    except AIProviderError as exc:
        logger.info(
            "Semantic matching skipped (embedding provider unavailable)",
            extra={"extra_fields": {"error": type(exc).__name__}},
        )
        return []

    evidence: list[SemanticEvidence] = []
    for requirement, vector in zip(queryable, vectors, strict=True):
        distance_expr = ResumeChunk.embedding.cosine_distance(vector)
        result = await db.execute(
            select(ResumeChunk.id, ResumeChunk.content, distance_expr)
            .where(ResumeChunk.candidate_id == candidate_id)
            .order_by(distance_expr)
            .limit(_TOP_K_PER_REQUIREMENT)
        )
        for chunk_id, content, distance in result.all():
            if distance > _MAX_DISTANCE:
                continue
            excerpt = content if len(content) <= 240 else content[:240].rstrip() + "…"
            evidence.append(
                SemanticEvidence(
                    requirement_label=requirement.label,
                    resume_chunk_id=chunk_id,
                    excerpt=excerpt,
                    similarity=round(1 - distance, 4),
                )
            )
    return evidence

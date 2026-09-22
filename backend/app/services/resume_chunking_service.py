"""Chunk + embed a resume's extracted text into ResumeChunk rows — the RAG
retrieval unit for the internal AI matching engine (app/services/matching/,
app/services/internal_ai/). Runs inline, synchronously, right after a resume
is saved (see resume_service.py) — no background worker is provisioned yet
(docs/architecture.md § 12: Arq is deferred until a real job needs it, and
this deployment has no Redis); this can move to a queued job later without
any schema change.

Best-effort by design: a resume upload must succeed even when the embedding
provider is unconfigured or briefly unavailable — chunking failure here
never fails the surrounding upload. The matching engine treats "no chunks
yet" as "semantic signal unavailable" and falls back to deterministic-only
scoring (app/services/matching/match_engine.py).
"""

import re
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.ai import AIProviderError, get_embedding_provider
from app.integrations.ai.extraction import extract_resume_text
from app.integrations.storage import StorageError, get_resume_storage_for_provider
from app.models.resume import Resume
from app.models.resume_chunk import ResumeChunk

logger = get_logger(__name__)

_CHUNK_CHARS = 1200
_CHUNK_OVERLAP_CHARS = 150
# Guards against a pathological huge document turning one upload into an
# unbounded number of embedding calls.
_MAX_CHUNKS_PER_RESUME = 40


def split_into_chunks(text: str) -> list[str]:
    """Fixed-size character chunking with overlap — a defensible MVP
    strategy (docs/ai-screening.md § 6 named "fixed-size vs. semantic/
    section-aware" as an open, deferred choice; fixed-size wins here for
    being predictable and independent of resume formatting, which varies
    too much to parse into sections reliably). Prefers to split on a
    paragraph or sentence boundary within the window so a chunk doesn't cut
    mid-sentence unless the text simply has no such boundary.
    """
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not cleaned:
        return []
    if len(cleaned) <= _CHUNK_CHARS:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned) and len(chunks) < _MAX_CHUNKS_PER_RESUME:
        end = min(start + _CHUNK_CHARS, len(cleaned))
        if end < len(cleaned):
            boundary = cleaned.rfind("\n\n", start, end)
            if boundary <= start:
                boundary = cleaned.rfind(". ", start, end)
            if boundary > start:
                end = boundary + 1
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - _CHUNK_OVERLAP_CHARS if end < len(cleaned) else end
    return chunks


async def chunk_and_embed_resume(db: AsyncSession, resume: Resume) -> list[ResumeChunk]:
    """Replaces every existing chunk for `resume.id` with a freshly
    extracted + embedded set. Returns an empty list (never raises) if
    extraction or embedding can't complete — callers must not let this fail
    the surrounding resume-upload transaction.
    """
    try:
        storage = get_resume_storage_for_provider(resume.storage_provider)
        resume_bytes = await storage.read(resume.storage_path)
        text = extract_resume_text(content=resume_bytes, filename=resume.original_filename)
        chunks_text = split_into_chunks(text)
        if not chunks_text:
            return []

        provider = get_embedding_provider()
        vectors = await provider.embed(chunks_text, task_type="RETRIEVAL_DOCUMENT")
    except (AIProviderError, StorageError) as exc:
        logger.warning(
            "Resume chunking/embedding skipped",
            extra={"extra_fields": {"resume_id": str(resume.id), "error": type(exc).__name__}},
        )
        return []

    await db.execute(delete(ResumeChunk).where(ResumeChunk.resume_id == resume.id))

    rows = [
        ResumeChunk(
            organization_id=resume.organization_id,
            resume_id=resume.id,
            candidate_id=resume.candidate_id,
            chunk_index=index,
            content=content,
            # A rough, non-billing estimate (~4 chars/token in English) used
            # only for display/diagnostics — never sent to a provider.
            token_count=max(1, len(content) // 4),
            embedding=vector,
        )
        for index, (content, vector) in enumerate(zip(chunks_text, vectors, strict=True))
    ]
    db.add_all(rows)
    await db.flush()
    logger.info(
        "Resume chunked and embedded",
        extra={"extra_fields": {"resume_id": str(resume.id), "chunk_count": len(rows)}},
    )
    return rows


async def backfill_missing_resume_chunks(
    db: AsyncSession, *, organization_id: uuid.UUID, limit: int = 20
) -> int:
    """One-off maintenance helper for resumes uploaded before this feature
    existed — nothing triggers chunking for them retroactively. Not exposed
    via an HTTP endpoint in this phase; intended to be run from a shell for
    an existing organization. The matching engine works without it: semantic
    retrieval simply finds no evidence for an un-chunked resume, and
    deterministic scoring still runs from Candidate/JobRequirement fields
    alone (app/services/matching/deterministic_scorer.py).
    """
    result = await db.execute(
        select(Resume)
        .outerjoin(ResumeChunk, ResumeChunk.resume_id == Resume.id)
        .where(Resume.organization_id == organization_id, ResumeChunk.id.is_(None))
        .limit(limit)
    )
    resumes = list(result.scalars().all())
    processed = 0
    for resume in resumes:
        if await chunk_and_embed_resume(db, resume):
            processed += 1
    return processed

"""Deterministically extract a `CandidateResumeProfile` from a Candidate's
existing structured fields plus their most recent resume's text — the
matching engine's normalized candidate side, mirroring
requirement_extraction.py on the job side. Uses the same skill taxonomy
(skill_taxonomy.py) as the job side, so a skill found on either side is
guaranteed to be the same token.

Deliberately independent of the embedding provider/ResumeChunk rows: resume
text is re-extracted directly from storage here (the same
`extract_resume_text` screening already uses), so deterministic skill/
education/experience extraction works even when Gemini is unconfigured or a
resume hasn't been chunked yet — only the matching engine's *semantic*
signal (semantic_scorer.py) depends on embeddings existing.

Idempotent: `sync_candidate_profile` upserts the one row `candidate_id`
allows (unique constraint), so re-running after a resume update never
leaves a stale duplicate.
"""

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.ai.extraction import extract_resume_text
from app.integrations.storage import StorageError, get_resume_storage_for_provider
from app.models.candidate import Candidate
from app.models.candidate_resume_profile import CandidateResumeProfile
from app.models.resume import Resume
from app.services.matching.skill_taxonomy import EDUCATION_TERMS, find_skills

logger = get_logger(__name__)

_EXPERIENCE_PATTERN = re.compile(
    r"(\d+)\+?\s*years?\s+(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience",
    re.IGNORECASE,
)


def _extract_education(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for term in EDUCATION_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
            canonical = term.rstrip(".").upper()
            if canonical not in seen:
                seen.add(canonical)
                found.append(term)
    return found


def _extract_experience_years(text: str) -> int | None:
    match = _EXPERIENCE_PATTERN.search(text)
    return int(match.group(1)) if match else None


async def _latest_resume(db: AsyncSession, candidate_id: uuid.UUID) -> Resume | None:
    result = await db.execute(
        select(Resume)
        .where(Resume.candidate_id == candidate_id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _resume_text(resume: Resume) -> str:
    try:
        storage = get_resume_storage_for_provider(resume.storage_provider)
        content = await storage.read(resume.storage_path)
        return extract_resume_text(content=content, filename=resume.original_filename)
    except StorageError as exc:
        logger.warning(
            "Could not read resume for profile extraction",
            extra={"extra_fields": {"resume_id": str(resume.id), "error": str(exc)}},
        )
        return ""


async def sync_candidate_profile(db: AsyncSession, candidate: Candidate) -> CandidateResumeProfile:
    resume = await _latest_resume(db, candidate.id)
    resume_text = await _resume_text(resume) if resume is not None else ""
    resume_word_count = len(resume_text.split())

    skills = find_skills(resume_text)
    education = _extract_education(resume_text)
    total_experience_years = candidate.years_experience
    if total_experience_years is None:
        total_experience_years = _extract_experience_years(resume_text)

    notice_period_days = candidate.notice_period_days
    if notice_period_days is None and candidate.immediate_joiner:
        notice_period_days = 0

    location = candidate.location or candidate.preferred_location

    existing = await db.scalar(
        select(CandidateResumeProfile).where(CandidateResumeProfile.candidate_id == candidate.id)
    )
    now = datetime.now(UTC)
    if existing is not None:
        existing.source_resume_id = resume.id if resume is not None else None
        existing.skills = skills
        existing.total_experience_years = total_experience_years
        existing.education = education
        existing.location = location
        existing.notice_period_days = notice_period_days
        existing.resume_word_count = resume_word_count
        existing.extracted_at = now
        await db.flush()
        return existing

    profile = CandidateResumeProfile(
        organization_id=candidate.organization_id,
        candidate_id=candidate.id,
        source_resume_id=resume.id if resume is not None else None,
        skills=skills,
        total_experience_years=total_experience_years,
        education=education,
        location=location,
        notice_period_days=notice_period_days,
        resume_word_count=resume_word_count,
        extracted_at=now,
    )
    db.add(profile)
    await db.flush()
    return profile

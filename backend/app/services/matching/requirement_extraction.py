"""Deterministically extract structured, categorized `JobRequirement` rows
from a Job's free-text `description` + its `location` field — the
"Normalize requirements" step of the matching engine pipeline. No LLM call:
every requirement here is either a taxonomy-matched skill or a plain regex
match against real text on the Job, so results are exactly reproducible and
independent of model drift (the brief's "do not make the score a
meaningless LLM-generated number" requirement starts here).

Idempotent: `sync_job_requirements` deletes every existing row for the job
and re-inserts the freshly extracted set, so requirements never go stale
after a description edit and stale/fresh rows can't coexist.
"""

import re
import uuid
from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_requirement import JobRequirement, RequirementCategory
from app.services.matching.skill_taxonomy import EDUCATION_TERMS, find_skills

# Section markers that flag everything after them as "nice to have" rather
# than mandatory — a common convention in job descriptions.
_OPTIONAL_SECTION_MARKERS = re.compile(
    r"(nice[- ]to[- ]have|good[- ]to[- ]have|preferred|bonus|plus\s+points?)",
    re.IGNORECASE,
)
_EXPERIENCE_PATTERN = re.compile(
    r"(\d+)\s*(?:\+|to\s*\d+)?\s*years?\s+(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience",
    re.IGNORECASE,
)
_NOTICE_PERIOD_PATTERN = re.compile(
    r"notice\s+period\s+of\s+(\d+)\s*days?|(\d+)\s*days?\s+notice\s+period",
    re.IGNORECASE,
)


class ExtractedRequirement(NamedTuple):
    category: RequirementCategory
    label: str
    is_required: bool
    weight: float
    raw_source_text: str


def _optional_section_start(description: str) -> int:
    match = _OPTIONAL_SECTION_MARKERS.search(description)
    return match.start() if match else len(description)


def extract_requirements(job: Job) -> list[ExtractedRequirement]:
    description = job.description or ""
    optional_from = _optional_section_start(description)

    requirements: list[ExtractedRequirement] = []

    for skill in find_skills(description):
        # Where a taxonomy match's *first* mention falls (before/after the
        # "nice to have" marker, if any) decides is_required — a skill
        # mentioned only in the optional section isn't held against a
        # candidate who lacks it.
        match = re.search(rf"(?<![\w+#.]){re.escape(skill)}(?![\w+#])", description, re.IGNORECASE)
        first_index = match.start() if match else 0
        requirements.append(
            ExtractedRequirement(
                category=RequirementCategory.SKILL,
                label=skill,
                is_required=first_index < optional_from,
                weight=1.0,
                raw_source_text=skill,
            )
        )

    experience_match = _EXPERIENCE_PATTERN.search(description)
    if experience_match:
        years = experience_match.group(1)
        requirements.append(
            ExtractedRequirement(
                category=RequirementCategory.EXPERIENCE,
                label=f"{years}+ years of experience",
                is_required=experience_match.start() < optional_from,
                weight=1.0,
                raw_source_text=experience_match.group(0),
            )
        )

    seen_education: set[str] = set()
    for term in EDUCATION_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", description, re.IGNORECASE):
            canonical = term.rstrip(".").upper()
            if canonical in seen_education:
                continue
            seen_education.add(canonical)
            requirements.append(
                ExtractedRequirement(
                    category=RequirementCategory.EDUCATION,
                    label=term,
                    is_required=description.lower().find(term.lower()) < optional_from,
                    weight=0.5,
                    raw_source_text=term,
                )
            )

    if job.location:
        requirements.append(
            ExtractedRequirement(
                category=RequirementCategory.LOCATION,
                label=job.location,
                is_required=True,
                weight=1.0,
                raw_source_text=f"Job location: {job.location}",
            )
        )

    notice_match = _NOTICE_PERIOD_PATTERN.search(description)
    if notice_match:
        days = notice_match.group(1) or notice_match.group(2)
        requirements.append(
            ExtractedRequirement(
                category=RequirementCategory.NOTICE_PERIOD,
                label=f"Notice period up to {days} days",
                is_required=notice_match.start() < optional_from,
                weight=0.5,
                raw_source_text=notice_match.group(0),
            )
        )

    return requirements


async def sync_job_requirements(db: AsyncSession, job: Job) -> list[JobRequirement]:
    """Regenerates every `JobRequirement` row for `job` from its current
    description/location. Safe to call as often as needed (e.g. every time
    a match is requested) — extraction is cheap, pure Python, no I/O."""
    await db.execute(delete(JobRequirement).where(JobRequirement.job_id == job.id))

    rows = [
        JobRequirement(
            organization_id=job.organization_id,
            job_id=job.id,
            category=req.category,
            label=req.label,
            is_required=req.is_required,
            weight=req.weight,
            raw_source_text=req.raw_source_text,
        )
        for req in extract_requirements(job)
    ]
    db.add_all(rows)
    await db.flush()
    return rows


async def get_job_requirements(db: AsyncSession, job_id: uuid.UUID) -> list[JobRequirement]:
    result = await db.execute(select(JobRequirement).where(JobRequirement.job_id == job_id))
    return list(result.scalars().all())

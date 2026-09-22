"""Pure, deterministic candidate<->job scoring — no LLM call, no I/O, no
randomness: the same `JobRequirement` rows and `CandidateResumeProfile`
always produce the same score (the brief's "do not make the score a
meaningless LLM-generated number" requirement). Every sub-score and its
weight is returned alongside the overall number, so a recruiter — or a test
— can see exactly where it came from (the "store the individual scoring
factors so the recruiter can understand WHY" requirement).
"""

import re
from dataclasses import dataclass, field
from typing import Final

from app.models.candidate_resume_profile import CandidateResumeProfile
from app.models.job_requirement import JobRequirement, RequirementCategory

#: Fixed, documented category weights — sum to 1.0. Changing these changes
#: every *future* score, never a past MatchResult (each persisted row keeps
#: its own scoring_breakdown regardless of a later weight change).
CATEGORY_WEIGHTS: Final[dict[RequirementCategory, float]] = {
    RequirementCategory.SKILL: 0.45,
    RequirementCategory.EXPERIENCE: 0.25,
    RequirementCategory.EDUCATION: 0.10,
    RequirementCategory.LOCATION: 0.10,
    RequirementCategory.NOTICE_PERIOD: 0.10,
}

_YEARS_PATTERN = re.compile(r"(\d+)")


@dataclass(frozen=True)
class CategoryScore:
    category: RequirementCategory
    score: float  # 0.0-1.0
    weight: float
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    detail: str = ""
    #: False when this category fell back to a neutral default because
    #: there was no requirement to check or no candidate data to check it
    #: against — used to derive overall `confidence`, never to hide the
    #: category from the recruiter (it's still reported either way).
    is_informative: bool = True


@dataclass(frozen=True)
class DeterministicScore:
    overall_score: int  # 0-100
    confidence: str  # LOW / MEDIUM / HIGH
    categories: list[CategoryScore]
    matching_skills: list[str]
    missing_skills: list[str]
    #: 0.0-1.0 — how much of the total category weight was actually
    #: informative (a requirement existed AND candidate data existed to
    #: check it against). Reported so "why is this score X" is always
    #: traceable, not just implied by the confidence label.
    evidence_completeness: float = 1.0
    #: 0.0-1.0 — how substantial the underlying resume text was (see
    #: `_evidence_density_factor`). 1.0 when there's no resume-substance
    #: concern (e.g. no resume needed at all for the check).
    evidence_density: float = 1.0
    #: Set when the score is capped/discounted by thin evidence — surfaced
    #: to the recruiter as a potential concern, never silently absorbed
    #: into a lower number with no explanation.
    evidence_note: str | None = None


def _score_skills(
    requirements: list[JobRequirement], profile_skills: list[str]
) -> CategoryScore:
    weight = CATEGORY_WEIGHTS[RequirementCategory.SKILL]
    skill_reqs = [r for r in requirements if r.category == RequirementCategory.SKILL]
    if not skill_reqs:
        return CategoryScore(
            RequirementCategory.SKILL, 1.0, weight,
            detail="No specific skills were extracted from the job description.",
            is_informative=False,
        )

    profile_set = {s.lower() for s in profile_skills}
    matched = [r.label for r in skill_reqs if r.label.lower() in profile_set]
    missing = [
        r.label for r in skill_reqs if r.is_required and r.label.lower() not in profile_set
    ]

    # Required skills count for more than explicitly optional ones.
    def _importance(req: JobRequirement) -> float:
        return req.weight * (1.5 if req.is_required else 0.5)

    total_weight = sum(_importance(r) for r in skill_reqs)
    matched_weight = sum(_importance(r) for r in skill_reqs if r.label.lower() in profile_set)
    score = (matched_weight / total_weight) if total_weight else 1.0
    return CategoryScore(
        RequirementCategory.SKILL, score, weight, matched=matched, missing=missing,
        detail=f"{len(matched)} of {len(skill_reqs)} job skills found on the candidate's resume.",
    )


def _parse_leading_int(text: str) -> int | None:
    match = _YEARS_PATTERN.search(text)
    return int(match.group(1)) if match else None


def _score_experience(
    requirements: list[JobRequirement], total_experience_years: int | None
) -> CategoryScore:
    weight = CATEGORY_WEIGHTS[RequirementCategory.EXPERIENCE]
    exp_reqs = [r for r in requirements if r.category == RequirementCategory.EXPERIENCE]
    if not exp_reqs:
        return CategoryScore(
            RequirementCategory.EXPERIENCE, 1.0, weight,
            detail="No specific experience requirement was extracted from the job description.",
            is_informative=False,
        )

    required_years = _parse_leading_int(exp_reqs[0].label)
    if required_years is None or total_experience_years is None:
        return CategoryScore(
            RequirementCategory.EXPERIENCE, 0.5, weight,
            detail="The role's required experience or the candidate's experience is unknown.",
            is_informative=False,
        )

    detail = f"Candidate has {total_experience_years} years; role requires {required_years}+."
    if total_experience_years >= required_years:
        return CategoryScore(RequirementCategory.EXPERIENCE, 1.0, weight, detail=detail)
    ratio = (total_experience_years / required_years) if required_years else 1.0
    return CategoryScore(
        RequirementCategory.EXPERIENCE, max(0.0, ratio), weight, detail=detail
    )


def _score_education(
    requirements: list[JobRequirement], profile_education: list[str]
) -> CategoryScore:
    weight = CATEGORY_WEIGHTS[RequirementCategory.EDUCATION]
    edu_reqs = [r for r in requirements if r.category == RequirementCategory.EDUCATION]
    if not edu_reqs:
        return CategoryScore(
            RequirementCategory.EDUCATION, 1.0, weight,
            detail="No specific education requirement was extracted from the job description.",
            is_informative=False,
        )
    if not profile_education:
        return CategoryScore(
            RequirementCategory.EDUCATION, 0.5, weight,
            detail="No education information was found for this candidate.",
            is_informative=False,
        )

    profile_terms = {term.lower() for term in profile_education}
    matched = [r.label for r in edu_reqs if r.label.lower() in profile_terms]
    missing = [
        r.label for r in edu_reqs if r.is_required and r.label.lower() not in profile_terms
    ]
    score = len(matched) / len(edu_reqs) if edu_reqs else 1.0
    return CategoryScore(
        RequirementCategory.EDUCATION, score, weight, matched=matched, missing=missing,
        detail=f"{len(matched)} of {len(edu_reqs)} education requirements matched.",
    )


def _score_location(
    requirements: list[JobRequirement], profile_location: str | None
) -> CategoryScore:
    weight = CATEGORY_WEIGHTS[RequirementCategory.LOCATION]
    loc_reqs = [r for r in requirements if r.category == RequirementCategory.LOCATION]
    if not loc_reqs:
        return CategoryScore(
            RequirementCategory.LOCATION, 1.0, weight,
            detail="The job has no location on file.", is_informative=False,
        )
    if not profile_location:
        return CategoryScore(
            RequirementCategory.LOCATION, 0.5, weight,
            detail="The candidate has no location on file.", is_informative=False,
        )

    job_location = loc_reqs[0].label.strip().lower()
    candidate_location = profile_location.strip().lower()
    is_remote = "remote" in job_location
    matches = (
        is_remote or job_location in candidate_location or candidate_location in job_location
    )
    detail = (
        f"Candidate location ({profile_location}) matches the job location "
        f"({loc_reqs[0].label})."
        if matches
        else f"Candidate location ({profile_location}) differs from the job location "
        f"({loc_reqs[0].label})."
    )
    return CategoryScore(
        RequirementCategory.LOCATION,
        1.0 if matches else 0.3,
        weight,
        matched=[loc_reqs[0].label] if matches else [],
        missing=[] if matches else [loc_reqs[0].label],
        detail=detail,
    )


def _score_notice_period(
    requirements: list[JobRequirement], notice_period_days: int | None
) -> CategoryScore:
    weight = CATEGORY_WEIGHTS[RequirementCategory.NOTICE_PERIOD]
    notice_reqs = [r for r in requirements if r.category == RequirementCategory.NOTICE_PERIOD]
    if not notice_reqs:
        return CategoryScore(
            RequirementCategory.NOTICE_PERIOD, 1.0, weight,
            detail="The job description does not specify a notice period requirement.",
            is_informative=False,
        )
    if notice_period_days is None:
        return CategoryScore(
            RequirementCategory.NOTICE_PERIOD, 0.5, weight,
            detail="The candidate's notice period is unknown.", is_informative=False,
        )

    max_days = _parse_leading_int(notice_reqs[0].label)
    if max_days is None:
        return CategoryScore(
            RequirementCategory.NOTICE_PERIOD, 0.5, weight,
            detail="Could not parse the job's notice period requirement.", is_informative=False,
        )
    if notice_period_days <= max_days:
        return CategoryScore(
            RequirementCategory.NOTICE_PERIOD, 1.0, weight,
            detail=f"Candidate's notice period ({notice_period_days} days) fits within "
            f"{max_days} days.",
        )
    ratio = max(0.0, max_days / notice_period_days) if notice_period_days else 0.0
    return CategoryScore(
        RequirementCategory.NOTICE_PERIOD, ratio, weight,
        detail=f"Candidate's notice period ({notice_period_days} days) exceeds the required "
        f"{max_days} days.",
    )


#: Below this many words, a resume is treated as a bare checklist — its
#: keyword matches are real, but nothing corroborates them, so the score
#: they produce is heavily discounted (never fully zeroed: a match is still
#: a match, just a weakly-evidenced one).
_MINIMAL_WORD_COUNT: Final = 15
#: At or above this many words, resume length is no longer treated as a
#: reliability concern — the discount only ever applies below this point.
_SUBSTANTIVE_WORD_COUNT: Final = 120
_MINIMAL_DENSITY_FACTOR: Final = 0.4

#: Confidence is about *how much could actually be checked*
#: (`evidence_completeness`, weighted by category importance) and *how much
#: substance backed what was checked* (`evidence_density`) — never about
#: how high the resulting score happens to be. A thin resume that
#: coincidentally satisfies every extracted requirement still gets LOW/
#: MEDIUM confidence, not HIGH, because there was little to verify it
#: against.
_HIGH_CONFIDENCE_COMPLETENESS: Final = 0.85
_HIGH_CONFIDENCE_DENSITY: Final = 0.85
_MEDIUM_CONFIDENCE_COMPLETENESS: Final = 0.5
_MEDIUM_CONFIDENCE_DENSITY: Final = 0.5


def _evidence_density_factor(resume_word_count: int | None) -> float:
    """How much a resume's sheer substance should be trusted as
    corroborating evidence, independent of which categories happened to
    find a match. A near-empty resume that happens to list exactly the
    required skills as a bare checklist ("Priya QA. 4 years QA experience.
    Skills: Python, pytest, Selenium.") contains real text with real
    keyword matches — but with almost nothing else to corroborate them, the
    overall match score must not read the same as a fully documented work
    history satisfying the same requirements (the brief's "empty/minimal
    resumes must not receive artificially high scores").

    A smooth ramp between two thresholds, not a fixed "cap at 50%" rule: a
    200-word resume is trusted fully, an 80-word resume is discounted
    moderately, and anything at or below `_MINIMAL_WORD_COUNT` floors out at
    `_MINIMAL_DENSITY_FACTOR` (never zero — the matched keywords are still
    real signal, just weak on their own).
    """
    if resume_word_count is None:
        return 0.6  # unknown substance (e.g. a pre-migration row) — a moderate, not free, discount
    if resume_word_count >= _SUBSTANTIVE_WORD_COUNT:
        return 1.0
    if resume_word_count <= _MINIMAL_WORD_COUNT:
        return _MINIMAL_DENSITY_FACTOR
    span = _SUBSTANTIVE_WORD_COUNT - _MINIMAL_WORD_COUNT
    progress = (resume_word_count - _MINIMAL_WORD_COUNT) / span
    return _MINIMAL_DENSITY_FACTOR + (1 - _MINIMAL_DENSITY_FACTOR) * progress


def score(
    requirements: list[JobRequirement], profile: CandidateResumeProfile
) -> DeterministicScore:
    categories = [
        _score_skills(requirements, profile.skills),
        _score_experience(requirements, profile.total_experience_years),
        _score_education(requirements, profile.education),
        _score_location(requirements, profile.location),
        _score_notice_period(requirements, profile.notice_period_days),
    ]

    informative = [c for c in categories if c.is_informative]
    informative_weight = sum(c.weight for c in informative)
    total_weight = sum(c.weight for c in categories)
    evidence_completeness = (informative_weight / total_weight) if total_weight else 0.0

    if informative_weight > 0:
        # Renormalized over only the categories that had both a real
        # requirement *and* real candidate data to check it against — a
        # category missing either is excluded, never defaulted to a neutral
        # score that silently pads the total (the brief: "missing candidate
        # information/job requirements must not silently behave like
        # perfect matching").
        raw_score = sum(c.score * c.weight for c in informative) / informative_weight
    else:
        # Nothing could actually be checked — there is no basis for a
        # match. The honest answer is "no score", never "100%".
        raw_score = 0.0

    density_factor = _evidence_density_factor(profile.resume_word_count)
    final_score = raw_score * density_factor

    evidence_note: str | None = None
    if informative_weight == 0:
        evidence_note = (
            "Neither the job description nor the candidate's profile had enough extracted "
            "detail to check any requirement — this score has no evidentiary basis."
        )
    elif density_factor < 0.99:
        word_count = profile.resume_word_count if profile.resume_word_count is not None else 0
        evidence_note = (
            f"This candidate's resume provides limited detail ({word_count} words) — treat "
            "this match score with caution until more information is available."
        )
    elif evidence_completeness < _MEDIUM_CONFIDENCE_COMPLETENESS:
        evidence_note = (
            "Most requirement categories could not be checked — either the job description or "
            "the candidate's profile is missing key details."
        )

    if (
        evidence_completeness >= _HIGH_CONFIDENCE_COMPLETENESS
        and density_factor >= _HIGH_CONFIDENCE_DENSITY
    ):
        confidence = "HIGH"
    elif (
        evidence_completeness >= _MEDIUM_CONFIDENCE_COMPLETENESS
        and density_factor >= _MEDIUM_CONFIDENCE_DENSITY
    ):
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    overall = round(100 * final_score)
    skill_category = categories[0]
    return DeterministicScore(
        overall_score=max(0, min(100, overall)),
        confidence=confidence,
        categories=categories,
        matching_skills=skill_category.matched,
        missing_skills=skill_category.missing,
        evidence_completeness=round(evidence_completeness, 3),
        evidence_density=round(density_factor, 3),
        evidence_note=evidence_note,
    )

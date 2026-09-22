"""Pure unit tests for the deterministic matching scorer — no DB, no mocks,
no LLM: the same inputs must always produce the same, explainable output
(the brief's "do not make the score a meaningless LLM-generated number"
requirement).

Also covers the evidence-quality fix: a score must reflect how much could
actually be checked and how substantial the underlying resume was, not just
whichever requirements happened to line up — missing job requirements,
missing candidate data, and thin/minimal resumes must never silently behave
like a perfect match.
"""

from app.models.candidate_resume_profile import CandidateResumeProfile
from app.models.job_requirement import JobRequirement, RequirementCategory
from app.services.matching.deterministic_scorer import score


def _requirement(category: RequirementCategory, label: str, *, is_required: bool = True, weight: float = 1.0) -> JobRequirement:
    return JobRequirement(
        category=category, label=label, is_required=is_required, weight=weight, raw_source_text=label,
    )


def _profile(**kwargs) -> CandidateResumeProfile:
    # `resume_word_count=150` by default — a normal, substantive resume, so
    # tests that aren't specifically about the evidence-density fix aren't
    # accidentally discounted by it. Tests that ARE about it override this.
    defaults = dict(
        skills=[], total_experience_years=None, education=[], location=None,
        notice_period_days=None, resume_word_count=150,
    )
    defaults.update(kwargs)
    return CandidateResumeProfile(**defaults)


def test_perfect_match_scores_100() -> None:
    requirements = [
        _requirement(RequirementCategory.SKILL, "Python"),
        _requirement(RequirementCategory.SKILL, "React"),
        _requirement(RequirementCategory.EXPERIENCE, "3+ years of experience"),
        _requirement(RequirementCategory.LOCATION, "Bengaluru"),
    ]
    profile = _profile(
        skills=["Python", "React"], total_experience_years=5, location="Bengaluru",
    )

    result = score(requirements, profile)

    assert result.overall_score == 100
    assert result.matching_skills == ["Python", "React"]
    assert result.missing_skills == []
    # SKILL/EXPERIENCE/LOCATION are informative here (80% of total weight);
    # EDUCATION and NOTICE_PERIOD have no extracted requirement, so
    # confidence is MEDIUM, not HIGH — confidence tracks how much of the
    # *requirement space* could be checked, not just how high the resulting
    # score is.
    assert result.confidence == "MEDIUM"
    assert result.evidence_density == 1.0  # a substantive resume — no discount applied


def test_missing_required_skill_reduces_score_and_is_reported() -> None:
    requirements = [
        _requirement(RequirementCategory.SKILL, "Python"),
        _requirement(RequirementCategory.SKILL, "AWS"),
    ]
    profile = _profile(skills=["Python"])

    result = score(requirements, profile)

    assert result.matching_skills == ["Python"]
    assert result.missing_skills == ["AWS"]
    assert 0 < result.overall_score < 100


def test_optional_skill_missing_does_not_count_as_missing() -> None:
    requirements = [
        _requirement(RequirementCategory.SKILL, "Python"),
        _requirement(RequirementCategory.SKILL, "Kubernetes", is_required=False),
    ]
    profile = _profile(skills=["Python"])

    result = score(requirements, profile)

    # Only required-and-absent skills are "missing" — an optional skill the
    # candidate lacks is not held against them.
    assert result.missing_skills == []


def test_candidate_with_only_unrelated_skills_scores_low_on_skills() -> None:
    requirements = [
        _requirement(RequirementCategory.SKILL, "React"),
        _requirement(RequirementCategory.SKILL, "Node.js"),
    ]
    profile = _profile(skills=["Digital Marketing", "SEO", "Excel"])

    result = score(requirements, profile)

    assert result.matching_skills == []
    assert set(result.missing_skills) == {"React", "Node.js"}
    assert result.overall_score == 0


def test_missing_job_requirements_never_behave_like_a_perfect_match() -> None:
    """No requirements were extracted at all (e.g. a vague job description)
    — there is nothing to check the candidate against, so the honest score
    is 0 with LOW confidence, never a free 100%."""
    result = score([], _profile())

    assert result.overall_score == 0
    assert result.confidence == "LOW"
    assert result.evidence_completeness == 0.0
    assert result.evidence_note is not None
    for category in result.categories:
        assert category.is_informative is False


def test_missing_candidate_data_is_excluded_not_defaulted_to_perfect() -> None:
    """The job specifies education/location/notice-period requirements, but
    the candidate's profile has none of that data — those categories must
    be excluded from the score (not silently scored as if they matched)."""
    requirements = [
        _requirement(RequirementCategory.SKILL, "Python"),
        _requirement(RequirementCategory.EDUCATION, "B.Tech"),
        _requirement(RequirementCategory.LOCATION, "Mumbai"),
        _requirement(RequirementCategory.NOTICE_PERIOD, "Notice period up to 15 days"),
    ]
    profile = _profile(skills=["Python"])  # no education, location, or notice_period_days

    result = score(requirements, profile)

    education = next(c for c in result.categories if c.category == RequirementCategory.EDUCATION)
    location = next(c for c in result.categories if c.category == RequirementCategory.LOCATION)
    notice = next(c for c in result.categories if c.category == RequirementCategory.NOTICE_PERIOD)
    assert education.is_informative is False
    assert location.is_informative is False
    assert notice.is_informative is False
    # Only SKILL (fully matched) was informative -> the score is 100% of
    # what *could* be checked, but confidence must reflect how little that
    # was (25% of total category weight).
    assert result.overall_score == 100
    assert result.confidence == "LOW"
    assert result.evidence_completeness < 0.5


def test_empty_resume_yields_low_score_despite_keyword_overlap() -> None:
    """A candidate with literally no resume (word count 0) must never score
    high, even if the job's requirements happen to line up with whatever
    little structured data exists."""
    requirements = [
        _requirement(RequirementCategory.SKILL, "Python"),
        _requirement(RequirementCategory.EXPERIENCE, "2+ years of experience"),
    ]
    profile = _profile(skills=["Python"], total_experience_years=2, resume_word_count=0)

    result = score(requirements, profile)

    assert result.overall_score <= 40
    assert result.confidence == "LOW"
    assert result.evidence_note is not None
    assert "0 words" in result.evidence_note


def test_minimal_resume_does_not_score_artificially_high() -> None:
    """The exact reported bug: a one-line resume that happens to list
    exactly the required skills must not score 95%. ("Priya QA. 4 years QA
    experience. Skills: Python, pytest, Selenium." is 11 words.)"""
    requirements = [
        _requirement(RequirementCategory.SKILL, "Python"),
        _requirement(RequirementCategory.SKILL, "pytest"),
        _requirement(RequirementCategory.SKILL, "Selenium"),
        _requirement(RequirementCategory.EXPERIENCE, "4+ years of experience"),
    ]
    profile = _profile(
        skills=["Python", "pytest", "Selenium"],
        total_experience_years=4,
        resume_word_count=11,
    )

    result = score(requirements, profile)

    # Every extracted requirement is technically satisfied (raw_score would
    # be 100%), but with only an 11-word resume behind it, the evidence
    # density factor must pull the headline score well below what a fully
    # documented match would show.
    assert result.overall_score <= 45
    assert result.confidence == "LOW"
    assert result.evidence_note is not None
    assert "11 words" in result.evidence_note
    assert any("limited detail" in concern for concern in [result.evidence_note])


def test_strong_documented_evidence_scores_high_with_high_confidence() -> None:
    """The counterpart to the minimal-resume test: full data, a substantive
    resume, and every category informative and matching -> HIGH confidence,
    not just a high score."""
    requirements = [
        _requirement(RequirementCategory.SKILL, "Python"),
        _requirement(RequirementCategory.SKILL, "Django"),
        _requirement(RequirementCategory.EXPERIENCE, "3+ years of experience"),
        _requirement(RequirementCategory.EDUCATION, "B.Tech"),
        _requirement(RequirementCategory.LOCATION, "Remote"),
        _requirement(RequirementCategory.NOTICE_PERIOD, "Notice period up to 30 days"),
    ]
    profile = _profile(
        skills=["Python", "Django"],
        total_experience_years=5,
        education=["B.Tech"],
        location="Bengaluru",
        notice_period_days=20,
        resume_word_count=400,
    )

    result = score(requirements, profile)

    assert result.overall_score == 100
    assert result.confidence == "HIGH"
    assert result.evidence_note is None
    assert result.evidence_completeness == 1.0
    assert result.evidence_density == 1.0


def test_experience_shortfall_is_proportional() -> None:
    requirements = [_requirement(RequirementCategory.EXPERIENCE, "10+ years of experience")]
    profile = _profile(total_experience_years=5)

    result = score(requirements, profile)

    experience_category = next(c for c in result.categories if c.category == RequirementCategory.EXPERIENCE)
    assert experience_category.score == 0.5
    assert "5 years" in experience_category.detail
    assert "10+" in experience_category.detail


def test_location_mismatch_is_penalized_but_not_zeroed() -> None:
    requirements = [_requirement(RequirementCategory.LOCATION, "Mumbai")]
    profile = _profile(location="Delhi")

    result = score(requirements, profile)

    location_category = next(c for c in result.categories if c.category == RequirementCategory.LOCATION)
    assert location_category.score == 0.3
    assert location_category.missing == ["Mumbai"]


def test_remote_job_always_matches_location() -> None:
    requirements = [_requirement(RequirementCategory.LOCATION, "Remote")]
    profile = _profile(location="Anywhere")

    result = score(requirements, profile)

    location_category = next(c for c in result.categories if c.category == RequirementCategory.LOCATION)
    assert location_category.score == 1.0


def test_notice_period_within_bound_matches() -> None:
    requirements = [_requirement(RequirementCategory.NOTICE_PERIOD, "Notice period up to 30 days")]
    profile = _profile(notice_period_days=15)

    result = score(requirements, profile)

    notice_category = next(c for c in result.categories if c.category == RequirementCategory.NOTICE_PERIOD)
    assert notice_category.score == 1.0


def test_score_is_deterministic_across_repeated_calls() -> None:
    requirements = [
        _requirement(RequirementCategory.SKILL, "Python"),
        _requirement(RequirementCategory.EXPERIENCE, "4+ years of experience"),
    ]
    profile = _profile(skills=["Python"], total_experience_years=4)

    first = score(requirements, profile)
    second = score(requirements, profile)

    assert first.overall_score == second.overall_score
    assert first.confidence == second.confidence
    assert first.evidence_completeness == second.evidence_completeness

"""Unit tests for deterministic job-requirement extraction — no DB, no LLM."""

from app.models.job import Job, JobStatus
from app.models.job_requirement import RequirementCategory
from app.services.matching.requirement_extraction import extract_requirements


def _job(description: str, *, location: str | None = None) -> Job:
    return Job(title="Full Stack Developer", description=description, location=location, status=JobStatus.OPEN)


def test_extracts_required_skills() -> None:
    job = _job("We need a developer strong in React, Node.js and MongoDB.")

    requirements = extract_requirements(job)

    skills = {r.label for r in requirements if r.category == RequirementCategory.SKILL}
    assert {"React", "Node.js", "MongoDB"} <= skills
    assert all(r.is_required for r in requirements if r.category == RequirementCategory.SKILL)


def test_nice_to_have_section_is_marked_optional() -> None:
    job = _job(
        "Required: Python, Django. Nice to have: AWS, Docker."
    )

    requirements = extract_requirements(job)
    by_label = {r.label: r for r in requirements if r.category == RequirementCategory.SKILL}

    assert by_label["Python"].is_required is True
    assert by_label["Django"].is_required is True
    assert by_label["AWS"].is_required is False
    assert by_label["Docker"].is_required is False


def test_extracts_experience_requirement() -> None:
    job = _job("Looking for a candidate with 5+ years of experience in backend development.")

    requirements = extract_requirements(job)

    experience = [r for r in requirements if r.category == RequirementCategory.EXPERIENCE]
    assert len(experience) == 1
    assert "5" in experience[0].label


def test_extracts_education_requirement() -> None:
    job = _job("A B.Tech in Computer Science is required for this role.")

    requirements = extract_requirements(job)

    education = [r.label for r in requirements if r.category == RequirementCategory.EDUCATION]
    assert "B.Tech" in education


def test_job_location_becomes_a_location_requirement() -> None:
    job = _job("Great opportunity for a backend engineer.", location="Bengaluru")

    requirements = extract_requirements(job)

    location = [r for r in requirements if r.category == RequirementCategory.LOCATION]
    assert len(location) == 1
    assert location[0].label == "Bengaluru"


def test_no_location_means_no_location_requirement() -> None:
    job = _job("Great opportunity for a backend engineer.")

    requirements = extract_requirements(job)

    assert not [r for r in requirements if r.category == RequirementCategory.LOCATION]


def test_extraction_is_deterministic() -> None:
    job = _job("Python, React, 3+ years of experience, B.Tech required.", location="Remote")

    first = extract_requirements(job)
    second = extract_requirements(job)

    assert first == second

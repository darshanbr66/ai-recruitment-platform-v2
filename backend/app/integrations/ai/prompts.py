"""Shared prompt construction for resume screening — kept provider-agnostic
so both adapters ask the model the same question the same way (see
docs/ai-screening.md § 5)."""

_SCREENING_SCHEMA = """{
  "overall_score": <integer 0-100, overall fit for this role>,
  "recommendation": <one of "STRONG_MATCH", "POSSIBLE_MATCH", "WEAK_MATCH", "NOT_A_MATCH">,
  "summary": <2-3 sentence plain-language summary for a recruiter>,
  "matching_skills": [<skills from the job description the resume evidences>],
  "missing_skills": [<skills the job asks for that the resume does not evidence>],
  "strengths": [<short bullet points>],
  "concerns": [<short bullet points - gaps, ambiguities, potential red flags>],
  "experience_assessment": <short paragraph on relevant experience>,
  "education_assessment": <short paragraph on relevant education/certifications>
}"""

SYSTEM_PROMPT = (
    "You are an assistant helping a recruiter screen a job application. You "
    "evaluate how well a candidate's resume matches a job's requirements. "
    "You are not making the hiring decision - a human recruiter reviews your "
    "output. Be honest and specific: if the resume lacks evidence for "
    "something, say so in missing_skills or concerns rather than guessing. "
    "Respond with ONLY a single JSON object matching this exact schema, no "
    "other text:\n" + _SCREENING_SCHEMA
)


def build_user_prompt(*, resume_text: str, job_title: str, job_description: str) -> str:
    return (
        f"Job title: {job_title}\n\n"
        f"Job description:\n{job_description}\n\n"
        f"Candidate resume (extracted text):\n{resume_text}"
    )

"""A curated, keyword-matchable skill vocabulary shared by both sides of the
deterministic matching engine (requirement_extraction.py extracts a Job's
required skills from it; candidate_profile_extraction.py extracts a
Candidate's skills from the same list), so "React" on a job description and
"React" on a resume are guaranteed to be compared as the same token rather
than depending on an LLM to normalize spelling/casing/synonyms.

This is a real, working starting vocabulary — not exhaustive, and
deliberately not: a fixed Python list is a stopgap for this phase. It is
intentionally easy to extend (append to `SKILLS`) and isolated in its own
module so a later phase can replace the source with an admin-editable
database table without touching either extraction module's logic.
"""

import re
from typing import Final

SKILLS: Final[tuple[str, ...]] = (
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "C", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "Perl", "Dart",
    "Objective-C", "Shell Scripting", "Bash",
    # Frontend
    "React", "React Native", "Angular", "Vue.js", "Next.js", "Svelte", "Redux",
    "HTML", "CSS", "Sass", "Tailwind CSS", "Bootstrap", "jQuery", "Webpack", "Vite",
    # Backend / frameworks
    "Node.js", "Express.js", "Django", "Flask", "FastAPI", "Spring Boot", "Spring",
    ".NET", "ASP.NET", "Ruby on Rails", "Laravel", "NestJS", "GraphQL", "REST APIs",
    "gRPC", "Microservices",
    # Data / databases
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "SQLite",
    "Oracle", "SQL Server", "Cassandra", "DynamoDB", "Snowflake", "BigQuery",
    "Data Warehousing", "ETL",
    # Cloud / DevOps
    "AWS", "Azure", "Google Cloud Platform", "GCP", "Docker", "Kubernetes",
    "Terraform", "Ansible", "Jenkins", "CI/CD", "Git", "GitHub Actions", "GitLab CI",
    "Linux", "Nginx", "Serverless",
    # Data science / AI
    "Machine Learning", "Deep Learning", "Natural Language Processing", "NLP",
    "Computer Vision", "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy",
    "Data Analysis", "Data Science", "Data Engineering", "Generative AI", "LLM",
    "MLOps",
    # Mobile
    "Android", "iOS", "Flutter", "Xamarin",
    # QA / testing
    "Selenium", "Cypress", "Jest", "PyTest", "JUnit", "Manual Testing",
    "Test Automation", "QA",
    # Project management / methodology
    "Agile", "Scrum", "Kanban", "JIRA", "Project Management", "Product Management",
    "Stakeholder Management",
    # Design
    "UI/UX Design", "Figma", "Adobe XD", "Sketch", "Wireframing",
    # Business / analyst
    "Business Analysis", "Financial Modeling", "Excel", "Power BI", "Tableau",
    "SAP", "Salesforce", "CRM", "ERP",
    # HR / recruitment (the platform's own domain)
    "Talent Acquisition", "Recruitment", "HR Operations", "Onboarding",
    "Payroll", "Employee Relations",
    # Sales / marketing
    "Sales", "Digital Marketing", "SEO", "Content Marketing", "Social Media Marketing",
    "Email Marketing", "Lead Generation",
    # Soft skills — matched but weighted lightly by the scorer since they're
    # rarely a differentiator on their own.
    "Communication", "Leadership", "Team Management", "Problem Solving",
    "Critical Thinking",
)

# Longer labels first, so "React Native" matches before the bare "React"
# inside it does; each is compiled with word boundaries so "Go" doesn't match
# inside "Google" and "R" doesn't match inside "Recruitment".
_PATTERNS: Final[list[tuple[str, re.Pattern[str]]]] = sorted(
    (
        (skill, re.compile(rf"(?<![\w+#.]){re.escape(skill)}(?![\w+#])", re.IGNORECASE))
        for skill in SKILLS
    ),
    key=lambda pair: -len(pair[0]),
)


def find_skills(text: str) -> list[str]:
    """Every taxonomy skill mentioned in `text`, in taxonomy order (not
    order-of-appearance), each returned exactly once in its canonical
    (taxonomy) spelling regardless of how it was cased in `text`."""
    if not text:
        return []
    found: list[str] = []
    for skill, pattern in _PATTERNS:
        if pattern.search(text):
            found.append(skill)
    # Restore taxonomy (declaration) order rather than the longest-first
    # sort order used for matching.
    order = {skill: index for index, skill in enumerate(SKILLS)}
    return sorted(found, key=lambda skill: order[skill])


#: Degree/qualification terms scanned for on both sides of the matching
#: engine (requirement_extraction.py, candidate_profile_extraction.py) —
#: kept alongside SKILLS since it's the same "controlled vocabulary
#: keyword-matched against free text" approach, just a different category.
EDUCATION_TERMS: Final[tuple[str, ...]] = (
    "B.Tech", "B.E.", "Bachelor's", "Bachelor", "BCA", "B.Sc", "BBA",
    "M.Tech", "M.E.", "Master's", "Master", "MCA", "M.Sc", "MBA",
    "PhD", "Ph.D.", "Doctorate", "Diploma", "Graduate", "Post Graduate",
)

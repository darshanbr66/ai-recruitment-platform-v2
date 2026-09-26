"""Real (not mocked) check of AI resume-to-JD screening, against a realistic
JD and three synthetic resumes rendered as actual PDFs:

    1. clearly matching   (MERN developer, 3 years)       -> expected MATCH
    2. clearly unrelated  (accountant)                     -> expected NOT_MATCH
    3. partially matching (junior React-only developer)    -> reported (borderline)

Default mode exercises  PDF -> text extraction -> configured LLM provider
(`get_llm_provider()`; Gemini when GEMINI_API_KEY is set).

`--e2e` additionally drives the full HTTP flow in-process — email code,
verification, application submission, AI screening gate, welcome email, HR
override, HR job match — against the local database inside ONE transaction
that is rolled back at the end (the same isolation the test suite uses), so
nothing is persisted and no real email is sent (a recording provider stands
in for it).

Run from backend/:  python scripts/verify_ai_screening.py [--e2e]
Uses real AI provider calls (and their cost/quota). Never point this at the
production database.
"""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Same isolation as tests/conftest.py, set before Settings is first read:
# resume files go to local disk (never a real GridFS deployment), and no
# real email provider is configured (a recorder captures every email).
for _name in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL", "RESEND_API_KEY", "EMAIL_FROM"):
    os.environ[_name] = ""
os.environ["RESUME_STORAGE_PROVIDER"] = "local"

from app.core.asyncio_compat import configure_event_loop_policy  # noqa: E402

configure_event_loop_policy()

from app import demo_data  # noqa: E402
from app.integrations.ai import get_llm_provider  # noqa: E402
from app.integrations.ai.extraction import extract_resume_text  # noqa: E402

RESUMES: dict[str, dict[str, Any]] = {
    "match": {
        "expected": "MATCH",
        "name": "Aarav Demo",
        "lines": [
            "AARAV DEMO - Full Stack Developer (MERN)",
            "Chennai, India | aarav.demo@example.com | github.com/aarav-demo",
            "",
            "SUMMARY",
            "Full stack developer with 3 years of professional experience building MERN stack",
            "web applications: React.js frontends and Node.js/Express.js REST APIs on MongoDB.",
            "",
            "SKILLS",
            "JavaScript (ES6+), TypeScript, React.js, Redux Toolkit, React Router, Hooks,",
            "Node.js, Express.js, MongoDB, Mongoose, aggregation pipelines, REST API design,",
            "JWT authentication, Jest, React Testing Library, Supertest, Git, GitHub Actions,",
            "Docker, AWS EC2/S3, HTML5, CSS3, Tailwind CSS, Agile/Scrum.",
            "",
            "EXPERIENCE",
            "Software Engineer - Brightcart Commerce (demo company), Chennai | Jun 2022 - Present",
            "- Built React.js storefront features (cart, checkout, order tracking) used daily.",
            "- Designed Express.js REST APIs with JWT auth, validation and centralized errors.",
            "- Modelled MongoDB collections; wrote aggregation pipelines for sales reports and",
            "  added indexes that cut report latency by 60%.",
            "- Wrote Jest/Supertest suites; reviewed pull requests in a Git PR workflow.",
            "Junior Developer - Pixelworks Studio (demo company) | Jul 2021 - May 2022",
            "- Developed Node.js/Express services and React admin dashboards.",
            "",
            "EDUCATION",
            "B.Tech in Computer Science and Engineering - Anna University, 2021",
        ],
    },
    "not_match": {
        "expected": "NOT_MATCH",
        "name": "Meera Demo",
        "lines": [
            "MEERA DEMO - Senior Accountant",
            "Coimbatore, India | meera.demo@example.com",
            "",
            "PROFILE",
            "Accounts professional with 6 years of experience in general ledger accounting,",
            "GST filing, payroll processing and statutory audits for manufacturing firms.",
            "",
            "CORE SKILLS",
            "Tally ERP 9, SAP FICO (end user), Advanced Microsoft Excel, GST and TDS returns,",
            "accounts payable/receivable, bank reconciliation, MIS reporting, budgeting.",
            "",
            "EXPERIENCE",
            "Senior Accountant - Kovai Textiles (demo company) | 2021 - Present",
            "- Manage month-end closing, GST reconciliation and vendor payments.",
            "- Prepare MIS reports and coordinate statutory audits.",
            "Accounts Executive - Sri Lakshmi Traders (demo company) | 2018 - 2021",
            "- Handled payroll, TDS returns and bank reconciliations.",
            "",
            "EDUCATION",
            "B.Com (Accounting and Finance) - Bharathiar University, 2018",
            "Pursuing CMA Intermediate",
        ],
    },
    "partial": {
        "expected": None,
        "name": "Karthik Demo",
        "lines": [
            "KARTHIK DEMO - Frontend Developer",
            "Bengaluru, India | karthik.demo@example.com",
            "",
            "SUMMARY",
            "Frontend developer with 1.5 years of experience building React.js interfaces.",
            "",
            "SKILLS",
            "JavaScript (ES6), React.js, HTML5, CSS3, Bootstrap, Git, basic REST API consumption",
            "with Axios. Currently learning Node.js through online courses.",
            "",
            "EXPERIENCE",
            "Frontend Developer - Nimbus Apps (demo company) | Jan 2024 - Present",
            "- Built React components and pages from Figma designs.",
            "- Integrated existing REST APIs built by the backend team.",
            "",
            "EDUCATION",
            "BCA - Bangalore University, 2023",
        ],
    },
}


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_text_pdf(lines: list[str]) -> bytes:
    """A real single-page PDF with one text line per entry (Helvetica 11pt),
    readable by pypdf exactly like an uploaded resume."""
    body = ["BT", "/F1 11 Tf", "14 TL", "50 760 Td"]
    for line in lines:
        body.append(f"({_pdf_escape(line)}) Tj T*")
    body.append("ET")
    stream = "\n".join(body).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


def _resume_pdf(key: str) -> bytes:
    lines = [line.replace("–", "-") for line in RESUMES[key]["lines"]]
    return build_text_pdf(lines)


async def provider_check() -> bool:
    provider = get_llm_provider()
    print(f"Provider: {provider.name} / {provider.model}\n")
    ok = True
    for key, resume in RESUMES.items():
        text = extract_resume_text(content=_resume_pdf(key), filename=f"{key}.pdf")
        verdict = await provider.screen_candidate(
            resume_text=text,
            job_title=demo_data.DEMO_JOB_TITLE,
            job_description=demo_data.DEMO_JOB_DESCRIPTION,
        )
        expected = resume["expected"]
        passed = expected is None or verdict.decision == expected
        ok = ok and passed
        print(
            f"[{'PASS' if passed else 'FAIL'}] {resume['name']:<13} ({key}): "
            f"decision={verdict.decision} expected={expected or 'either'} "
            f"score={verdict.overall_score} recommendation={verdict.recommendation}"
        )
        print(f"    extracted {len(text.split())} words from the PDF")
        print(f"    matched: {verdict.matched_requirements[:6]}")
        print(f"    missing: {verdict.missing_requirements[:6]}")
        print(f"    summary: {verdict.summary}\n")
    return ok


async def e2e_check() -> bool:
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.security import hash_password
    from app.db.rls import rls_bypass
    from app.db.session import engine, get_db
    from app.integrations.email import EmailProvider
    from app.main import app
    from app.models.rbac import Role, UserRole
    from app.models.user import User
    from app.services import notification_service

    sent: list[dict[str, Any]] = []

    class Recorder(EmailProvider):
        async def send(self, *, to, subject, html, text=None, reply_to=None, cc=(), bcc=()):  # type: ignore[no-untyped-def]
            sent.append({"to": list(to), "subject": subject, "text": text, "reply_to": reply_to})

    ok = True

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and condition
        print(f"[{'PASS' if condition else 'FAIL'}] {label}{(' - ' + detail) if detail else ''}")

    async with engine.connect() as connection:
        await connection.begin()
        session_factory = async_sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        async with session_factory() as db:

            async def override_get_db():  # type: ignore[no-untyped-def]
                try:
                    yield db
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise

            async with rls_bypass(db):
                role = await db.scalar(
                    select(Role).where(Role.organization_id.is_(None), Role.name == "SUPER_ADMIN")
                )
                admin = User(
                    organization_id=None,
                    email="verify.ai.superadmin@example.com",
                    hashed_password=hash_password("VerifyAiPass123"),
                    full_name="AI Verification Admin",
                )
                db.add(admin)
                await db.flush()
                db.add(UserRole(user_id=admin.id, role_id=role.id))  # type: ignore[union-attr]
                await db.flush()

            app.dependency_overrides[get_db] = override_get_db
            try:
                with patch.object(notification_service, "get_email_provider", Recorder):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://verify", timeout=120
                    ) as client:
                        await _run_flow(client, check, sent)
            finally:
                app.dependency_overrides.pop(get_db, None)
        await connection.rollback()
    print("\nAll e2e data rolled back (nothing persisted).")
    return ok


async def _run_flow(client: Any, check: Any, sent: list[dict[str, Any]]) -> None:
    async def login(email: str, password: str) -> dict[str, str]:
        r = await client.post("/api/v1/recruiter/auth/login", json={"email": email, "password": password})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    su = await login("verify.ai.superadmin@example.com", "VerifyAiPass123")
    slug = "verify-ai-demo"
    org = await client.post(
        "/api/v1/admin/organizations",
        json={
            "name": "Verify AI Demo Org",
            "slug": slug,
            "admin_email": "hr.admin@verify-ai.example.com",
            "admin_password": "VerifyAdminPass1",
            "admin_full_name": "Demo HR Admin",
        },
        headers=su,
    )
    await client.patch(
        f"/api/v1/admin/organizations/{org.json()['id']}",
        json={"careers_contact_email": "careers@verify-ai.example.com"},
        headers=su,
    )
    hr = await login("hr.admin@verify-ai.example.com", "VerifyAdminPass1")
    job = (
        await client.post(
            "/api/v1/recruiter/jobs",
            json={
                "title": demo_data.DEMO_JOB_TITLE,
                "department": demo_data.DEMO_JOB_DEPARTMENT,
                "location": demo_data.DEMO_JOB_LOCATION,
                "employment_type": demo_data.DEMO_JOB_EMPLOYMENT_TYPE,
                "description": demo_data.DEMO_JOB_DESCRIPTION,
            },
            headers=hr,
        )
    ).json()
    await client.patch(f"/api/v1/recruiter/jobs/{job['id']}", json={"status": "OPEN"}, headers=hr)

    phones = {"match": "+919812300001", "not_match": "+919812300002", "partial": "+919812300003"}
    outcomes: dict[str, dict[str, Any]] = {}
    for key, resume in RESUMES.items():
        email = f"{key}.demo@verify-ai.example.com"
        before = len(sent)
        await client.post(
            f"/api/v1/public/organizations/{slug}/email-verification/request", json={"email": email}
        )
        code = re.search(r"verification code: (\d{6})", sent[before]["subject"]).group(1)  # type: ignore[union-attr]
        token = (
            await client.post(
                f"/api/v1/public/organizations/{slug}/email-verification/verify",
                json={"email": email, "code": code},
            )
        ).json()["verification_token"]
        form = {
            "full_name": resume["name"],
            "email": email,
            "email_verification_token": token,
            "phone": phones[key],
            "date_of_birth": "1998-01-15",
            "place_of_birth": "Chennai",
            "languages": ["English", "Tamil"],
            "candidate_type": "EXPERIENCED",
            "years_experience": "3",
            "notice_period_days": "30",
            "current_title": "Engineer",
            "current_company": "Demo Company",
            "current_location": "Chennai",
            "preferred_location": "Chennai",
            "qualification": "Bachelor's degree",
            "linkedin_url": f"https://www.linkedin.com/in/{key}-demo",
            "github_url": f"https://github.com/{key}-demo",
        }
        emails_before_apply = len(sent)
        response = await client.post(
            f"/api/v1/public/organizations/{slug}/jobs/{job['id']}/apply",
            data=form,
            files={"resume": (f"{key}.pdf", _resume_pdf(key), "application/pdf")},
        )
        body = response.json()
        outcomes[key] = body
        welcome = len(sent) > emails_before_apply
        print(
            f"\n{resume['name']} ({key}): HTTP {response.status_code} outcome={body.get('outcome')} "
            f"welcome_email_sent={welcome} confirmation_email_sent={body.get('confirmation_email_sent')}"
        )
        check(f"{key}: application created", response.status_code == 201, response.text[:200])
        check(f"{key}: no internal AI data in candidate response", "decision" not in body and "summary" not in body)

    check("match -> RECEIVED", outcomes["match"].get("outcome") == "RECEIVED")
    check("not_match -> NOT_SHORTLISTED_FOR_ROLE", outcomes["not_match"].get("outcome") == "NOT_SHORTLISTED_FOR_ROLE")

    apps = (await client.get("/api/v1/recruiter/applications", headers=hr)).json()
    by_name = {a["candidate_full_name"]: a for a in apps}
    screened_out = by_name[RESUMES["not_match"]["name"]]
    check("HR sees the screened-out candidate", screened_out["status"] == "AI_SCREENED_OUT")
    runs = (
        await client.get(f"/api/v1/recruiter/applications/{screened_out['id']}/screening", headers=hr)
    ).json()
    print(f"    stored evidence: missing={runs[0]['missing_requirements'][:5]} model={runs[0]['model']}")
    check("screening evidence stored", runs[0]["decision"] == "NOT_MATCH" and runs[0]["missing_requirements"])

    override = await client.post(
        f"/api/v1/recruiter/applications/{screened_out['id']}/ai-override",
        json={"reason": "Verification script: HR override check."},
        headers=hr,
    )
    check("HR override -> UNDER_REVIEW", override.json().get("status") == "UNDER_REVIEW")

    job_b = (
        await client.post(
            "/api/v1/recruiter/jobs",
            json={"title": "Accounts Executive (Demo)", "description": "Tally, GST, Excel, 3+ years."},
            headers=hr,
        )
    ).json()
    matched = await client.post(
        f"/api/v1/recruiter/candidates/{screened_out['candidate_id']}/job-matches",
        json={"job_id": job_b["id"], "reason": "Verification script: HR match check."},
        headers=hr,
    )
    check("HR match to another job", matched.status_code == 201 and matched.json()["source"] == "HR_MATCH")
    history = (
        await client.get(f"/api/v1/recruiter/candidates/{screened_out['candidate_id']}/history", headers=hr)
    ).json()
    check("history keeps original + HR match", len(history["applications"]) == 2)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e2e", action="store_true", help="also run the full rolled-back HTTP flow")
    args = parser.parse_args()
    ok = await provider_check()
    if args.e2e:
        print("=" * 72 + "\nEnd-to-end HTTP flow (rolled back)\n" + "=" * 72)
        ok = await e2e_check() and ok
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

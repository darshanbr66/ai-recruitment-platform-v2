"""Public, visitor-safe knowledge about SIGVITAS and how its hiring works.

Every statement here mirrors what the public site and the shipped product
actually do (landing page copy, the application form, the assessment consent
screen, docs/). It is written for a language model to ground on, so it states
limits plainly — where the platform publishes nothing (e.g. a contact channel,
company history), the entry says so rather than leaving a gap for the model to
fill.

Keep this file public-safe: no internal architecture, administration, tenant
or personal data. Update it in the same change that alters the behaviour it
describes (CLAUDE.md § 7).
"""

from app.knowledge.base import KnowledgeEntry


def _kw(words: str) -> frozenset[str]:
    return frozenset(words.split())


SIGVITAS_PUBLIC_KNOWLEDGE: tuple[KnowledgeEntry, ...] = (
    KnowledgeEntry(
        id="about-sigvitas",
        title="About SIGVITAS",
        content=(
            "SIGVITAS is a recruitment platform. This site is SIGVITAS' careers site, where "
            "visitors can explore open roles and campus opportunities and apply in minutes "
            "without creating an account. AI helps SIGVITAS recruiters review applications, "
            "and a person always makes the hiring decision. Roles span areas such as "
            "engineering and design; the current openings list is the source of truth for what "
            "is hiring now. The site does not publish further company details (history, size, "
            "offices, leadership), so those are not available here."
        ),
        keywords=_kw(
            "sigvitas sigvi company platform organization organisation "
            "recruitment careers site mission offices founded history"
        ),
        url="/",
    ),
    KnowledgeEntry(
        id="hiring-process",
        title="The hiring process",
        content=(
            "The path is the same whether someone applies directly or through a campus drive: "
            "1) Explore openings. 2) Apply by submitting the application and resume - no "
            "account required. 3) Resume review - the team reviews the candidate's background "
            "against the role. 4) Screening - an initial pass that is assisted by AI and always "
            "reviewed by a recruiter. 5) Assessment - some roles include a short skills "
            "assessment before the next round. 6) Interview - meet the team and talk through "
            "the role in more depth. 7) Decision - SIGVITAS follows up either way, as soon as "
            "it can. Timelines are not published; no specific turnaround time is promised."
        ),
        keywords=_kw(
            "process hiring recruitment steps stages workflow pipeline path timeline rounds"
        ),
        url="/#process",
    ),
    KnowledgeEntry(
        id="how-to-apply",
        title="How to apply for a job",
        content=(
            "To apply: open the careers page (/org/sigvitas), choose a role, and use the "
            "'Apply for this role' button, which leads to the application form at the bottom of "
            "the role page. No account or login is needed. When the form is submitted, the page "
            "confirms the application has been received and that the team will be in touch. "
            "Applications are made per role."
        ),
        keywords=_kw(
            "apply applying applied application applications submit register account signup "
            "login portal"
        ),
        url="/org/sigvitas",
    ),
    KnowledgeEntry(
        id="application-requirements",
        title="What information is required when applying",
        content=(
            "Required: full name, email, whether you are a Fresher (no professional experience "
            "yet) or an Experienced professional, and a resume file (PDF, DOC or DOCX, up to "
            "10 MB). Experienced applicants also give total years of experience and notice "
            "period in days (or mark themselves an immediate joiner). Optional: phone, current "
            "title and company (experienced), current and preferred location, qualification, "
            "and LinkedIn and GitHub links. The email address is used to keep one profile per "
            "person, so use the same one each time."
        ),
        keywords=_kw(
            "information fields form upload pdf docx size notice period linkedin github "
            "qualification documents mandatory"
        ),
        url="/org/sigvitas",
    ),
    KnowledgeEntry(
        id="after-you-apply",
        title="What happens after you apply",
        content=(
            "After applying, the page shows a confirmation that the application was received. "
            "The recruitment team then reviews the resume against the role. If the profile is a "
            "fit it moves on through screening (AI-assisted, always reviewed by a recruiter), an "
            "optional assessment for some roles, an interview and a decision. Follow-ups from "
            "the recruitment team, such as an assessment invitation or interview details, are "
            "sent by email, so it helps to check the inbox (and spam folder) for the address "
            "used on the application. There is no candidate login or online status tracker at "
            "the moment."
        ),
        keywords=_kw(
            "after happens next status track follow response reply hear wait confirmation "
            "received notified outcome"
        ),
        url="/#process",
    ),
    KnowledgeEntry(
        id="assessments",
        title="How assessments work",
        content=(
            "Some roles include a short skills assessment. Candidates receive a personal "
            "invitation link (no login needed); the link is for one attempt and has an expiry "
            "date. The assessment is made of multiple-choice questions (single or multiple "
            "correct answers) and shows its duration and instructions before starting. Before "
            "starting, the candidate reads and must agree to a 'Before You Begin' notice about "
            "browser-based monitoring: the team may see timestamped events such as switching "
            "tabs or windows, exiting fullscreen, camera/microphone becoming unavailable or "
            "changing, and internet interruptions. SIGVITAS does not record or store audio or "
            "video. After submitting, the candidate sees a confirmation but no score; the "
            "recruitment team reviews the result and contacts the candidate about the next step."
        ),
        keywords=_kw(
            "assessment assessments test tests exam quiz mcq invitation invite "
            "monitoring proctoring camera microphone webcam duration score attempt retest"
        ),
        url="/#process",
    ),
    KnowledgeEntry(
        id="campus-drives",
        title="Campus drives (campus hiring)",
        content=(
            "A campus drive is a hiring drive SIGVITAS runs with a college. Campus hiring "
            "follows the same review and assessment process as any other application. If a "
            "college is running a drive, the placement office shares a direct application link "
            "- no account needed - where the student gives name, email, phone (optional) and a "
            "resume. Only open drives accept applications; if a drive has closed, the link says "
            "so. Some drives include an assessment, which may be offered right after applying. "
            "Drive links are private to each drive, so there is no public list of drives; "
            "watch for the link from the college placement office or check the site for "
            "upcoming opportunities."
        ),
        keywords=_kw(
            "campus drive drives college university student students placement fresher freshers "
            "graduate graduates batch mass"
        ),
        url="/#campus",
    ),
    KnowledgeEntry(
        id="ai-in-hiring",
        title="How AI is used in hiring at SIGVITAS",
        content=(
            "AI assists SIGVITAS recruiters; it never decides. It surfaces signal for a "
            "recruiter to review during screening, every screening result stays traceable back "
            "to the application it belongs to, and a recruiter always makes the call. If an "
            "assessment uses monitoring, the candidate is told before starting."
        ),
        keywords=_kw(
            "ai artificial intelligence automated automatic screening bias human "
            "fair algorithm machine"
        ),
        url="/#ai",
    ),
    KnowledgeEntry(
        id="contact",
        title="Contacting the recruitment team",
        content=(
            "No public contact details (email address, phone number or contact form) are "
            "published on this site, so none can be given here - and none should be guessed. "
            "The recruitment team contacts applicants by email once there is an update, so "
            "the best route is to reply to an email received from the team. Applications "
            "themselves are submitted through the role page."
        ),
        keywords=_kw("contact reach phone support address office enquiry inquiry"),
        url="/org/sigvitas",
    ),
    KnowledgeEntry(
        id="about-sigvi",
        title="About Sigvi, the assistant",
        content=(
            "Sigvi is an AI assistant on the SIGVITAS careers site. It can explain the "
            "platform and hiring process, point to current public openings, and answer general "
            "career questions. It cannot look up an individual application or its status, "
            "cannot apply on someone's behalf, and does not make hiring decisions or "
            "recommendations about candidates. Its answers are AI-generated and can contain "
            "mistakes; please avoid sharing sensitive personal information in the chat."
        ),
        keywords=_kw("sigvi assistant chatbot bot chat privacy"),
        url=None,
    ),
)

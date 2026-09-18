# Recruitment Workflow

**Implementation status:** The `Application` status model below (§ 2) is
implemented exactly as specified, in `backend/app/workflows/
application_workflow.py`, and is what actually gates every status change in
the app (recruiter-triggered and assessment-triggered alike — see
`app/services/assessment_public_service.py`). `AssessmentInvitation.status`
is a separate, simpler enum (`SENT/STARTED/SUBMITTED/EXPIRED/CANCELLED`)
with its transitions handled directly in `app/services/assessment_service.py`
and `assessment_public_service.py`, not by a dedicated
`invitation_workflow.py` module (that split wasn't warranted at this size —
see `app/models/assessment.py`'s docstring for the full list of
simplifications from the original assessment design). § 5 ("Candidate
portal flow") describes a self-service candidate account that does not
exist yet — see `docs/ai-screening.md`/`docs/assessment.md`/
`docs/campus-hiring.md` implementation-status notes for what candidates
actually get today (an anonymous public apply flow and token-based
assessment links, no login).

## 1. Why a workflow module, not scattered status checks

`Application.status` is a finite-state value with rules about which
transitions are legal and who/what can trigger them. Per `CLAUDE.md` § 2
("Workflow state != ad hoc strings"), these rules live in one place:

- `backend/app/workflows/application_workflow.py`

It defines an explicit transition table (`{current_status: {allowed_next
statuses}}`) and a single `transition(application, to_status, actor, reason)`
function that: validates the transition is legal, writes the new status,
and appends an `ApplicationStatusHistory` row — so no call site can move an
application into an invalid state or skip the history write.

## 2. Application status model

```
APPLIED
  → UNDER_REVIEW
  → REJECTED

UNDER_REVIEW
  → SCREENING
  → REJECTED

SCREENING
  → ASSESSMENT_INVITED       (if an assessment is required for this pipeline)
  → SHORTLISTED              (if no assessment required)
  → REJECTED

ASSESSMENT_INVITED
  → ASSESSMENT_STARTED
  → REJECTED                 (e.g. invitation expired without action — recruiter decision, not automatic)

ASSESSMENT_STARTED
  → ASSESSMENT_COMPLETED
  → REJECTED

ASSESSMENT_COMPLETED
  → SHORTLISTED
  → REJECTED

SHORTLISTED
  → INTERVIEW
  → REJECTED

INTERVIEW
  → SELECTED
  → REJECTED

SELECTED
  → HIRED

REJECTED, HIRED   (terminal)
```

Notes:

- `ASSESSMENT_STARTED`/`ASSESSMENT_COMPLETED` are driven by the assessment
  domain (see `docs/assessment.md`) calling into the workflow module when an
  invitation's `CandidateAttempt` starts/submits — the application workflow
  does not know about assessment internals, it only receives a
  transition request.
- Interview scheduling/feedback is out of scope for the initial phases
  (tracked as a future domain); `INTERVIEW` is a status the recruiter moves
  an application into/out of manually for now.
- `REJECTED`/`HIRED` are terminal — no code path transitions out of them. A
  mis-rejection is corrected by recruiter override (explicit, audited,
  permission-gated), not by "un-terminal-izing" a state silently.
- **`WITHDRAWN` was removed (SIGVITAS platform overhaul):** the platform no
  longer distinguishes a candidate-initiated withdrawal from a recruiter
  rejection — every prior `WITHDRAWN` application became `REJECTED`, and the
  value no longer exists in the enum (application code or database). `HIRED`
  was added as the new outcome after `SELECTED`, matching the product's
  "Selected → Hired" flow.

## 3. Candidate-visible projection

Candidates never see the raw internal status enum value or history reasons.
The candidate API maps internal status to a small, stable public vocabulary:

| Internal status | Candidate sees |
|---|---|
| APPLIED, UNDER_REVIEW | "Application Submitted" |
| SCREENING | "Under Review" |
| ASSESSMENT_INVITED, ASSESSMENT_STARTED | "Assessment Pending" |
| ASSESSMENT_COMPLETED | "Assessment Completed" |
| SHORTLISTED | "Shortlisted" |
| INTERVIEW | "Interview" |
| SELECTED | "Selected" |
| REJECTED | "Not Selected" |
| HIRED | "Hired" |

This mapping lives in the candidate-facing schema/serializer, not in the
workflow module itself — the workflow module's vocabulary is the operational
truth; the candidate projection is a presentation concern.

## 4. Normal recruitment flow

```
Job created → requirements defined → sourcing/candidate application →
resume upload → resume parsing (Phase 5) → AI-assisted screening (Phase 6) →
recruiter review → assessment (optional) → interview → decision → reports
```

Sourcing is not a distinct backend entity in the initial phases — it is a
recruiter-portal view over candidates/applications filtered by `source` and
by "not yet applied" status, plus manual candidate add. If sourcing grows
dedicated needs (outreach sequences, external sourcing integrations), it
becomes its own domain at that point rather than being speculatively modeled
now.

## 5. Candidate portal flow

```
Browse public jobs → job details → Apply → register/login → complete profile →
upload resume → submit application → view status → (assessment if invited) →
interview → final decision
```

The "Apply" action from a public job detail page, if the visitor isn't
authenticated, routes through candidate register/login and returns to
complete the application — the Job the candidate was applying to is
preserved across that redirect (client-side state), not silently dropped.

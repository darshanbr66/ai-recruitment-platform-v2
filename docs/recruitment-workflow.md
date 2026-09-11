# Recruitment Workflow

Status: Phase 0 design. Implemented starting Phase 3 (states/model) and
completed through Phase 9 (recruiter-side transitions/UI).

## 1. Why a workflow module, not scattered status checks

`Application.status` and `AssessmentInvitation.status` are both finite-state
values with rules about which transitions are legal and who/what can trigger
them. Per `CLAUDE.md` § 2 ("Workflow state != ad hoc strings"), these rules
live in one place per entity:

- `backend/app/workflows/application_workflow.py`
- `backend/app/workflows/invitation_workflow.py`

Each defines an explicit transition table (`{current_status: {allowed_next
statuses}}`) and a single `transition(application, to_status, actor, reason)`
function that: validates the transition is legal, writes the new status,
appends an `ApplicationStatusHistory` row, and emits the corresponding audit
log entry — so no call site can move an application into an invalid state or
skip the history/audit write.

## 2. Application status model

```
APPLIED
  → UNDER_REVIEW
  → WITHDRAWN                (candidate-initiated, any point before a terminal state)

UNDER_REVIEW
  → SCREENING
  → REJECTED
  → WITHDRAWN

SCREENING
  → ASSESSMENT_INVITED       (if an assessment is required for this pipeline)
  → SHORTLISTED              (if no assessment required)
  → REJECTED
  → WITHDRAWN

ASSESSMENT_INVITED
  → ASSESSMENT_STARTED
  → REJECTED                 (e.g. invitation expired without action — recruiter decision, not automatic)
  → WITHDRAWN

ASSESSMENT_STARTED
  → ASSESSMENT_COMPLETED
  → WITHDRAWN

ASSESSMENT_COMPLETED
  → SHORTLISTED
  → REJECTED

SHORTLISTED
  → INTERVIEW
  → REJECTED
  → WITHDRAWN

INTERVIEW
  → SELECTED
  → REJECTED
  → WITHDRAWN

SELECTED, REJECTED, WITHDRAWN   (terminal)
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
- `REJECTED`/`SELECTED`/`WITHDRAWN` are terminal — no code path transitions
  out of them. A mis-rejection is corrected by recruiter override
  (explicit, audited, permission-gated), not by "un-terminal-izing" a state
  silently.

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
| WITHDRAWN | "Withdrawn" |

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

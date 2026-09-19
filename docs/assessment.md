# Assessment Platform

**Implementation status:** MCQ assessments are implemented end-to-end —
recruiter builds an assessment with single/multi-select questions
(`app/models/assessment.py`), invites a candidate from the application
detail page (only legal while the application is in `SCREENING`, per
`docs/recruitment-workflow.md`), and the candidate answers via an opaque
token link with no login (`app/api/v1/public/assessments.py`), auto-scored
on submit. Real simplifications from the design below, noted in
`app/models/assessment.py`'s docstring: no `AssessmentEvaluation` as a
separate row (the scoring process and its result are one `AssessmentResult`
row), no `DELIVERED`/`OPENED` webhook states, no `max_attempts` bound (one
attempt per invitation), and email is manual — assigning an assessment
only *prepares* the invitation (the link is also returned once in the
recruiter's API response so it can be copied manually, see
`app/api/v1/recruiter/assessments.py`); the recruiter emails it explicitly
with "Send Assessment Invitation" (see § 8).

## 0. Assessment monitoring ("proctoring") — SIGVITAS platform overhaul

Transparent, browser-based monitoring, not hidden surveillance. Before
starting an attempt, the candidate sees a "Before You Begin" screen
(`frontend/src/features/careers/MonitoringConsentScreen.tsx`) listing
exactly what's monitored and must explicitly check "I understand and
agree" before the "Start Assessment" button is enabled. Only what is
actually implemented is disclosed — nothing is claimed that the browser
can't reliably detect.

**Implemented events** (`app/models/assessment.py::MonitoringEventType`,
persisted to `assessment_monitoring_events`, recorded via
`POST /api/v1/public/assessment/{token}/events` while the attempt is
`STARTED`): `MONITORING_CONSENT_GIVEN`, `TAB_SWITCH`, `WINDOW_BLUR`,
`WINDOW_FOCUS`, `FULLSCREEN_EXIT`, `CAMERA_PERMISSION_CHANGED`,
`MICROPHONE_PERMISSION_CHANGED`, `CAMERA_DEVICE_CHANGED`,
`MICROPHONE_DEVICE_CHANGED`, `CAMERA_UNAVAILABLE`,
`MICROPHONE_UNAVAILABLE`, `CONNECTION_INTERRUPTED`,
`CONNECTION_RESTORED`. The frontend listener
(`frontend/src/features/careers/useProctoring.ts`) batches events and
flushes every ~4 seconds — a failed/dropped flush never blocks or fails the
candidate's attempt.

**No raw audio/video is ever captured or stored.** On accepting the consent
screen, the browser is asked for camera/microphone permission purely to
detect whether they're available (`getUserMedia`, then every track is
immediately stopped) — no stream is displayed, transmitted, or persisted.
This is a deliberate scope boundary (CLAUDE.md: "do not store raw
audio/video unless there is a clearly defined, secure requirement and
architecture for it" — there isn't one here).

**Documented limitations** (do not oversell these to candidates or
recruiters):
- `navigator.mediaDevices.ondevicechange` fires on device add/remove, not
  on a live, mid-session *permission* revocation in every browser — some
  browsers don't surface that at all to page script.
- `Permissions.query({name: "camera"})`/`"microphone"` isn't supported in
  every browser; where unsupported, permission state is only inferred from
  the initial `getUserMedia` call's success/failure, not live-tracked.
- `visibilitychange`/`blur`/`focus` are reliable across modern browsers but
  can't distinguish *why* focus was lost (another app, OS notification,
  devtools) — the event only records that it happened.
- Fullscreen monitoring only fires if the assessment UI actually requested
  fullscreen; this build does not force fullscreen, so `FULLSCREEN_EXIT`
  only fires for candidates who opted into fullscreen themselves.

**Candidate-facing result never includes a score.** Submission returns only
an acknowledgement (`PublicSubmissionResult`, just `submitted_at`) — the
candidate sees a polished "Assessment Submitted" confirmation
(`frontend/src/features/careers/SubmissionSuccess.tsx`), never a
percentage. Recruiters/admins see the full score via the existing,
separate `AssessmentResultResponse` and the events above via "Assessment
Activity" on the application detail page — both permission-gated by the
existing `assessment.read` permission, and both described to recruiters in
neutral, non-accusatory language (an event is something *observed*, never
an automatic accusation of misconduct).

## 1. Design goal

Assessments are a reusable domain, independent of *why* a candidate was
invited (normal recruitment or campus drive) and, longer-term, independent
of *what kind* of question is being asked (MCQ now; aptitude, technical,
coding, subjective/AI-evaluated later). The initial build only implements
MCQ (single and multi-select), but the schema's `type` discriminator on
`Question` and `evaluator_type` on `AssessmentEvaluation` exist specifically
so those future types are additive, not a redesign.

## 2. Entities and their responsibilities

```
Assessment            -- org-owned definition: title, instructions, duration, pass score
  └─ Question          -- belongs to one Assessment; type, prompt, points, order
       └─ QuestionOption   -- MCQ choices, is_correct flag (never sent to the candidate)

AssessmentInvitation   -- the secure, single-purpose link from ONE Application
                          to ONE Assessment
  └─ CandidateAttempt      -- one attempt at answering (bounded by max_attempts)
       └─ CandidateAnswer[]    -- one row per question answered
       └─ AssessmentEvaluation -- HOW it was scored (auto/AI/manual), when, by what
       └─ AssessmentResult     -- the durable scored outcome (score, pass/fail)
```

`AssessmentEvaluation` and `AssessmentResult` are deliberately separate
(mirroring the AI screening domain's Run/Result split in
`docs/ai-screening.md`): `AssessmentEvaluation` is the record of the scoring
*process* (useful once AI-evaluated subjective answers exist and evaluation
might be re-run or reviewed), `AssessmentResult` is the *current* scored
outcome a recruiter/candidate actually reads.

Questions belong directly to one `Assessment` (no shared question-bank
abstraction) — the spec does not call for cross-assessment question reuse,
and adding that layer now would be exactly the kind of premature abstraction
`CLAUDE.md` § 5 rules out. If reuse becomes a real need, introducing a
question bank later is additive (a new table + a nullable
`source_question_id` on `Question`), not a breaking change.

## 3. Invitation lifecycle

States (from `docs/database.md` § 3.7):

```
NOT_SENT → SENT → [DELIVERED] → [OPENED] → STARTED → SUBMITTED
                                                    ↘ EXPIRED (if not started/submitted in time)
   → CANCELLED (recruiter action, any point before SUBMITTED)
```

`DELIVERED`/`OPENED` are populated only where the email provider supports
delivery/open webhooks — their absence never blocks progression to
`STARTED`/`SUBMITTED`, which are derived from the candidate's own actions
against `/api/v1/assessment/invitations/{token}/start` and `.../submit`.

Creating an invitation is always an explicit recruiter action (single or
bulk — see `docs/campus-hiring.md` § 3); it is never a side effect of adding
or importing a candidate.

## 4. Secure access mechanics

- Token: high-entropy random value, shown once (in the email), never
  persisted in plaintext. The DB stores `sha256(token)` only.
- Lookup path (`GET /api/v1/assessment/invitations/{token}`) hashes the
  incoming token and looks up `assessment_invitations.token_hash` — no
  candidate/assessment ID is trusted from the URL.
- Expired/cancelled/exhausted-attempts tokens return a generic
  "this invitation is no longer valid" response — never a detailed reason
  that could help an attacker distinguish "expired" from "wrong token" from
  "already submitted."
- Taking an assessment does **not** require a Candidate portal login —
  possession of the token is the authorization. This is required because
  campus-imported candidates may never register a portal account. A
  candidate who *does* have a portal account can still see the same
  invitation surfaced in "My Applications," but clicking through still uses
  the token link, not their session.
- Every lifecycle transition is audit-logged with the invitation `id` (never
  the token value) and actor context (system/candidate-via-token/recruiter).

## 5. Attempt & answer capture

- `CandidateAttempt.status = IN_PROGRESS` is created on `/start`; answers are
  captured incrementally via `/answers` (so a connectivity drop doesn't lose
  earlier answers), and `/submit` finalizes it (`status = SUBMITTED`,
  `submitted_at` set).
- `max_attempts` on the invitation bounds how many `CandidateAttempt` rows
  can exist for it; a new attempt beyond that limit is rejected.
- Server-side duration enforcement: `submitted_at - started_at` checked
  against `Assessment.duration_minutes` at evaluation time (not solely
  trusted from client-side timers) — a submission arriving after the
  server-computed deadline is flagged, not silently accepted as on-time.

## 6. Evaluation (initial: MCQ auto-scoring)

For each `CandidateAnswer` on an MCQ question, correctness is computed by
comparing `selected_option_ids` against the `QuestionOption.is_correct` set;
`score_awarded` follows `Question.points`. `AssessmentEvaluation
(evaluator_type=AUTO)` and `AssessmentResult` (aggregate score, percentage,
pass/fail against `Assessment.pass_score`) are written immediately on
submission — no manual step required for MCQ-only assessments. This is the
extension point where a future `evaluator_type=AI` path (for subjective/
coding answers) plugs in without changing the `AssessmentResult` shape
downstream consumers (reports, application workflow) already read.

## 7. Interaction with the application workflow

Invitation/attempt events call into `application_workflow.transition(...)`
(see `docs/recruitment-workflow.md`) rather than the assessment domain
writing to `Application.status` directly:

- Invitation assigned/prepared → `Application.status = ASSESSMENT_INVITED`
  (independent of whether the invitation has been emailed yet)
- Attempt started → `Application.status = ASSESSMENT_STARTED`
- Attempt submitted + evaluated → `Application.status = ASSESSMENT_COMPLETED`

This keeps the "who is allowed to move an application into which state"
rule in one place, even though the trigger originates in a different domain.

## 8. Email integration

Invitation email is **manual only**. Assigning an assessment
(`POST /recruiter/assessments/invite`) or authorizing a retest creates the
invitation and moves the application to `ASSESSMENT_INVITED`, but sends
nothing; `assessment_invitations.emailed_at` stays `NULL` ("Not emailed yet").

The recruiter then clicks **Send Assessment Invitation** on the application,
which opens the composer with the `ASSESSMENT_INVITATION` template
(`app/services/email_composer.py`): assessment name, deadline (the
invitation's expiry) and the candidate/job/company details are filled in, the
recruiter may edit the text, previews it, and sends. Because only
`sha256(token)` is stored, the raw link cannot be recovered later — so the
*send* issues a fresh personal link (the "Start the assessment" button), and
it replaces the previous token only if delivery succeeds. A failed send leaves
the existing link working. Only an invitation that is still `SENT` (not
started, submitted or expired) can be emailed. Delivery goes through the
`EmailProvider` interface; services never import a provider SDK directly
(`CLAUDE.md` § 2).

## 9. Importing questions from a file

`POST /api/v1/recruiter/assessments/parse-questions` (multipart file
upload) extracts candidate questions from a PDF, DOCX, XLSX, or CSV file
and returns them shaped exactly like `AssessmentCreateRequest.questions` —
**nothing is persisted by this endpoint.** The frontend shows the result as
an editable preview (select which questions to keep, edit/delete/reorder,
add more by hand) and only calls the existing
`POST /api/v1/recruiter/assessments` once the recruiter clicks "Create
assessment," so import and manual entry share one persistence path.

Parsing (`app/integrations/documents/question_import.py`) is deliberately
**rule-based, not AI** — free/local/open-source libraries only (`pypdf`,
`python-docx`, `openpyxl`, stdlib `csv`), consistent with "no paid API
dependency for convenience." It never guesses at a correct answer it can't
find explicitly in the document: a row/question with no resolvable correct
option is skipped and surfaced as a warning, not silently included with a
fabricated answer.

- **CSV/XLSX**: a header row with a `question` column, `option_1`/
  `option_2`/… (or `a`/`b`/`c`/…) columns, and a `correct` column naming the
  right option(s) by 1-based index, letter, or exact text — comma-separated
  for multi-select. Optional `type` and `points` columns.
- **PDF/DOCX**: numbered questions ("1. ...") with lettered options
  ("A) ..."), where the correct option is marked either with a trailing `*`
  or an explicit `Answer: B` / `Correct: B, C` line.

Malformed files (wrong type, missing required columns/structure) raise a
clear `QuestionImportError` rather than returning empty or guessed data.

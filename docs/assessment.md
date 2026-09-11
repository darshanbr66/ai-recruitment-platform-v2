# Assessment Platform

Status: Phase 0 design. Implemented in Phase 7, reused (not re-implemented)
by campus hiring in Phase 8.

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

- Invitation sent → `Application.status = ASSESSMENT_INVITED`
- Attempt started → `Application.status = ASSESSMENT_STARTED`
- Attempt submitted + evaluated → `Application.status = ASSESSMENT_COMPLETED`

This keeps the "who is allowed to move an application into which state"
rule in one place, even though the trigger originates in a different domain.

## 8. Email integration

The invitation email is sent through the Notification Service (see
`docs/architecture.md` § notification module) — the assessment service calls
`notification_service.send_assessment_invitation(invitation)`, which resolves
a template and hands off to whatever `EmailProvider` is configured. The
assessment/campus/recruitment services never import an email provider SDK
directly (`CLAUDE.md` § 2).

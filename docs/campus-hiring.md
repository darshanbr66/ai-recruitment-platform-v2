# Campus / Mass Hiring

Status: Phase 0 design. Implemented in Phase 8, reusing the Application and
Assessment domains built in earlier phases.

## 1. Model

```
CampusDrive
  organization_id
  job_id                  -- the opportunity being hired for
  college_id              -- which institution
  batch_year
  eligibility_criteria    -- jsonb (e.g. min CGPA, allowed branches — structured
                             enough to filter on, flexible enough not to need a
                             schema change per new criterion type)
  default_assessment_id   -- optional; recruiter can still send a different
                             assessment per invitation if needed
  start_date / end_date
  candidate_limit         -- optional cap
  status                  -- PLANNED / ACTIVE / CLOSED / CANCELLED
```

A `CampusDrive` does not duplicate anything `Job` or `Assessment` already
model — it composes them with campus-specific scheduling/eligibility
metadata.

## 2. Candidates in a drive

There is deliberately **no** separate "drive membership" or
"drive candidate" table. A candidate's participation in a drive is an
`Application` row:

```
Application {
  candidate_id
  job_id = campus_drive.job_id
  campus_drive_id = campus_drive.id
  source = CAMPUS_IMPORT | PORTAL | RECRUITER_ADDED
  status = APPLIED (initial, regardless of how the candidate entered)
}
```

Reasons this is not a separate entity: `Application` already models
"this candidate, this opportunity, current workflow state" — introducing a
parallel `DriveCandidate` table would mean every downstream step (screening,
assessment invitation, status reporting) would have to reconcile two
records for the same relationship. Per `CLAUDE.md` § 2, Candidate/Application
modeling rules apply identically inside campus hiring — no special case.

Candidates can enter a drive via:

- **Recruiter import** (bulk, e.g. CSV) → creates `Candidate` rows (if not
  already existing for that org/email) + `Application` rows with
  `source=CAMPUS_IMPORT`.
- **Manual add** (one at a time) → same, single record.
- **Public portal association** → a candidate who applies through the
  career portal to a job that happens to be attached to an active drive gets
  `campus_drive_id` set automatically on their `Application`.

**Import/add never sends an assessment invitation.** Creating the
`Application` only ever results in `status=APPLIED`. Sending an invitation
is always a distinct, explicit recruiter action — this is a hard requirement,
not a default-off setting.

## 3. Sending assessment invitations

```
Recruiter reviews applications for a drive (Application Review, filtered by campus_drive_id)
  → selects one or many eligible applications
  → "Send Assessment Invitation" (single or bulk)
    → for each selected application: create AssessmentInvitation
      (assessment_id = chosen assessment, application_id = the application,
       status=NOT_SENT → generate token → send email → status=SENT)
    → Application.status transitions APPLIED/UNDER_REVIEW/SCREENING → ASSESSMENT_INVITED
```

Bulk send is a loop over the same single-invitation service call (not a
separate code path) so behavior (audit logging, email templating, failure
handling per recipient) is identical whether sent one at a time or in bulk.
A partial failure (e.g. one bad email address) does not roll back the
successful sends — each invitation's outcome is independent and reported
back to the recruiter per-recipient.

Resend uses the same `AssessmentInvitation` row (new token generated,
`expires_at` refreshed) if the invitation hasn't been submitted; a fresh
`AssessmentInvitation` row is not created for a resend, so invitation history
stays attributable to one link's lifecycle. (If a candidate needs an entirely
new attempt after submission, that is a recruiter decision handled as an
explicit "issue new invitation," which is a new row, not a resend.)

## 4. Downstream flow

Once submitted, the assessment domain (`docs/assessment.md`) evaluates the
attempt, writes `AssessmentResult`, and the application workflow moves the
`Application` to `ASSESSMENT_COMPLETED`. From there, campus applications flow
through the same `SHORTLISTED → INTERVIEW → SELECTED/REJECTED` states as any
other application — there is no separate "campus status" vocabulary.

## 5. Campus reporting

Because campus participation is just `Application.campus_drive_id`, campus
reports (drive-wise, college-wise, batch-wise funnel/conversion) are the same
reporting service as general recruitment reports, filtered/grouped by
`campus_drive_id` / `college_id` / `batch_year` — not a separate reporting
subsystem (see `docs/database.md` § 3.10 and the Reporting module in
`docs/architecture.md` § 10).

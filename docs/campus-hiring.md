# Campus / Mass Hiring

**Implementation status:** `CampusDrive` (`app/models/campus_drive.py`)
composes an existing `Job` (or creates one inline), and participation is
exactly `Application.campus_drive_id` with no separate membership table,
per § 2 below. Each drive has its own public, no-login application link
(§ 3). Campus reporting (§ 5) is real, computed from live data — both the
per-drive funnel endpoint and the reports overview breakdown.

Not implemented: `eligibility_criteria` (jsonb filtering), `candidate_limit`
enforcement, and recruiter-side bulk/CSV candidate import — candidates
currently enter a drive only via its public application link, the general
career portal (if attached to the same job), or the one-at-a-time
candidate/application creation endpoints.

## 1. Model

```
CampusDrive
  organization_id
  job_id                  -- the opportunity being hired for (existing job,
                             or one created inline at drive-creation time —
                             see "job source" below)
  college_name
  description
  batch_year / start_date / end_date / registration_deadline
  default_assessment_id   -- optional; if set, a candidate who applies is
                             automatically invited to it
  link_token_hash         -- SHA-256 hash of the opaque public application
                             token; the raw token is only ever returned once,
                             by create/regenerate-link (same pattern as
                             assessment invitations, docs/assessment.md § 4)
  status                  -- DRAFT / ACTIVE / PAUSED / CLOSED
```

A `CampusDrive` does not duplicate anything `Job` or `Assessment` already
model — it composes them with campus-specific scheduling metadata.

**Job source.** Creating a drive takes either an existing `job_id`, or
`new_job_title` + `new_job_description` to create the job inline in the
same request (`app/services/campus_drive_service.py::_resolve_job_id`) —
never both, never neither. This avoids the recruiter having to leave the
campus-drive flow to first create a job, without ever creating a duplicate
job behind the scenes.

**Status lifecycle** (`CAMPUS_DRIVE_TRANSITIONS` in
`app/models/campus_drive.py`, enforced server-side, not just hidden in the
UI):

```
DRAFT   --Activate-->  ACTIVE
ACTIVE  --Pause-->     PAUSED
ACTIVE  --Close-->     CLOSED
PAUSED  --Resume-->    ACTIVE
PAUSED  --Close-->     CLOSED
CLOSED  --Reopen-->    ACTIVE
```

A drive is never deleted by a status change — `Close` and `Reopen` are
just further transitions, so closed drives stay in the recruiter's history
and their applications remain intact. Only `ACTIVE` drives accept new
public applications (§ 3); `DRAFT` drives 404 on their public link so an
unfinished drive can't be applied to before it's ready.

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
  status = APPLIED (initial, regardless of how the candidate entered) —
           or fast-tracked straight to ASSESSMENT_INVITED if the drive has
           a default_assessment_id (see § 3)
}
```

Reasons this is not a separate entity: `Application` already models
"this candidate, this opportunity, current workflow state" — introducing a
parallel `DriveCandidate` table would mean every downstream step (screening,
assessment invitation, status reporting) would have to reconcile two
records for the same relationship. Per `CLAUDE.md` § 2, Candidate/Application
modeling rules apply identically inside campus hiring — no special case.

## 3. The public application link (no candidate login)

Each drive gets one shareable link, `https://<frontend>/campus-drive/<token>`
(`app/api/v1/public/campus_drives.py`, `app/services/public_campus_drive_service.py`).
Same opaque-bearer-token pattern as assessment invitations
(`docs/architecture.md` § 4): the raw token is shown to the recruiter once
(on create, or again via "Regenerate link," which invalidates the previous
one), only its SHA-256 hash is persisted.

```
GET  /api/v1/public/campus-drive/{token}         -- drive/job/college details, no auth
POST /api/v1/public/campus-drive/{token}/apply    -- name, email, phone, resume — no account
```

`apply` upserts the `Candidate` by (organization, email), creates the
`Application` with `source=CAMPUS_IMPORT`, saves the resume, and — only if
the drive has a `default_assessment_id` — fast-tracks the application
through `UNDER_REVIEW → SCREENING` and creates an `AssessmentInvitation`
immediately, returning its link in the response so the candidate can take
the assessment right after applying. If no assessment is attached, the
application simply stays at `APPLIED` for a recruiter to review.

**Import/add never sends an assessment invitation** unless the drive was
explicitly configured with one — this is a hard requirement, not a
default-off setting: a recruiter adding a candidate one at a time never
gets a surprise auto-invite.

## 4. Recruiter-side management

```
POST   /api/v1/recruiter/campus-drives                    -- create (§ 1 job source)
GET    /api/v1/recruiter/campus-drives                    -- list (org-scoped)
GET    /api/v1/recruiter/campus-drives/{id}                -- detail
PATCH  /api/v1/recruiter/campus-drives/{id}                -- edit fields and/or status
GET    /api/v1/recruiter/campus-drives/{id}/funnel          -- real counts, see § 5
POST   /api/v1/recruiter/campus-drives/{id}/regenerate-link -- invalidates the old link
```

## 5. Campus reporting

**Candidates in this drive** (drive detail page) reads the ordinary Applications
list with `campus_drive_id` — there is no drive-specific candidates API. It
supports server-side search (name, email, phone), a status filter,
qualification, and an applied-from/to range, with pagination, and the state is
kept in the page URL. The drive's own lifecycle (DRAFT / ACTIVE / PAUSED /
CLOSED) only governs the *public* apply link; a recruiter can always search a
drive's candidates, whatever its state.

Because campus participation is just `Application.campus_drive_id`, two
real (never hardcoded) views are available:

- **Per-drive funnel** (`GET /campus-drives/{id}/funnel`,
  `campus_drive_service.get_funnel_counts`): a `GROUP BY status` count over
  that drive's applications, keyed to the same `ApplicationStatus` values
  used everywhere else in the product — registered, screening,
  assessment_invited, assessment_completed, shortlisted, interview,
  selected, rejected, hired.
- **Cross-drive comparison** (`GET /api/v1/recruiter/reports/overview`,
  `campus_drives` field): total application count per drive, for the
  Reports page's "Campus drives" chart.

Downstream of `apply`, campus applications flow through the exact same
application workflow (`docs/recruitment-workflow.md`) as any other
application — there is no separate "campus status" vocabulary.

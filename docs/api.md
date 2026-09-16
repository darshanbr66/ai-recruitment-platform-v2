# API Architecture

Status: Implemented for the domains that exist (auth, admin/organizations,
recruiter jobs/candidates/applications/reports/screening/assessments/
campus-drives/notes, public career site + apply + assessment-taking). No
`/api/v1/candidate/*` audience exists yet — there is no candidate portal
login (see `docs/recruitment-workflow.md`'s implementation-status note).
The versioning/audience-partitioning convention below is exactly what's
implemented; the endpoint list further down predates several of the
domains actually built and was not kept in lockstep with every new route —
`GET /api/v1/*/openapi.json` (or `/docs`) is the authoritative live list.

## 1. Versioning & audience partitioning

All routes are under `/api/v1/`, further partitioned by audience so the
authorization requirement is visible from the URL:

```
/api/v1/public/...      anonymous
/api/v1/candidate/...   candidate JWT (audience="candidate")
/api/v1/assessment/...  invitation bearer token (not a login session)
/api/v1/recruiter/...   staff JWT (audience="user") + role/permission check
/api/v1/admin/...       staff JWT, SUPER_ADMIN only
```

A route handler never has to guess its own trust level — the prefix is the
contract, enforced by a FastAPI dependency attached at the router level for
each prefix (not per-endpoint, to avoid one endpoint being forgotten).

## 2. Representative endpoint surface (illustrative — finalized per-phase)

### Public
```
GET  /api/v1/public/organizations/{org_slug}/jobs
GET  /api/v1/public/organizations/{org_slug}/jobs/{job_id}
```
Only published (`status=OPEN`) jobs, minimal fields (title, department,
location, employment_type, description, requirements summary).

### Candidate
```
POST /api/v1/candidate/auth/register
POST /api/v1/candidate/auth/login
POST /api/v1/candidate/auth/refresh
POST /api/v1/candidate/auth/logout
GET  /api/v1/candidate/me
PATCH /api/v1/candidate/me
POST /api/v1/candidate/me/resume
GET  /api/v1/candidate/applications
POST /api/v1/candidate/jobs/{job_id}/apply
GET  /api/v1/candidate/applications/{application_id}
```
Application detail exposes a candidate-safe status view (current stage,
timestamps) — never raw internal `ApplicationStatusHistory.reason`,
recruiter notes, or AI evaluation evidence.

### Assessment (token-bearer, not session-based)
```
GET  /api/v1/assessment/invitations/{token}
POST /api/v1/assessment/invitations/{token}/start
POST /api/v1/assessment/invitations/{token}/answers
POST /api/v1/assessment/invitations/{token}/submit
```
`{token}` is the raw invitation token; the server looks it up by
`sha256(token)` against `assessment_invitations.token_hash`. See
`docs/assessment.md` and `docs/security.md` for the full token lifecycle.

### Recruiter
```
GET/POST      /api/v1/recruiter/jobs
GET/PATCH     /api/v1/recruiter/jobs/{job_id}
GET/POST      /api/v1/recruiter/candidates
GET/PATCH     /api/v1/recruiter/candidates/{candidate_id}
GET           /api/v1/recruiter/applications
GET/PATCH     /api/v1/recruiter/applications/{application_id}
POST          /api/v1/recruiter/applications/{application_id}/status
POST          /api/v1/recruiter/applications/{application_id}/screening-runs
GET           /api/v1/recruiter/applications/{application_id}/screening-runs
POST          /api/v1/recruiter/applications/{application_id}/notes
GET/POST      /api/v1/recruiter/assessments
GET/POST      /api/v1/recruiter/assessments/{assessment_id}/questions
POST          /api/v1/recruiter/applications/{application_id}/assessment-invitations
POST          /api/v1/recruiter/assessment-invitations/{invitation_id}/resend
GET/POST      /api/v1/recruiter/campus-drives
POST          /api/v1/recruiter/campus-drives/{drive_id}/candidates
POST          /api/v1/recruiter/campus-drives/{drive_id}/assessment-invitations:bulk
GET           /api/v1/recruiter/reports/funnel
GET           /api/v1/recruiter/reports/campus/{drive_id}
GET/POST      /api/v1/recruiter/users
```
All resolve `organization_id` from the authenticated principal — never from
a path/query/body parameter — and enforce the specific permission for the
action via a dependency (e.g. `require_permission("application.status.change")`).

### Admin
```
GET/POST /api/v1/admin/organizations
PATCH    /api/v1/admin/organizations/{org_id}
```

## 3. Conventions

- **Errors**: consistent envelope —
  `{"error": {"code": "...", "message": "...", "request_id": "..."}}` with
  the correct HTTP status. No internal exception messages or stack traces in
  the body; those go to structured logs keyed by `request_id`.
- **Pagination**: cursor or offset/limit (finalized in Phase 3 when the first
  list endpoints ship), consistent shape:
  `{"items": [...], "total": N, "next_cursor": "..."}`.
- **Validation**: every request/response is a Pydantic model; no raw `dict`
  bodies.
- **HTTP status codes**: `201` on resource creation, `204` on
  no-content-success (e.g. delete), `409` on conflict (e.g. duplicate
  application), `422` on validation error (FastAPI default), `403` vs `404`
  chosen deliberately for cross-tenant access attempts (see
  `docs/security.md` — default to `404` for resources outside the caller's
  tenant, to avoid confirming existence).
- **Idempotency**: bulk operations (e.g. bulk assessment invitation send)
  accept a client-supplied idempotency key to make retries safe.

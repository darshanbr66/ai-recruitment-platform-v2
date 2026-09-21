# Security Model

Status: Implemented — Argon2id password hashing, JWT access tokens, hashed
opaque refresh tokens with rotation/reuse detection, two-layer tenant
isolation (application-scoped queries + Postgres RLS, `app/db/rls.py`),
and hashed opaque tokens for assessment invitations (same pattern as
refresh tokens) all exist in code today, not just as a plan. This document
was the checklist that build was measured against; it has not been audited
end-to-end for a production/external deployment (see CLAUDE.md's "local
development demo" framing) — treat it as accurate for what's implemented,
not as a completed hardening sign-off.

## 1. Authentication

- **Password hashing: Argon2id** (`argon2-cffi`), never bcrypt for this
  project. Parameters (memory cost, iterations, parallelism) chosen per
  OWASP current guidance and set in `core/security.py`, not hardcoded inline
  at each call site.
- Two independent principal types — **User** (staff) and **Candidate** —
  each with their own login endpoint, JWT signing audience, and refresh
  token table. A token issued for one can never authenticate as the other,
  even if a route-level check were accidentally omitted, because the JWT
  `aud` claim is verified centrally in the auth dependency.
- Access tokens: short-lived JWT (~15 min), signed with a server-held secret
  (or asymmetric key — finalized in Phase 2), carrying `sub`, `aud`, `org_id`
  (for users; candidates carry their own `org_id` too, per the tenant-scoped
  candidate decision), and role claims.
- Refresh tokens: opaque random value, only the hash is stored
  (`user_refresh_tokens.token_hash` / `candidate_refresh_tokens.token_hash`),
  delivered as `httpOnly; Secure` cookies (`SameSite=None` in production
  because frontend and API are on different sites, `Lax` locally) — never
  accessible to frontend JS, never put in `localStorage`. Because
  `SameSite=None` cookies are sent on cross-site requests, the CORS allow-list
  (`CORS_ALLOW_ORIGINS`) must name the exact frontend origin, and browsers that
  block third-party cookies outright (e.g. Safari) will still break the silent
  refresh unless the API is served from the same site as the frontend. Rotated on every refresh;
  reuse of an already-rotated token revokes the entire token family
  (indicates token theft).
- **Assessment invitation tokens are a third mechanism**, deliberately not a
  login session — see § 5.

## 2. Authorization

- Every recruiter-facing endpoint requires both: (a) a valid permission for
  the action (`require_permission("...")`, resolved via the RBAC tables in
  `docs/database.md` § 3.1), and (b) that the specific resource being
  touched belongs to the caller's `organization_id`. Missing either is a
  failure, not a warning.
- Candidate endpoints only ever operate on `current_candidate.id`-owned
  resources — there is no "candidate views another candidate's application"
  code path, not even behind a permission check.
- Cross-tenant access to an existing resource returns **404**, not 403 —
  this avoids confirming to an unauthorized caller that a resource with that
  ID exists in another tenant.
- Frontend route guards and conditional rendering are UX only. Every
  decision they make is re-checked server-side; this is treated as a
  correctness requirement, not a suggestion (see `CLAUDE.md` § 2).

## 3. Tenant isolation

Defense in depth, per `docs/architecture.md` § 3:

1. Application-layer: `organization_id` required in every tenant-scoped
   service/repository call, sourced only from the authenticated principal.
2. Database-layer: Postgres Row-Level Security on every tenant-owned table,
   keyed to a per-request `SET LOCAL app.current_org_id`.
3. Explicit isolation tests from Phase 2 onward: for every tenant-owned
   resource type, a test asserting "Tenant A's token cannot read/write
   Tenant B's row," run as part of the standard test suite, not a one-off
   manual check.

## 4. Secrets & configuration

- All secrets (DB credentials, JWT signing key, email provider keys, AI
  provider keys) come from environment variables via `pydantic-settings`,
  never hardcoded, never committed. `.env` is gitignored; `.env.example`
  documents required variables with placeholder values only.
- No secret is ever logged, including in error/debug logs. Log redaction is
  applied to known-sensitive field names.

## 5. Assessment invitation security

- Token is a high-entropy random value (≥ 256 bits), generated server-side,
  shown to the candidate exactly once (in the invitation email link, which is issued when the recruiter sends the invitation).
- The database stores only `sha256(token)` (`token_hash`) — a leaked
  database backup does not expose usable tokens.
- Tokens expire (`expires_at`); expired-token access returns a generic
  "invitation no longer valid" response, not a detailed reason.
- `max_attempts` bounds how many `CandidateAttempt`s a single invitation can
  spawn; exceeding it is rejected.
- Every state transition (`SENT → OPENED → STARTED → SUBMITTED`, plus
  `CANCELLED`/`EXPIRED`) is written to `AuditLog` with actor context.
- Token values themselves are never written to `AuditLog` or application
  logs — only the invitation `id` and resulting status.
- No sequential/predictable ID is ever used as an authorization check —
  knowing an `assessment_invitations.id` (a UUID, and not accepted as a URL
  parameter for the candidate-facing endpoints anyway) is not sufficient;
  only possession of the raw token is.

## 6. Input & file handling

- All request bodies validated via Pydantic — type, length, and format
  constraints declared on the schema, not checked ad hoc in handlers.
- Resume uploads: allow-listed content types (PDF/DOC/DOCX initially),
  server-side size limit, and content sniffing (not just trusting the
  client-supplied `Content-Type`) before accepting a file. Files are named
  by a generated storage key, never the client-supplied filename, and served
  back only through an authenticated download endpoint — never a raw
  filesystem/public URL.
- SQL injection: SQLAlchemy parameterized queries everywhere; no
  string-built SQL.
- XSS: React escapes by default; any place rendering user-supplied HTML
  (none planned) would require explicit sanitization — avoided by design
  (rich text fields, if ever added, render as sanitized markdown, not raw
  HTML).
- CORS: explicit allow-list of frontend origins per environment, not `*`.
- Rate limiting: applied first to unauthenticated/high-abuse-risk endpoints
  (login, register, assessment token lookup) in Phase 2/7; general API rate
  limiting considered in Phase 12 if needed.

## 7. Data exposure boundaries

- Public API: job listing/detail fields only — no candidate data, no
  recruiter data, no counts that reveal pipeline volume.
- Candidate API: own data only; application status is a candidate-safe
  projection of the internal workflow state (see `docs/recruitment-workflow.md`),
  never raw recruiter notes or AI evaluation evidence.
- Recruiter API: tenant-scoped only; role/permission-gated within the
  tenant (e.g. an `INTERVIEWER` role is not expected to see compensation
  fields or other interviewers' private notes once that distinction is
  built — tracked as a future permission granularity, not implemented in
  Phase 2's initial role set).
- Error responses never include stack traces, ORM/SQL error text, or
  internal file paths — mapped to safe, generic messages with a
  `request_id` for support/log correlation.

## 8. Audit logging

- Append-only `audit_logs` table (see `docs/database.md` § 3.10). Application
  code has no update/delete path for this table.
- Logged: authentication events, job/candidate/application create & status
  changes, assessment invitation lifecycle, screening runs, AI evaluations,
  campus drive actions, user/role changes.
- As implemented today, the organization-visible trail is the `activities`
  table (`app/models/activity.py`), readable with `activity.read` and — since
  the ORG_ADMIN activity-delete feature — removable with `activity.delete`.
  Both permissions are ORG_ADMIN-only. `DELETE /api/v1/recruiter/activities/{id}`
  filters by the caller's own `organization_id` inside the DELETE statement (and
  RLS backs it up), so another tenant's id is a plain 404; each removal is
  written to the structured application log (actor, activity id, action) but is
  not itself re-recorded as an activity. The bulk endpoints
  (`DELETE .../activities/bulk` for a selection, `.../activities/all` for the
  whole organization, which also needs an explicit `{"confirm": true}`) apply
  the same `organization_id` filter inside one DELETE statement: ids from
  another tenant or already deleted match nothing and are not counted, the
  response reports the number of rows actually removed, and one concise log line
  (counts, actor, organization — no per-row records) is written per request.
  Recruiters and hiring managers get 403 on all of them.
- Outbound email is audited in the same table: `CANDIDATE_EMAIL_SENT/FAILED`
  (application email) and `GENERAL_EMAIL_SENT/FAILED` (general email) record
  who sent which template with which subject to which addresses and whether it
  worked — never the message body and never any SMTP configuration.
- Never logged: passwords, raw tokens (access, refresh, or invitation),
  provider API keys, full request/response bodies of authentication
  endpoints.

## 9. Observability without over-building

Structured logs with request-correlation IDs, `/healthz` and `/readyz`, and
business-event logs feeding the audit table cover the initial build (see
`docs/architecture.md` § 11). A metrics/tracing stack is deferred to Phase 12
and only added if a concrete operational need justifies it.

## 10. Public AI assistant (Sigvi)

`POST /api/v1/public/ai/chat` is anonymous, so its safety comes from what the
model can reach and from input/rate limits rather than from authentication:
the model receives only curated public knowledge and public fields of OPEN
jobs (no tools, no queries, no tenant/candidate/recruiter/admin data); input,
history and output are bounded; requests are rate limited per client and
globally; replies are validated (prompt marker / key-shaped text / configured
key are never returned); provider errors are never forwarded; the Gemini key is
a `SecretStr` sent in a header; conversation text is never logged or stored.
Details and known limits: `docs/sigvi.md` §§ 5, 7, 10.

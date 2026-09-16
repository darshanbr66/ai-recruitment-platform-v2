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
  delivered as `httpOnly; Secure; SameSite=Strict` cookies — never accessible
  to frontend JS, never put in `localStorage`. Rotated on every refresh;
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
  shown to the candidate exactly once (in the invitation email link).
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
- Never logged: passwords, raw tokens (access, refresh, or invitation),
  provider API keys, full request/response bodies of authentication
  endpoints.

## 9. Observability without over-building

Structured logs with request-correlation IDs, `/healthz` and `/readyz`, and
business-event logs feeding the audit table cover the initial build (see
`docs/architecture.md` § 11). A metrics/tracing stack is deferred to Phase 12
and only added if a concrete operational need justifies it.

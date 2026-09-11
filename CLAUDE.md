# CLAUDE.md — Project Rules (AI Recruitment Platform)

This file is the binding source of truth for how this repository is built. It is
read at the start of every session. Do not silently deviate from it — if a change
is architectural or irreversible, stop and get explicit approval before
implementing it.

Roles: the product owner directs priorities. ChatGPT is the technical
architect/reviewer controlling architecture and implementation direction.
Claude (this agent) is the implementation engineer — build what is approved,
report deviations, never assume architecture from any prior/unrelated project.

This is a **new, from-scratch** repository. Nothing is carried over from any
previous "ai-recruitment-platform" project.

## 1. Product scope

A multi-tenant recruitment intelligence platform with three surfaces:

- **Recruiter portal**: Platform Overview, Sourcing, Application Review,
  Screening, Notes, Assessments, Reports, Jobs, Campus Drives, Candidates,
  Users/Settings.
- **Candidate portal**: register/login, profile, resume upload, browse/apply to
  jobs, view applications and status, take assessments via invitation.
- **Public career site**: anonymous job browse/search/details, entry point into
  candidate apply flow.

Full recruitment lifecycle: job creation → sourcing → application → resume
parsing → screening (AI-assisted) → recruiter review → assessment (optional) →
interview → decision → reporting. Campus/mass hiring is a first-class variant
of this flow, not a bolted-on special case.

## 2. Non-negotiable domain principles

- **Candidate != Application.** Candidate holds reusable personal/profile data.
  Application is the relationship between a Candidate and a hiring opportunity
  (Job, optionally sourced via a Campus Drive) and carries all workflow state.
  A Candidate has many Applications.
- **Assessment != Campus Drive.** Assessments are a reusable domain usable by
  normal recruitment and campus hiring alike. Never couple assessment logic to
  campus-specific code paths.
- **AI != Candidate.** AI screening results (ScreeningRun / AIRun /
  RequirementEvaluation / EvaluationEvidence) are their own traceable domain,
  linked to Application, never merged into the Candidate model. Re-running
  screening must never destroy prior evaluation history.
- **Email provider != business logic.** Notification sending is an
  infrastructure service behind an interface. Route handlers and domain
  services never call a provider SDK directly.
- **Frontend authorization != backend authorization.** The UI may hide things
  for UX; every authorization decision is re-enforced server-side.
- **Tenant isolation != frontend filtering.** Every tenant-owned row carries an
  `organization_id` and is enforced at the query layer (and via Postgres RLS —
  see `docs/security.md`). Never rely on the client to scope data.
- **Resume storage != DB blob.** File bytes live in a storage abstraction
  (local disk now, S3-compatible later). Postgres stores metadata only. Never
  expose raw storage paths to clients.
- **Workflow state != ad hoc strings.** Application status and assessment
  invitation status are enums governed by explicit transition tables in a
  workflow module, not scattered `if` statements.
- **Reports != hardcoded numbers.** Every reported metric is computed from
  persisted data, tenant-scoped.

## 3. Tech stack (fixed — do not swap without approval)

**Backend:** Python, FastAPI, SQLAlchemy 2.x (async), PostgreSQL + pgvector,
Alembic, Pydantic v2 / pydantic-settings, Pytest, Argon2id for password hashing
(never bcrypt for this project unless explicitly instructed later).

**Frontend:** React 19, TypeScript (strict), Vite, React Router, TanStack
Query, Vitest.

**Background jobs:** Arq (Redis-backed), added starting Phase 5 when the
first real job (embedding generation) exists — see
`docs/architecture.md` § 12 for the decision record. Do not introduce
Celery or another queue without approval.

**No LangChain/LangGraph assumed.** If introduced later: isolate orchestration
behind our own interfaces, keep providers swappable, keep prompts
configurable, keep domain logic independent of the framework.

## 4. Architectural decisions on record

These were made during Phase 0 and documented in `docs/architecture.md`. Treat
as settled unless a reviewer explicitly overturns one — do not re-litigate
silently.

1. **Primary keys: UUID (v4) everywhere**, DB-generated
   (`gen_random_uuid()`/`pgcrypto`), stored as native Postgres `uuid`. No
   integer PKs, no mixing. Rationale and tradeoffs in `docs/database.md`.
2. **Candidate is tenant-scoped** (`organization_id` NOT NULL on `candidates`),
   unique on `(organization_id, email)`. The same human applying to two
   different organizations on the platform is two independent Candidate
   records. This follows directly from the tenant-isolation requirement that
   lists candidates as isolated tenant data.
3. **Tenant isolation is enforced twice**: application-layer scoping
   (every query goes through a service/repository that requires an
   `organization_id`) **and** Postgres Row-Level Security as a DB-level
   backstop. See `docs/security.md`.
4. **Assessment invitations use opaque bearer tokens**, stored only as a
   salted hash (`token_hash`), never the raw token. Invitation access does not
   require a logged-in Candidate account — this supports imported campus
   candidates who may never register on the portal.
5. **Modular monolith**, not microservices. Domain separation happens at the
   Python package level (`models/`, `services/`, `api/` all split by domain).
   Revisit only if a specific domain needs independent scaling/deployment.
6. **AI/embeddings are provider-agnostic** behind `integrations/ai/` interfaces
   (`EmbeddingProvider`, `LLMProvider`, `DocumentExtractor`). No concrete
   vendor is wired into domain/service code.

## 5. Development rules

- Production quality only. No fake implementations, placeholder logic,
  meaningless mocks, or duplicate models/services.
- No business logic in route handlers — handlers call services; services own
  logic and transactions; repositories (where justified) own data access.
- No dependency added without a stated reason.
- No silent architectural changes, no unrelated deletions, no unnecessary
  renames.
- Mock only for tests, and only where a real integration is impractical in
  test scope.
- Every schema change goes through an Alembic migration. Never hand-edit a
  production schema.
- Security boundaries (tenant isolation, candidate/recruiter auth separation,
  invitation tokens) must have explicit tests.

## 6. Workflow for every phase

1. Explain what will be built and why.
2. Identify the exact files/modules touched.
3. Implement.
4. Run tests.
5. Run type/import checks.
6. Fix failures.
7. Report exactly what changed.
8. Report remaining issues/known gaps.

Implementation proceeds in the phase order defined in `docs/architecture.md`
§ Implementation Phases. Do not jump ahead to a later phase's concerns without
flagging it.

## 7. Documentation

Keep `README.md` and everything under `docs/` in sync with what is actually
implemented. Never document aspirational functionality as done. Update the
relevant doc in the same change that alters the behavior it describes.

## 8. Git

Do not commit `.env`, secrets, credentials, `uploads/` contents, virtual
environments, or `node_modules`. Only commit when explicitly asked. Prefer
small, logical commits with clear messages.

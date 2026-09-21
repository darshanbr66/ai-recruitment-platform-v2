# AI Recruitment Platform

A multi-tenant recruitment intelligence platform covering recruiter-side
hiring workflows (jobs, candidates, applications, AI screening, assessments,
campus hiring, reporting) and a public candidate-facing career site/apply
flow.

**Status:** Local development demo. Working end-to-end: staff auth (with
org/tenant isolation via Postgres RLS), Jobs/Candidates/Applications CRUD
and pipeline, a public career site with resume upload, AI-assisted resume
screening, MCQ assessments with token-based candidate access (no login
required), campus drives, application notes, live reports, and outbound
template-based candidate email (Resend over HTTPS in production, SMTP for local development). Email is **manual only**: a
recruiter picks one of six professional HTML templates (application received,
interview invitation, assessment invitation, next steps, rejection, general),
edits it if needed, previews it, and sends. Applying, assigning an assessment
and changing a status never send email on their own. The same composer is also
available as a general **Email** page for messages that aren't tied to an
application. The Team page shows a live organization chart built from the
organization's departments and employees. Employees appear in a stored order —
new employees are added at the end of their department, and an org admin can
drag them (or use the arrow keys on the drag handle) to rearrange a department;
the position itself is internal and never shown. An org admin can also delete
activity entries in bulk (a selection, or every entry of their own organization).

The visual language, motion rules, the lazy-loaded 3D landing hero (with its
static fallback) and the accessibility approach are described in
[`docs/design-system.md`](docs/design-system.md).

Local test accounts are in [`docs/TEST_CREDENTIALS.md`](docs/TEST_CREDENTIALS.md).
No candidate portal (self-service login/profile) yet — candidates interact
anonymously via the public apply flow and assessment invitation links.
See `docs/architecture.md` for the original full design and phase plan, and
the "Implementation status" note at the top of each of the docs below for
how the current build compares to that original design (some domains were
intentionally simplified for the local MVP — see each doc for specifics).

## Repository layout

```
/
├── backend/     FastAPI + SQLAlchemy + PostgreSQL/pgvector application (Phase 1+)
├── frontend/    React 19 + TypeScript + Vite application (Phase 1+)
├── docs/        Architecture, database, API, security, and workflow documentation
├── CLAUDE.md    Binding project rules and architectural decision record
└── README.md    This file
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — system shape, domain
  modules, multi-tenancy, identity/authz, API boundary, frontend structure,
  implementation phases, risks.
- [`docs/database.md`](docs/database.md) — entity model, primary key
  strategy, relationships, indexing.
- [`docs/api.md`](docs/api.md) — API versioning, audience partitioning,
  endpoint surface, conventions.
- [`docs/security.md`](docs/security.md) — authentication, authorization,
  tenant isolation, secrets, invitation token security.
- [`docs/recruitment-workflow.md`](docs/recruitment-workflow.md) —
  application status model and lifecycle.
- [`docs/campus-hiring.md`](docs/campus-hiring.md) — campus drive model and
  bulk assessment invitation flow.
- [`docs/assessment.md`](docs/assessment.md) — assessment domain model,
  secure invitation mechanics, evaluation.
- [`docs/ai-screening.md`](docs/ai-screening.md) — resume intelligence and
  AI screening pipeline, provider abstraction.
- [`docs/TEST_CREDENTIALS.md`](docs/TEST_CREDENTIALS.md) — local test/demo
  login credentials for every role.

## Running locally

Prerequisites: Python 3.12+, Node 20+, a PostgreSQL 16+ instance with the
`vector` (pgvector) extension enabled, and a dedicated database/role for
this project (see `backend/.env.example`).

**Backend**

```bash
cd backend
python -m venv .venv
./.venv/Scripts/pip install -e ".[dev]"     # ./.venv/bin/pip on macOS/Linux
cp .env.example .env                         # then fill in real values
PYTHONFAULTHANDLER=1 ./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python run.py                # dev server on http://127.0.0.1:8000
```

`run.py` (not a plain `uvicorn app.main:app`) is the local dev entrypoint on
Windows — see the comment in that file for why. On Linux/containers,
`uvicorn app.main:app` works directly.

On Windows, `python -m alembic <command>` occasionally aborts silently
(exit code 127, no output) the first time it's invoked after a fresh
interpreter/DB state — this is an observed interaction between psycopg3's
async mode and the greenlet bridge Alembic uses to run its (synchronous)
migration operations, not an application bug. Running with
`PYTHONFAULTHANDLER=1` set reliably avoids it; harmless to leave set for
every Alembic invocation on Windows.

Optional environment variables (`backend/.env`, see `.env.example` for the
full list) enable outbound email and AI screening; the app runs fully
without them — both features fail with a clear "not configured" message
rather than faking success/results:

| Variable | Enables |
|---|---|
| `SMTP_HOST`, `SMTP_PORT` (default `587`), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USE_TLS` (default `true`) | Outbound email over SMTP for the recruiter's manual "Send Email" / "Send Assessment Invitation" actions (nothing is emailed automatically). `SMTP_PASSWORD` is a secret — keep it in your local `.env` / the host's secret store only, never in source or `.env.example`. With any of host/username/password/from-address missing, sends fail with a clear `email_not_configured` error. |
| `RESEND_API_KEY`, `EMAIL_FROM` | Outbound email over HTTPS via [Resend](https://resend.com) — **the production provider** (hosts like Render's free web services block outbound SMTP ports). When both are set, Resend is used in preference to SMTP. `RESEND_API_KEY` is a secret. `EMAIL_FROM` must be an address on a domain verified in Resend, e.g. `SIGVITAS <hr@yourdomain.com>`. Leave both empty locally to keep using SMTP. |
| `OLLAMA_BASE_URL` (+ `OLLAMA_MODEL`) | AI-assisted resume screening via a **free, local** [Ollama](https://ollama.com) model — no API key, nothing leaves your machine. Preferred over the paid options below when set. |
| `ANTHROPIC_API_KEY` *or* `OPENAI_API_KEY` | AI-assisted resume screening via a paid cloud provider, if you'd rather not run Ollama. Only used when `OLLAMA_BASE_URL` isn't set. |

Backend checks:

```bash
./.venv/Scripts/python -m pytest
./.venv/Scripts/python -m ruff check app tests alembic
./.venv/Scripts/python -m mypy app
```

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env.local                  # VITE_API_BASE_URL, if not default
npm run dev                                  # dev server on http://localhost:5173
```

Frontend checks:

```bash
npm run typecheck
npm run lint
npm run test
npm run build
```

## Tech stack

**Backend:** Python, FastAPI, SQLAlchemy 2.x (async), PostgreSQL + pgvector,
Alembic, Pydantic v2, Pytest, Argon2id password hashing.

**Frontend:** React 19, TypeScript, Vite, React Router, TanStack Query,
Vitest; Three.js (lazy-loaded, for the public landing hero only).

## Working on this project

Read [`CLAUDE.md`](CLAUDE.md) first — it holds the binding project rules,
non-negotiable domain principles, and the recorded architectural decisions.
Implementation proceeds in the phases listed in `docs/architecture.md` § 12;
each phase is scoped, implemented, tested, and reported before the next one
starts.

# Deployment (Render + Vercel)

**Status: preparation only.** This document describes how to deploy the
SIGVITAS recruitment platform — backend to Render, frontend to Vercel,
database to Render PostgreSQL. Nothing described here has been executed
against a production environment as part of writing this document; no
Render/Vercel resources, secrets, or DNS records have been created.

## 0. Architecture recap

- **Backend**: FastAPI (`backend/`), Python 3.12, SQLAlchemy 2 (async,
  psycopg3), Alembic migrations. Fully configured through environment
  variables (`app/core/config.py`) — no hardcoded hosts, ports, or
  credentials anywhere in the app.
- **Frontend**: React 19 + Vite (`frontend/`), a single-page app using
  `react-router-dom`'s `BrowserRouter`.
- **Database**: PostgreSQL. The schema uses native enums, Postgres
  Row-Level Security, and (architecturally, not yet by any migration —
  see § 6) pgvector.

---

## 1. Create the Render PostgreSQL database

1. Render dashboard → **New** → **PostgreSQL**.
2. Choose a plan/region. Note the database name, user, and the
   **Internal Database URL** (for the Render web service) and **External
   Database URL** (for running Alembic from your own machine, e.g. the
   first `alembic upgrade head`).
3. Render's connection string looks like:
   `postgres://<user>:<password>@<host>/<database>`

   **This app requires the `postgresql+psycopg://` scheme** (SQLAlchemy's
   async psycopg3 driver). Rewrite it before use:

   ```
   postgres://user:pass@host/db   →   postgresql+psycopg://user:pass@host/db
   ```

   This is the single most common way to break the deploy — the app will
   fail to start (or Alembic will fail to connect) if the scheme isn't
   rewritten. `app/core/config.py` and `.env.example` both call this out.

## 2. Enable the pgvector extension

No current migration creates or uses pgvector — the schema doesn't have any
embedding columns yet (`docs/architecture.md` defers that to a later
phase; see `app/models/screening.py`'s docstring). It is **not required**
for `alembic upgrade head` to succeed today. Enable it anyway, since it's
part of the fixed tech stack (CLAUDE.md § 3) and Render's managed Postgres
supports it natively:

Connect with `psql` (using the External Database URL) and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## 3. Configure Render environment variables

Create these on the Render **web service** (not the database). See
`backend/.env.example` for the authoritative list with inline explanations.
`render.yaml` (repo root) lists every key the Blueprint expects; anything
marked `sync: false` there must be filled in by hand in the dashboard —
nothing sensitive is stored in the Blueprint file itself.

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | Yes | Render's connection string, rewritten to `postgresql+psycopg://` (§ 1). |
| `JWT_SECRET_KEY` | Yes | Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Never reuse the local dev value. |
| `JWT_ALGORITHM` | No (default `HS256`) | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No (default `15`) | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No (default `30`) | |
| `ENVIRONMENT` | Recommended | Set to `production`. Gates `Settings.is_production`. |
| `DEBUG` | Recommended | Set to `false`. Also flips refresh-token cookies to `Secure` (see `app/api/v1/recruiter/auth.py`). |
| `LOG_LEVEL` | No (default `INFO`) | |
| `CORS_ALLOW_ORIGINS` | Yes | JSON array, e.g. `["https://<your-vercel-domain>"]`. See § 5. |
| `FRONTEND_BASE_URL` | Yes | The same Vercel origin — used to build assessment/campus-drive links shared with candidates. |
| `RESUME_STORAGE_PROVIDER` | Recommended | Set to `mongodb_gridfs` in production. See § 11. |
| `RESUME_STORAGE_DIR` | No (default `uploads/resumes`) | Only used when `RESUME_STORAGE_PROVIDER=local`. Ephemeral on Render's default filesystem — see § 11. |
| `MAX_RESUME_SIZE_MB` | No (default `10`) | |
| `MONGODB_URI` | Yes, if `RESUME_STORAGE_PROVIDER=mongodb_gridfs` | Connection string for the MongoDB deployment storing resume files (e.g. an Atlas cluster). Never commit the real value. |
| `MONGODB_DATABASE` | No (default `ai_recruitment`) | Database name within the MongoDB deployment; the `resumes` GridFS bucket is created inside it. |
| `RESEND_API_KEY` / `EMAIL_FROM` | No | Optional. Unset → email sends report "not configured" rather than failing or faking success. |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | No | Optional, free/local AI screening — not reachable from Render, only useful if you run Ollama somewhere Render can reach it. |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | No | Optional paid AI screening providers. Do not set unless you intend to enable AI screening. |

None of the optional integrations block startup or any core workflow if
left unset — this is enforced in code (`app/integrations/email`,
`app/integrations/ai`), not just a deployment convention.

## 4. Run Alembic migrations against the production database

From your own machine (not Render's shell, so you control exactly when
this runs), with the **External Database URL** (rewritten per § 1) in your
environment:

```bash
cd backend
DATABASE_URL="postgresql+psycopg://...<external-url>..." alembic upgrade head
```

This is the **first and only** way the schema should ever be created —
`Base.metadata.create_all()` is never used anywhere in this codebase.
`alembic upgrade head` on a brand-new, empty database runs every migration
in order (identity/tenancy → recruitment core → screening/assessments/
campus/notes → campus-drive redesign → activity/soft-delete → assessment
retests → team-management/soft-delete columns → the WITHDRAWN→REJECTED
enum rebuild → job description visibility → assessment monitoring events →
team hierarchy/departments/employees), seeding system roles and permissions
as it goes. This full chain was verified locally (`alembic downgrade base`
→ `alembic upgrade head` → `alembic downgrade base` → `alembic upgrade
head`) during the SIGVITAS platform work — see git history — with no
manual intervention required.

After migrating, create the platform super admin (needed to bootstrap the
first organization via `/api/v1/admin/organizations`):

```bash
DATABASE_URL="...same external url..." python -m app.cli create-superadmin \
  --email you@yourcompany.com --password "<a strong password>" --full-name "Your Name"
```

**Do not** run `alembic upgrade head` against the local development
database as part of this preparation task — only against the new Render
database, and only when you're actually ready to initialize it.

## 5. Create the Render Web Service

- **Root directory**: `backend`
- **Runtime**: Python (native, not Docker — no Dockerfile is needed; see
  § "Why no Docker" below)
- **Python version**: `3.12.10`, pinned via `backend/.python-version` (Render
  reads this file automatically) and mirrored in `render.yaml`'s
  `PYTHON_VERSION` env var as a second, explicit pin.
- **Build command**: `pip install --upgrade pip && pip install .`
  (installs from `pyproject.toml` — there is no separate `requirements.txt`
  to keep dependency declarations in one place)
- **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path**: `/healthz`

If you use the Blueprint (`render.yaml` at the repo root), most of this is
already filled in — Render will still prompt for every `sync: false`
variable.

### Why no Docker

The backend has no native-extension dependency that needs a custom system
image — `psycopg[binary]` ships a self-contained wheel, and
`uvicorn[standard]`'s extras (`uvloop`, `httptools`) have prebuilt Linux
wheels. Render's native Python buildpack handles `pip install .` directly,
so a Dockerfile would add a maintenance surface with no corresponding
benefit right now.

### Why `uvicorn` directly, not Gunicorn

A single `uvicorn` process is sufficient for this deployment's current
scale and keeps the process model simple. If concurrency ever becomes a
bottleneck, moving to `gunicorn -k uvicorn.workers.UvicornWorker` is a
one-line start-command change — not introduced now, per the project's "no
dependency without a stated reason" rule (`gunicorn` isn't in
`pyproject.toml` today).

### Windows-specific code does not affect production

`backend/run.py`'s Windows event-loop shim
(`app/core/asyncio_compat.py::configure_event_loop_policy`) is a documented
no-op on every platform except Windows. Render's Linux containers are
unaffected; the start command above (`uvicorn app.main:app` directly, not
through `run.py`) is exactly what the code's own docstring recommends for
non-Windows environments.

## 6. Verify `/healthz`

Once deployed:

```bash
curl https://<your-render-service>.onrender.com/healthz
# {"status":"ok"}
```

This endpoint (`app/api/system.py`) does not touch the database and
requires no authentication — safe for Render's health-check probe. A
second endpoint, `/readyz`, does check database connectivity
(`SELECT 1`) and returns HTTP 503 if the database is unreachable; use it
for post-deploy verification, not as the Render health-check path (a
transient DB blip shouldn't cause Render to restart the whole service).

## 7. Deploy the Vercel frontend

- **Root directory**: `frontend`
- **Framework preset**: Vite
- **Install command**: `npm install` (default)
- **Build command**: `npm run build` (runs `tsc -b && vite build`)
- **Output directory**: `dist`

## 8. Configure the Vercel API URL

Set in the Vercel project's environment variables:

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://<your-render-service>.onrender.com` |

This is the **only** environment variable the frontend needs. Every
`VITE_*`-prefixed variable is bundled into client-side JS and is publicly
readable — never put a backend secret in one (there currently are none
here to worry about; the frontend has no secrets at all).

## 9. Update Render CORS with the real Vercel URL

Once Vercel assigns your production domain, go back to the Render web
service and set:

```
CORS_ALLOW_ORIGINS=["https://<your-vercel-domain>"]
FRONTEND_BASE_URL=https://<your-vercel-domain>
```

(Add a second entry to the `CORS_ALLOW_ORIGINS` array if you also keep a
Vercel preview-deployment domain you want to exercise against the same
backend.) Redeploy the Render service after changing env vars so
`get_settings()` — an `lru_cache`d singleton — picks up the new value on
the fresh process.

## 10. Test the production application

1. `GET /healthz` → `{"status":"ok"}`.
2. `GET /readyz` → `{"status":"ok","database":"ok","mongodb":"ok"}` (the
   `mongodb` key is only present when `RESUME_STORAGE_PROVIDER=mongodb_gridfs`).
3. Log in as the super admin created in § 4, create the SIGVITAS
   organization + admin via `/api/v1/admin/organizations`.
4. Log in as that org admin from the deployed frontend; confirm CORS
   works (no browser console CORS errors) and the refresh-token cookie is
   set (check DevTools → Application → Cookies — should show `Secure`,
   `HttpOnly`, `SameSite=Strict`).
5. Create a job, publish it, open the public career site
   (`https://<vercel-domain>/org/<slug>`), submit a test application,
   confirm the resume upload succeeds and is retrievable — see § 11 for
   the `RESUME_STORAGE_PROVIDER=mongodb_gridfs` variables this depends on
   in production.
6. Refresh the browser on a deep link (e.g. `/recruiter/applications`) to
   confirm Vercel's SPA rewrite (`frontend/vercel.json`) is working — it
   should render the app, not a 404.

---

## 11. File / resume storage

Resume file *bytes* live behind the `ResumeStorage` abstract interface
(`app/integrations/storage/base.py`) that every route/service depends on —
no route or service touches a filesystem or database driver directly.
Two implementations exist, selected by `RESUME_STORAGE_PROVIDER`:

- **`local`** (`app/integrations/storage/local.py`) — writes to local disk
  under `RESUME_STORAGE_DIR`. Development default. **Render's default
  web-service filesystem is ephemeral**: files written to it do not
  survive a redeploy/restart and are not shared across instances — never
  use this in production.
- **`mongodb_gridfs`** (`app/integrations/storage/mongo_gridfs.py`) —
  **the production setting.** Stores resume bytes in a MongoDB GridFS
  bucket named `resumes`, addressed by the bucket file's ObjectId. Postgres
  remains the system of record for everything else (`resumes.storage_path`
  holds only that opaque ObjectId string; `resumes.storage_provider`
  records which backend wrote it, so resumes uploaded before this setting
  changed keep resolving against `local` correctly — CLAUDE.md § 2:
  "Resume storage != DB blob").

**Required Render environment variables for production**:

```
RESUME_STORAGE_PROVIDER=mongodb_gridfs
MONGODB_URI=<your MongoDB connection string — set in the Render dashboard, never in Git>
MONGODB_DATABASE=ai_recruitment
```

Any MongoDB deployment reachable from Render works (e.g. a free-tier
[MongoDB Atlas](https://www.mongodb.com/atlas) cluster). Create the
cluster, allow network access from Render (or use Atlas's "allow from
anywhere" for a first deploy, then tighten it), and paste its connection
string into `MONGODB_URI` in the Render dashboard as a secret.

The MongoDB client is created once at process startup (`app/db/mongo.py`,
wired into `app.main`'s lifespan) — never per request — and pinged during
startup and by `/readyz`. `/readyz` only checks MongoDB when
`RESUME_STORAGE_PROVIDER=mongodb_gridfs`; it never checks it while
`local` is selected, since that configuration has no MongoDB dependency
to be ready.

**Before going live with real candidate applications, confirm
`RESUME_STORAGE_PROVIDER=mongodb_gridfs` and `MONGODB_URI` are both set —
do not deploy the default local-disk configuration and assume resumes are
safe.**

## 12. Email — production behavior

The manual "Send Interview Email" action
(`app/services/notification_service.py::send_interview_email`) and every
other outbound email path already meet the production bar with no changes
needed:

- Manually triggered only — nothing sends automatically on a status change
  except the existing best-effort candidate status-update notification,
  which was already the case before this deployment work and is unrelated
  to the interview-email feature.
- No hardcoded credentials — `RESEND_API_KEY`/`EMAIL_FROM` come from the
  environment (`app/integrations/email/__init__.py::get_email_provider`).
- If unset, sends are logged as "not configured" and every caller reports
  that honestly back to the recruiter (`sent: false, reason: "..."`) —
  never a fabricated success (see `app/integrations/email/base.py`'s
  `UnconfiguredEmailProvider`).

Leave `RESEND_API_KEY`/`EMAIL_FROM` unset until you have a verified
sending domain with Resend; the app is fully functional without them.

## 13. AI provider — production behavior

Optional by construction (`app/integrations/ai/__init__.py::get_llm_provider`):
if none of `OLLAMA_BASE_URL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` is set,
AI-assisted screening returns a clear "not configured" error rather than
failing startup or fabricating a result. **Do not set any AI provider
key as part of this deployment** unless you've decided to enable AI
screening — the platform is fully usable without it.

## 14. Security posture at deployment time

Audited as part of this preparation task:

- No `.env` file has ever been committed to this repository's git history
  (checked with `git log --all --diff-filter=A --name-only`) — no secret
  rotation is required before deploying.
- No hardcoded passwords, API keys, or database credentials exist in
  application code. The only credentials in the repository are the
  documented local-dev-only demo accounts in `docs/TEST_CREDENTIALS.md`
  and test fixtures — do not reuse any of those emails/passwords for a
  real production account.
- `JWT_SECRET_KEY` and `DATABASE_URL` have no default — the app refuses to
  start without them (`app/core/config.py::Settings`), which is the
  correct fail-closed behavior.
- Refresh-token cookies are `HttpOnly`, `SameSite=Strict`, and `Secure`
  whenever `DEBUG=false` (`app/api/v1/recruiter/auth.py`) — sets
  correctly once `DEBUG` is set per § 3.
- Structured JSON logs redact `password`, `hashed_password`, `token`,
  `authorization`, and `secret` keys unconditionally
  (`app/core/logging.py::_SENSITIVE_KEYS`) — independent of log level.
- The generic exception handler never leaks stack traces, SQL text, or
  file paths to a client response — only to server-side logs, keyed by a
  request ID (`app/core/exceptions.py`).
- Swagger/OpenAPI (`/docs`, `/redoc`, `/openapi.json`) is left enabled —
  no route in this API exposes a secret in its schema or example values,
  and there's no existing requirement in this codebase to disable it. If
  you'd prefer it disabled in production, that's a one-line change
  (`docs_url=None, redoc_url=None` in `create_app()`), not made here since
  it wasn't a stated requirement.
- Found no committed real API keys, private keys, or AWS-style access
  keys anywhere in the repository (pattern search across `.py`, `.ts`,
  `.tsx`, `.md`, `.json`, `.ini`, `.yaml`/`.yml`).

## 15. Debug / production-mode checklist

Set on the Render web service before considering the deploy "production":

- `DEBUG=false` (disables FastAPI's debug tracebacks and flips cookies to
  `Secure`)
- `ENVIRONMENT=production`
- `LOG_LEVEL=INFO` (or `WARNING` if you want quieter logs — never
  `DEBUG`, which would also turn on verbose SQLAlchemy engine logging if
  that were ever wired to the SQL logger; today `echo=False` is hardcoded
  in `app/db/session.py` regardless of `LOG_LEVEL`, so this isn't
  currently a real risk, just good practice)

There are no development-only endpoints or test-authentication bypasses
anywhere in the route tree to worry about disabling — none exist in this
codebase.

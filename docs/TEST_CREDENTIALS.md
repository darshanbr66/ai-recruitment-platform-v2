# Test / Demo Credentials (Local Development Only)

These accounts exist in the **local development database** only
(`ai_recruitment_v2` on `localhost:5432`, per `backend/.env`). They are for
frontend/API manual testing. Never use these emails/passwords in a shared or
production environment.

Verified working (`POST /api/v1/recruiter/auth/login` → `200`) on 2026-09-16.

## Platform super admin

Used for `/api/v1/admin/*` (organization bootstrap/management). Not tied to
any tenant — `organization_id` is `NULL`.

| Field | Value |
|---|---|
| Email | `super.admin@platform.dev` |
| Password | `SuperAdmin@2026Dev` |
| Role | `SUPER_ADMIN` |
| Organization | — (platform-level) |
| Purpose | Bootstrap/manage organizations via the admin API |

## Organization admin — Acme Corp

| Field | Value |
|---|---|
| Email | `admin@acme-corp.dev` |
| Password | `OrgAdmin@2026Dev` |
| Role | `ORG_ADMIN` |
| Organization | Acme Corp (`acme-corp`) |
| Purpose | Full recruiter-portal access + user management (`user.create`/`user.read`) for the tenant |

## Recruiter — Acme Corp

| Field | Value |
|---|---|
| Email | `recruiter@acme-corp.dev` |
| Password | `Recruiter@2026Dev` |
| Role | `RECRUITER` |
| Organization | Acme Corp (`acme-corp`) |
| Purpose | Standard recruiter-portal testing (jobs, candidates, applications) without user-management permissions — use to verify role boundaries against `admin@acme-corp.dev` |

## Notes

- No candidate-portal test accounts exist yet (candidate auth ships in a
  later phase per `docs/architecture.md`).
- Login endpoint: `POST /api/v1/recruiter/auth/login` with `{"email": ..., "password": ...}`.
- If you reseed or reset these accounts, update this file in the same
  change so it keeps matching the local database.

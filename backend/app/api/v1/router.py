"""Aggregates every /api/v1/* sub-router.

Audience-partitioned sub-routers (public/candidate/assessment/recruiter/
admin — see docs/api.md) are added here as each is built, starting Phase 2.
Nothing is registered yet in Phase 1 — health/readiness are mounted at the
application root instead, since they are infrastructure probes, not
versioned product API (see app/api/v1/system.py).
"""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

"""Aggregates every /api/v1/* sub-router.

Audience-partitioned sub-routers (public/candidate/assessment/recruiter/
admin — see docs/api.md) are added here as each is built. Health/readiness
are mounted at the application root instead, since they are infrastructure
probes, not versioned product API (see app/api/system.py).
"""

from fastapi import APIRouter

from app.api.v1.admin.router import router as admin_router
from app.api.v1.recruiter.router import router as recruiter_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(recruiter_router)
api_router.include_router(admin_router)

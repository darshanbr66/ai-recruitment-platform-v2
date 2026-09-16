from fastapi import APIRouter

from app.api.v1.public.applications import router as applications_router
from app.api.v1.public.assessments import router as assessments_router
from app.api.v1.public.jobs import router as jobs_router

router = APIRouter(prefix="/public")
router.include_router(jobs_router)
router.include_router(applications_router)
router.include_router(assessments_router)

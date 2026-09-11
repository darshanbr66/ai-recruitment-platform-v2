from fastapi import APIRouter

from app.api.v1.recruiter.auth import router as auth_router
from app.api.v1.recruiter.users import router as users_router

router = APIRouter(prefix="/recruiter")
router.include_router(auth_router)
router.include_router(users_router)

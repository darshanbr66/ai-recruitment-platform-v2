from fastapi import APIRouter

from app.api.v1.admin.organizations import router as organizations_router

router = APIRouter(prefix="/admin")
router.include_router(organizations_router)

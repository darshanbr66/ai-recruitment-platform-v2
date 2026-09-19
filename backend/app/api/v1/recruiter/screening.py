"""AI-assisted resume screening for one Application. Results are always
presented as an assistive opinion for a recruiter to review, never an
automatic decision (docs/ai-screening.md)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.screening import ScreeningRunResponse
from app.services import screening_service

router = APIRouter(prefix="/applications/{application_id}/screening", tags=["recruiter-screening"])


@router.post("", response_model=ScreeningRunResponse, status_code=status.HTTP_201_CREATED)
async def start_screening(
    application_id: uuid.UUID,
    current_user: User = Depends(require_permission("screening.create")),
    db: AsyncSession = Depends(get_db),
) -> ScreeningRunResponse:
    assert current_user.organization_id is not None
    run = await screening_service.run_screening(
        db,
        organization_id=current_user.organization_id,
        application_id=application_id,
        requested_by_user_id=current_user.id,
    )
    return ScreeningRunResponse.model_validate(run)


@router.get("", response_model=list[ScreeningRunResponse])
async def list_screening(
    application_id: uuid.UUID,
    _: User = Depends(require_permission("screening.read")),
    db: AsyncSession = Depends(get_db),
) -> list[ScreeningRunResponse]:
    runs = await screening_service.list_screening_runs(db, application_id)
    return [ScreeningRunResponse.model_validate(run) for run in runs]

"""Platform-level organization administration — SUPER_ADMIN only.

Organization creation must go through the privileged/bypass path
(`get_current_super_admin`) because a tenant cannot be scoped by RLS before
it exists (docs/security.md § 3).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationSettingsUpdateRequest,
)
from app.services import organization_service

router = APIRouter(prefix="/organizations", tags=["admin-organizations"])


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreateRequest,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    organization, _admin_user = await organization_service.bootstrap_organization(
        db,
        name=payload.name,
        slug=payload.slug,
        admin_email=payload.admin_email,
        admin_password=payload.admin_password,
        admin_full_name=payload.admin_full_name,
    )
    return OrganizationResponse.model_validate(organization)


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationResponse]:
    organizations = await organization_service.list_organizations(db)
    return [OrganizationResponse.model_validate(org) for org in organizations]


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization_settings(
    organization_id: uuid.UUID,
    payload: OrganizationSettingsUpdateRequest,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Company-level configuration — e.g. the careers contact email shown to
    candidates and used as the reply-to of system emails."""
    organization = await organization_service.update_organization_settings(
        db, organization_id=organization_id, payload=payload
    )
    return OrganizationResponse.model_validate(organization)

"""User management within the caller's own organization.

`organization_id` is always taken from the authenticated caller, never from
the request — see app/schemas/user.py and docs/security.md § 2.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreateRequest, UserResponse, UserUpdateRequest
from app.services import user_service

router = APIRouter(prefix="/users", tags=["recruiter-users"])


async def _to_response(db: AsyncSession, user: User) -> UserResponse:
    roles = await user_service.get_user_role_names(db, user.id)
    return UserResponse(
        id=user.id,
        organization_id=user.organization_id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        roles=roles,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    current_user: User = Depends(require_permission("user.create")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    # current_user.organization_id is guaranteed non-None here: only tenant
    # users can hold the "user.create" permission (see the Phase 2
    # migration's role_permissions seed — SUPER_ADMIN is not granted it).
    assert current_user.organization_id is not None
    created = await user_service.create_tenant_user(
        db,
        organization_id=current_user.organization_id,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role_name=payload.role.value,
        actor=current_user,
    )
    return await _to_response(db, created)


@router.get("", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(require_permission("user.read")),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    assert current_user.organization_id is not None
    users = await user_service.list_organization_users(db, current_user.organization_id)
    return [await _to_response(db, user) for user in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_permission("user.read")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await user_service.get_organization_user(db, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return await _to_response(db, user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_permission("user.update")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Deactivate/reactivate a team member or change their role
    (app/services/user_service.py::update_team_member owns every guard —
    self-deactivation and last-admin protection — and the audit trail)."""
    target = await user_service.get_organization_user(db, user_id)
    if target is None:
        raise NotFoundError("User not found.")
    updated = await user_service.update_team_member(
        db, actor=current_user, target=target, payload=payload
    )
    return await _to_response(db, updated)

"""FastAPI dependencies for authentication and authorization.

Two principals exist in this system (User/staff, Candidate — see
CLAUDE.md § 2); this module only deals with User. Candidate auth is a
separate mechanism built in Phase 4.
"""

import uuid
from collections.abc import Callable, Coroutine

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import InvalidTokenError, TokenAudience, decode_access_token
from app.db.rls import rls_bypass, set_rls_bypass, set_tenant_context
from app.db.session import get_db
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)

_INVALID_TOKEN = "Invalid or expired token."


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolves the caller from a `user`-audience JWT and sets this
    request's RLS tenant context from the *database's* record of the
    user's organization_id — not from the JWT's own `org_id` claim, which
    is informational only and never trusted for authorization (see
    docs/security.md § 2).
    """
    if credentials is None:
        raise UnauthorizedError("Not authenticated.")

    try:
        claims = decode_access_token(credentials.credentials, audience=TokenAudience.USER)
        user_id = uuid.UUID(claims["sub"])
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise UnauthorizedError(_INVALID_TOKEN) from exc

    # Looking up "who is this" for a request that has no tenant context yet
    # is exactly the privileged-lookup case `rls_bypass` exists for (see
    # app/db/rls.py) — the same pattern the login/refresh flows use.
    async with rls_bypass(db):
        user = await db.get(User, user_id)

    if user is None or not user.is_active:
        raise UnauthorizedError(_INVALID_TOKEN)

    await set_tenant_context(db, user.organization_id)
    return user


async def get_current_super_admin(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authorization for `/api/v1/admin/*`. Self-contained by design: it
    both verifies the SUPER_ADMIN role AND enables RLS bypass for the rest
    of the request, in one dependency, so there is no ordering hazard with
    a sibling dependency needing bypass to already be active (a generic
    `require_permission(...)` run as a *separate* dependency alongside this
    one would not be guaranteed to execute after it — see the module-level
    note below for why permission checks for admin routes live here
    instead of being composed from `require_permission`).
    """
    if user.organization_id is not None:
        raise ForbiddenError("This action requires a platform administrator account.")

    async with rls_bypass(db):
        has_super_admin_role = await db.scalar(
            select(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user.id, Role.name == "SUPER_ADMIN")
        )

    if has_super_admin_role is None:
        raise ForbiddenError("This action requires a platform administrator account.")

    # Left ON deliberately: admin routes' own business logic (creating an
    # organization, listing all organizations) needs cross-tenant access
    # for the rest of this request.
    await set_rls_bypass(db, enabled=True)
    return user


def require_permission(
    code: str,
) -> Callable[[User, AsyncSession], Coroutine[None, None, User]]:
    """Authorization for `/api/v1/recruiter/*`: the caller must hold a role
    granted `code` in `role_permissions`. Safe to use as an independent
    sibling dependency here (unlike for admin routes) because
    `get_current_user` fully resolves tenant context *before* returning —
    there is no side effect left for a sibling to race against.
    """

    async def dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if code not in await granted_permission_codes(db, user):
            raise ForbiddenError("You do not have permission to perform this action.")
        return user

    return dependency


async def granted_permission_codes(db: AsyncSession, user: User) -> set[str]:
    """Every permission code the user's roles grant — the one definition
    `require_permission` and any "one of several permissions" check share."""
    result = await db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )
    return set(result.scalars().all())

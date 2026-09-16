"""Staff (User) authentication — login/refresh/logout.

Mirrors the candidate portal's own `/api/v1/candidate/auth/*` convention
(docs/api.md § 2) rather than inventing a separate top-level `/auth`
namespace. SUPER_ADMIN accounts authenticate here too — login is not
"recruiter business data," it's staff auth; the recruiter/admin split is
about authorization on what comes *after* login, not about the login
mechanism itself (see docs/architecture.md § 4).
"""

from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.db.rls import rls_bypass
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services import auth_service, user_service

router = APIRouter(prefix="/auth", tags=["recruiter-auth"])

_REFRESH_COOKIE_NAME = "refresh_token"
_REFRESH_COOKIE_PATH = "/api/v1/recruiter/auth"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=not settings.debug,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=_REFRESH_COOKIE_NAME,
        path=_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=not settings.debug,
        samesite="strict",
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await auth_service.authenticate(db, email=payload.email, password=payload.password)
    tokens = await auth_service.issue_tokens(db, user)

    _set_refresh_cookie(response, tokens.refresh_token)

    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.access_expires_in)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME),
) -> TokenResponse:
    if refresh_token is None:
        raise UnauthorizedError("Refresh token is invalid or expired.")

    _, tokens = await auth_service.rotate_refresh_token(db, refresh_token)

    _set_refresh_cookie(response, tokens.refresh_token)

    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.access_expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME),
) -> None:
    if refresh_token is not None:
        await auth_service.revoke_refresh_token(db, refresh_token)
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    # A SUPER_ADMIN's own user_roles row is only reachable through its own
    # user row, which normal (non-bypass) tenant-scoped RLS on `users`
    # deliberately hides — see app/api/deps.py::get_current_user, which
    # resolves the same principal's identity under an identical bypass for
    # the same reason ("who am I" is a privileged self-lookup, not a
    # tenant-scoped query, per app/db/rls.py::rls_bypass).
    async with rls_bypass(db):
        roles = await user_service.get_user_role_names(db, current_user.id)
    return UserResponse(
        id=current_user.id,
        organization_id=current_user.organization_id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        roles=roles,
    )

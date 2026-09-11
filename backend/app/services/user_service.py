import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.rbac import Role, UserRole
from app.models.user import User


async def create_tenant_user(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    email: str,
    password: str,
    full_name: str,
    role_name: str,
) -> User:
    """`organization_id` must come from the authenticated caller's own
    record — never from client input (see app/schemas/user.py). Runs under
    the caller's normal tenant-scoped RLS context; no bypass needed since
    the caller is only ever creating a user in their own tenant.
    """
    role = await db.scalar(select(Role).where(Role.organization_id.is_(None), Role.name == role_name))
    if role is None:
        raise NotFoundError(f"Role '{role_name}' does not exist.")

    user = User(
        organization_id=organization_id,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError("A user with this email already exists in this organization.") from exc

    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.flush()
    return user


async def list_organization_users(db: AsyncSession, organization_id: uuid.UUID) -> list[User]:
    result = await db.execute(
        select(User).where(User.organization_id == organization_id).order_by(User.created_at)
    )
    return list(result.scalars().all())


async def get_organization_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """RLS scopes this to the caller's own tenant automatically — a
    cross-tenant id simply isn't visible, so this returns None exactly as
    if the row didn't exist (see docs/security.md § 2: 404, not 403, for
    cross-tenant access attempts)."""
    return await db.get(User, user_id)


async def get_user_role_names(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return list(result.scalars().all())

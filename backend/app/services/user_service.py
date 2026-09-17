import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.schemas.user import UserUpdateRequest
from app.services import activity_service

_ORG_ADMIN_ROLE = "ORG_ADMIN"


async def create_tenant_user(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    email: str,
    password: str,
    full_name: str,
    role_name: str,
    actor: User | None = None,
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

    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="USER_CREATED",
        entity_type="user",
        entity_id=user.id,
        entity_label=f"{full_name} ({email})",
        description=f"Team member {full_name} was added with role {role_name}.",
    )
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


async def _count_other_active_org_admins(
    db: AsyncSession, *, organization_id: uuid.UUID, exclude_user_id: uuid.UUID
) -> int:
    """Used to guard against leaving an organization with no ORG_ADMIN who
    can manage it (QA § 4)."""
    count = await db.scalar(
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.organization_id == organization_id,
            User.is_active.is_(True),
            User.id != exclude_user_id,
            Role.name == _ORG_ADMIN_ROLE,
        )
    )
    return count or 0


async def deactivate_user(
    db: AsyncSession, *, actor: User, target: User, reason: str | None
) -> User:
    """Deactivation, never a hard delete — a team member may have created
    jobs/assessments/campus drives (`created_by` is ON DELETE RESTRICT on
    every one of those), so removing the row outright is both unsafe and,
    for any account with history, impossible anyway. Deactivating instead
    preserves that history and simply revokes login (`get_current_user`
    rejects `is_active=False`)."""
    if target.id == actor.id:
        raise ConflictError("You cannot deactivate your own account.")
    if not target.is_active:
        raise ConflictError("This team member is already deactivated.")

    target_roles = await get_user_role_names(db, target.id)
    if _ORG_ADMIN_ROLE in target_roles:
        assert target.organization_id is not None
        remaining = await _count_other_active_org_admins(
            db, organization_id=target.organization_id, exclude_user_id=target.id
        )
        if remaining < 1:
            raise ConflictError(
                "Cannot deactivate the organization's last admin — promote another "
                "team member to Org Admin first."
            )

    target.is_active = False
    await db.flush()

    assert target.organization_id is not None
    await activity_service.record_activity(
        db,
        organization_id=target.organization_id,
        actor=actor,
        action="USER_DEACTIVATED",
        entity_type="user",
        entity_id=target.id,
        entity_label=f"{target.full_name} ({target.email})",
        description=f"Team member {target.full_name} was deactivated.",
        reason=reason,
    )
    return target


async def reactivate_user(db: AsyncSession, *, actor: User, target: User) -> User:
    if target.is_active:
        raise ConflictError("This team member is already active.")

    target.is_active = True
    await db.flush()

    assert target.organization_id is not None
    await activity_service.record_activity(
        db,
        organization_id=target.organization_id,
        actor=actor,
        action="USER_REACTIVATED",
        entity_type="user",
        entity_id=target.id,
        entity_label=f"{target.full_name} ({target.email})",
        description=f"Team member {target.full_name} was reactivated.",
    )
    return target


async def change_user_role(db: AsyncSession, *, actor: User, target: User, new_role_name: str) -> User:
    current_roles = await get_user_role_names(db, target.id)
    if new_role_name in current_roles:
        return target

    if _ORG_ADMIN_ROLE in current_roles and new_role_name != _ORG_ADMIN_ROLE:
        assert target.organization_id is not None
        remaining = await _count_other_active_org_admins(
            db, organization_id=target.organization_id, exclude_user_id=target.id
        )
        if remaining < 1:
            raise ConflictError(
                "Cannot change the organization's last admin's role — promote another "
                "team member to Org Admin first."
            )

    role = await db.scalar(select(Role).where(Role.organization_id.is_(None), Role.name == new_role_name))
    if role is None:
        raise NotFoundError(f"Role '{new_role_name}' does not exist.")

    await db.execute(delete(UserRole).where(UserRole.user_id == target.id))
    db.add(UserRole(user_id=target.id, role_id=role.id))
    await db.flush()

    assert target.organization_id is not None
    old_role_label = ", ".join(current_roles) or "no role"
    await activity_service.record_activity(
        db,
        organization_id=target.organization_id,
        actor=actor,
        action="USER_ROLE_CHANGED",
        entity_type="user",
        entity_id=target.id,
        entity_label=f"{target.full_name} ({target.email})",
        description=(
            f"Team member {target.full_name}'s role changed from "
            f"{old_role_label} to {new_role_name}."
        ),
    )
    return target


async def update_team_member(
    db: AsyncSession, *, actor: User, target: User, payload: UserUpdateRequest
) -> User:
    """Single entry point the API uses for team management (QA § 4) —
    applies a role change and/or an active-state change from one PATCH,
    each fully guarded and audited by the functions above."""
    if payload.role is not None:
        target = await change_user_role(db, actor=actor, target=target, new_role_name=payload.role.value)

    if payload.is_active is not None and payload.is_active != target.is_active:
        if payload.is_active:
            target = await reactivate_user(db, actor=actor, target=target)
        else:
            target = await deactivate_user(db, actor=actor, target=target, reason=payload.reason)

    return target

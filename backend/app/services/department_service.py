import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.team_hierarchy import Department, Employee
from app.models.user import User
from app.schemas.team_hierarchy import DepartmentCreateRequest, DepartmentUpdateRequest
from app.services import activity_service


async def create_department(
    db: AsyncSession, *, organization_id: uuid.UUID, actor: User, payload: DepartmentCreateRequest
) -> Department:
    department = Department(
        organization_id=organization_id, name=payload.name, description=payload.description
    )
    db.add(department)
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="DEPARTMENT_CREATED",
        entity_type="department",
        entity_id=department.id,
        entity_label=department.name,
        description=f"Department \"{department.name}\" was created.",
    )
    return department


async def list_departments(db: AsyncSession, organization_id: uuid.UUID) -> list[Department]:
    result = await db.execute(
        select(Department)
        .where(Department.organization_id == organization_id, Department.deleted_at.is_(None))
        .order_by(Department.name)
    )
    return list(result.scalars().all())


async def get_department(db: AsyncSession, department_id: uuid.UUID) -> Department | None:
    return await db.get(Department, department_id)


async def count_active_employees(db: AsyncSession, department_id: uuid.UUID) -> int:
    count = await db.scalar(
        select(func.count(Employee.id)).where(
            Employee.department_id == department_id, Employee.deleted_at.is_(None)
        )
    )
    return count or 0


async def update_department(
    db: AsyncSession, department: Department, payload: DepartmentUpdateRequest, *, actor: User
) -> Department:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return department

    for field, value in updates.items():
        setattr(department, field, value)
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=department.organization_id,
        actor=actor,
        action="DEPARTMENT_UPDATED",
        entity_type="department",
        entity_id=department.id,
        entity_label=department.name,
        description=f"Department \"{department.name}\" was updated ({', '.join(sorted(updates))}).",
    )
    return department


async def delete_department(
    db: AsyncSession, department: Department, *, actor: User, reason: str
) -> Department:
    """Refuses to delete a department that still has active employees
    (CLAUDE.md § 10) — employees must be moved to another department or
    deactivated first, never silently orphaned or destroyed."""
    if department.deleted_at is not None:
        raise ConflictError("This department has already been deleted.")

    active_employees = await count_active_employees(db, department.id)
    if active_employees > 0:
        raise ConflictError(
            f"This department still has {active_employees} employee(s) assigned. "
            "Move them to another department before deleting it."
        )

    department.deleted_at = datetime.now(UTC)
    department.deleted_by_user_id = actor.id
    department.deletion_reason = reason
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=department.organization_id,
        actor=actor,
        action="DEPARTMENT_DELETED",
        entity_type="department",
        entity_id=department.id,
        entity_label=department.name,
        description=f"Department \"{department.name}\" was deleted.",
        reason=reason,
    )
    return department

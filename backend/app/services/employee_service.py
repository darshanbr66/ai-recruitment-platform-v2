import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.team_hierarchy import Department, Employee, EmploymentStatus
from app.models.user import User
from app.schemas.team_hierarchy import EmployeeCreateRequest, EmployeeUpdateRequest
from app.services import activity_service


async def create_employee(
    db: AsyncSession, *, organization_id: uuid.UUID, actor: User, payload: EmployeeCreateRequest
) -> Employee:
    employee = Employee(
        organization_id=organization_id,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        employee_code=payload.employee_code,
        designation=payload.designation,
        department_id=payload.department_id,
        manager_id=payload.manager_id,
        joining_date=payload.joining_date,
        location=payload.location,
        user_id=payload.user_id,
        created_by=actor.id,
    )
    db.add(employee)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "An employee with this email already exists in this organization."
        ) from exc

    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="EMPLOYEE_CREATED",
        entity_type="employee",
        entity_id=employee.id,
        entity_label=f"{employee.full_name} ({employee.email})",
        description=f"Employee {employee.full_name} was added.",
    )
    return employee


async def list_employees(
    db: AsyncSession, organization_id: uuid.UUID, *, department_id: uuid.UUID | None = None
) -> list[Employee]:
    query = (
        select(Employee)
        .where(Employee.organization_id == organization_id, Employee.deleted_at.is_(None))
        .order_by(Employee.full_name)
    )
    if department_id is not None:
        query = query.where(Employee.department_id == department_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_employee(db: AsyncSession, employee_id: uuid.UUID) -> Employee | None:
    return await db.get(Employee, employee_id)


async def get_department_names_for(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Small helper for denormalizing `department_name`/`manager_name` on
    `EmployeeResponse` — a single lookup for the department table, one for
    the (self-referential) employee table, both callable with whatever id
    set the response layer already has in hand."""
    if not ids:
        return {}
    result = await db.execute(select(Department.id, Department.name).where(Department.id.in_(ids)))
    return dict(result.tuples().all())


async def get_employee_names_for(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    result = await db.execute(select(Employee.id, Employee.full_name).where(Employee.id.in_(ids)))
    return dict(result.tuples().all())


async def update_employee(
    db: AsyncSession, employee: Employee, payload: EmployeeUpdateRequest, *, actor: User
) -> Employee:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return employee

    for field, value in updates.items():
        setattr(employee, field, value)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "An employee with this email already exists in this organization."
        ) from exc

    await activity_service.record_activity(
        db,
        organization_id=employee.organization_id,
        actor=actor,
        action="EMPLOYEE_UPDATED",
        entity_type="employee",
        entity_id=employee.id,
        entity_label=employee.full_name,
        description=f"Employee {employee.full_name} was updated ({', '.join(sorted(updates))}).",
    )
    return employee


async def move_employee(
    db: AsyncSession, employee: Employee, *, new_department_id: uuid.UUID | None, actor: User
) -> Employee:
    if new_department_id == employee.department_id:
        return employee

    if new_department_id is not None:
        department = await db.get(Department, new_department_id)
        if department is None or department.deleted_at is not None:
            raise NotFoundError("Department not found.")
        new_department_name = department.name
    else:
        new_department_name = "no department"

    old_department_name = "no department"
    if employee.department_id is not None:
        old_department = await db.get(Department, employee.department_id)
        if old_department is not None:
            old_department_name = old_department.name

    employee.department_id = new_department_id
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=employee.organization_id,
        actor=actor,
        action="EMPLOYEE_MOVED",
        entity_type="employee",
        entity_id=employee.id,
        entity_label=employee.full_name,
        description=(
            f"Employee {employee.full_name} was moved from {old_department_name} to "
            f"{new_department_name}."
        ),
    )
    return employee


async def deactivate_employee(
    db: AsyncSession, employee: Employee, *, actor: User, reason: str | None
) -> Employee:
    if employee.employment_status == EmploymentStatus.INACTIVE:
        raise ConflictError("This employee is already inactive.")

    employee.employment_status = EmploymentStatus.INACTIVE
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=employee.organization_id,
        actor=actor,
        action="EMPLOYEE_DEACTIVATED",
        entity_type="employee",
        entity_id=employee.id,
        entity_label=employee.full_name,
        description=f"Employee {employee.full_name} was deactivated.",
        reason=reason,
    )
    return employee


async def reactivate_employee(db: AsyncSession, employee: Employee, *, actor: User) -> Employee:
    if employee.employment_status == EmploymentStatus.ACTIVE:
        raise ConflictError("This employee is already active.")

    employee.employment_status = EmploymentStatus.ACTIVE
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=employee.organization_id,
        actor=actor,
        action="EMPLOYEE_REACTIVATED",
        entity_type="employee",
        entity_id=employee.id,
        entity_label=employee.full_name,
        description=f"Employee {employee.full_name} was reactivated.",
    )
    return employee

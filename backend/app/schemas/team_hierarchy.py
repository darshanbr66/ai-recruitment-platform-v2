import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.team_hierarchy import EmploymentStatus


class DepartmentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class DepartmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class DepartmentDeleteRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Computed by the service layer, not a Department column — active
    # (non-deleted) employees currently assigned to this department.
    employee_count: int = 0


class EmployeeCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    employee_code: str | None = Field(default=None, max_length=50)
    designation: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    joining_date: date | None = None
    location: str | None = Field(default=None, max_length=255)
    user_id: uuid.UUID | None = None


class EmployeeUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    employee_code: str | None = Field(default=None, max_length=50)
    designation: str | None = Field(default=None, max_length=255)
    manager_id: uuid.UUID | None = None
    joining_date: date | None = None
    location: str | None = Field(default=None, max_length=255)
    user_id: uuid.UUID | None = None


class EmployeeMoveRequest(BaseModel):
    department_id: uuid.UUID | None = None


class EmployeeDeactivateRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    phone: str | None
    employee_code: str | None
    designation: str | None
    department_id: uuid.UUID | None
    manager_id: uuid.UUID | None
    joining_date: date | None
    location: str | None
    employment_status: EmploymentStatus
    user_id: uuid.UUID | None
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Denormalized for list/detail views, like ApplicationResponse's
    # candidate_full_name/job_title (app/schemas/application.py).
    department_name: str | None = None
    manager_name: str | None = None

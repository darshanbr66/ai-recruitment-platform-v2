"""Import every model module here so `Base.metadata` is fully populated for
Alembic autogenerate and for `Base.metadata.create_all()` in tests.
"""

from app.models.application import (
    Application,
    ApplicationSource,
    ApplicationStatus,
    ApplicationStatusHistory,
)
from app.models.candidate import Candidate, CandidateSource
from app.models.job import Job, JobStatus
from app.models.organization import Organization
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User, UserRefreshToken

__all__ = [
    "Organization",
    "User",
    "UserRefreshToken",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    "Candidate",
    "CandidateSource",
    "Job",
    "JobStatus",
    "Application",
    "ApplicationSource",
    "ApplicationStatus",
    "ApplicationStatusHistory",
]

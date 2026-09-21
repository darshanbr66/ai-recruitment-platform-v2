"""Import every model module here so `Base.metadata` is fully populated for
Alembic autogenerate and for `Base.metadata.create_all()` in tests.
"""

from app.models.activity import Activity
from app.models.application import (
    Application,
    ApplicationSource,
    ApplicationStatus,
    ApplicationStatusHistory,
)
from app.models.assessment import (
    Assessment,
    AssessmentInvitation,
    AssessmentMonitoringEvent,
    AssessmentResult,
    CandidateAnswer,
    InvitationStatus,
    MonitoringEventType,
    Question,
    QuestionOption,
    QuestionType,
)
from app.models.campus_drive import CampusDrive, CampusDriveStatus
from app.models.candidate import Candidate, CandidateSource
from app.models.job import Job, JobStatus
from app.models.note import Note
from app.models.notification import Notification, NotificationType
from app.models.organization import Organization
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.resume import Resume
from app.models.screening import ScreeningRun, ScreeningStatus
from app.models.team_hierarchy import Department, Employee, EmploymentStatus
from app.models.user import User, UserRefreshToken

__all__ = [
    "Activity",
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
    "Resume",
    "ScreeningRun",
    "ScreeningStatus",
    "Assessment",
    "Question",
    "QuestionType",
    "QuestionOption",
    "AssessmentInvitation",
    "InvitationStatus",
    "CandidateAnswer",
    "AssessmentResult",
    "AssessmentMonitoringEvent",
    "MonitoringEventType",
    "CampusDrive",
    "CampusDriveStatus",
    "Note",
    "Notification",
    "NotificationType",
    "Department",
    "Employee",
    "EmploymentStatus",
]

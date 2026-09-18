from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.campus_drive import CampusDriveStatus


class PublicCampusDriveView(BaseModel):
    kind: Literal["drive"] = "drive"
    name: str
    college_name: str
    description: str | None
    job_title: str
    job_description: str
    organization_name: str
    registration_deadline: date | None
    status: CampusDriveStatus
    has_assessment: bool


class PublicCampusDriveUnavailable(BaseModel):
    """Returned instead of `PublicCampusDriveView` once a drive is CLOSED
    (SIGVITAS platform overhaul § 16) — deliberately carries no JD, drive
    description, or assessment info, so an old shared link never leaks
    recruitment content after the drive stops accepting applications. A
    DRAFT/deleted/unknown token stays a 404 (see
    public_campus_drive_service.get_drive_by_token) rather than this shape,
    since those are "this link never worked / no longer exists," not "this
    drive existed and is now closed."
    """

    kind: Literal["unavailable"] = "unavailable"
    message: str = (
        "This campus recruitment drive has been closed and is no longer "
        "accepting applications."
    )


class PublicCampusDriveApplicationResult(BaseModel):
    application_id: str
    job_title: str
    candidate_email: str
    status: str
    assessment_invitation_link: str | None

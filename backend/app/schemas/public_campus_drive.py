from datetime import date

from pydantic import BaseModel

from app.models.campus_drive import CampusDriveStatus


class PublicCampusDriveView(BaseModel):
    name: str
    college_name: str
    description: str | None
    job_title: str
    job_description: str
    organization_name: str
    registration_deadline: date | None
    status: CampusDriveStatus
    has_assessment: bool


class PublicCampusDriveApplicationResult(BaseModel):
    application_id: str
    job_title: str
    candidate_email: str
    status: str
    assessment_invitation_link: str | None

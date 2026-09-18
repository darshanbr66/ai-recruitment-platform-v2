import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PublicOrganizationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str


class PublicJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    department: str | None
    location: str | None
    employment_type: str | None
    openings_count: int
    created_at: datetime


class PublicJobDetail(PublicJobSummary):
    # None when the recruiter has hidden the JD from the public listing —
    # the text itself is never deleted (app/models/job.py::description_visible),
    # this is a presentation omission enforced here, not just in the UI.
    description: str | None
    organization: PublicOrganizationSummary


class PublicApplicationResult(BaseModel):
    id: uuid.UUID
    job_title: str
    candidate_email: str
    status: str
    submitted_at: datetime

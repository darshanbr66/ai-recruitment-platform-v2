import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PublicOrganizationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    # The recruitment team's published contact address (None = not
    # published). Candidate-facing copy reads it from here, never from a
    # hardcoded constant.
    careers_contact_email: str | None = None


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


class PublicApplicationOutcome(StrEnum):
    """What the candidate is told — deliberately coarse. Never carries the
    AI's reasoning, score, model or the internal status name."""

    #: In the pipeline for recruiter review (AI matched, or AI unavailable).
    RECEIVED = "RECEIVED"
    #: The submission-time screening found the profile doesn't meet this
    #: role's requirements; the profile is retained for other roles.
    NOT_SHORTLISTED_FOR_ROLE = "NOT_SHORTLISTED_FOR_ROLE"


class PublicApplicationResult(BaseModel):
    id: uuid.UUID
    job_title: str
    candidate_email: str
    outcome: PublicApplicationOutcome
    #: True only when the email provider actually accepted the confirmation
    #: email — the UI must never claim an email that wasn't sent.
    confirmation_email_sent: bool
    careers_contact_email: str | None
    submitted_at: datetime


class EmailVerificationRequest(BaseModel):
    email: EmailStr


class EmailVerificationRequested(BaseModel):
    expires_in_seconds: int
    resend_available_in_seconds: int


class EmailVerificationConfirm(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)


class EmailVerificationConfirmed(BaseModel):
    verification_token: str
    expires_at: datetime

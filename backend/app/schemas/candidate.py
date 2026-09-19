import uuid
from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.candidate import CandidateSource, CandidateType


def _blank_to_none(value: object) -> object:
    """Form submissions and cleared inputs send "" for "not provided"."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


BlankToNone = BeforeValidator(_blank_to_none)


def _normalize_profile_url(value: str | None, *, allowed_hosts: tuple[str, ...]) -> str | None:
    """Accepts `linkedin.com/in/x` as well as a full URL; rejects anything
    that isn't http(s) on the expected site, so this field can never hold a
    `javascript:` URL that a recruiter UI might later render as a link."""
    if value is None:
        return None
    candidate = value if "://" in value else f"https://{value}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not any(
        host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts
    ):
        raise ValueError(f"Must be a valid {allowed_hosts[0]} URL.")
    return candidate


class CandidateProfileFields(BaseModel):
    """Reusable profile data shared by the public application form and the
    recruiter create/update requests. `location` is the *current*
    location."""

    location: Annotated[str | None, BlankToNone] = Field(default=None, max_length=255)
    current_title: Annotated[str | None, BlankToNone] = Field(default=None, max_length=255)
    current_company: Annotated[str | None, BlankToNone] = Field(default=None, max_length=255)
    preferred_location: Annotated[str | None, BlankToNone] = Field(default=None, max_length=255)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    candidate_type: CandidateType | None = None
    notice_period_days: int | None = Field(default=None, ge=0, le=365)
    immediate_joiner: bool | None = None
    qualification: Annotated[str | None, BlankToNone] = Field(default=None, max_length=255)
    linkedin_url: Annotated[str | None, BlankToNone] = Field(default=None, max_length=500)
    github_url: Annotated[str | None, BlankToNone] = Field(default=None, max_length=500)

    # Field validators (not a model validator) so a rejected URL is reported
    # against its own field, and so they only run for values actually
    # supplied — which keeps `exclude_unset` PATCH semantics intact.
    @field_validator("linkedin_url")
    @classmethod
    def _check_linkedin_url(cls, value: str | None) -> str | None:
        return _normalize_profile_url(value, allowed_hosts=("linkedin.com",))

    @field_validator("github_url")
    @classmethod
    def _check_github_url(cls, value: str | None) -> str | None:
        return _normalize_profile_url(value, allowed_hosts=("github.com",))

    @model_validator(mode="after")
    def _immediate_joiner_has_no_notice_period(self) -> "CandidateProfileFields":
        if self.immediate_joiner:
            self.notice_period_days = 0
        return self


class PublicApplicantProfile(CandidateProfileFields):
    """The extra fields the *public* application form collects. Stricter
    than the base: once someone declares themselves EXPERIENCED we need
    their experience and availability, and a FRESHER carries 0 years of
    experience and no notice period. Nothing is required when
    `candidate_type` is omitted, which keeps the endpoint backward
    compatible with clients that only send name/email/resume."""

    @model_validator(mode="after")
    def _validate_by_candidate_type(self) -> "PublicApplicantProfile":
        if self.candidate_type == CandidateType.EXPERIENCED:
            if self.years_experience is None:
                raise ValueError("Years of experience is required for experienced candidates.")
            if self.notice_period_days is None and not self.immediate_joiner:
                raise ValueError(
                    "Notice period is required for experienced candidates "
                    "unless they are an immediate joiner."
                )
        elif self.candidate_type == CandidateType.FRESHER:
            if self.years_experience is None:
                self.years_experience = 0
            self.notice_period_days = None
            self.immediate_joiner = None
        return self


class CandidateCreateRequest(CandidateProfileFields):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    source: CandidateSource = CandidateSource.RECRUITER_ADDED


class CandidateUpdateRequest(CandidateProfileFields):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class CandidateDeleteRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    location: str | None
    current_title: str | None
    current_company: str | None
    preferred_location: str | None
    years_experience: int | None
    candidate_type: CandidateType | None
    notice_period_days: int | None
    immediate_joiner: bool | None
    qualification: str | None
    linkedin_url: str | None
    github_url: str | None
    source: CandidateSource
    is_active: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

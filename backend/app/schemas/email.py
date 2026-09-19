from pydantic import BaseModel, EmailStr, Field, model_validator

from app.email_templates import EmailTemplateKey


class EmailTemplateFieldResponse(BaseModel):
    key: str
    label: str
    input_type: str
    required: bool
    options: list[str]
    placeholder: str


class EmailTemplateResponse(BaseModel):
    key: EmailTemplateKey
    name: str
    description: str
    # Inputs when sent for an application (candidate/job come from the record).
    fields: list[EmailTemplateFieldResponse]
    # Inputs when sent as a general email with no application, where the
    # recipient name and role must be typed. None = this template needs an
    # application (the assessment invitation) and can't be sent that way.
    general_fields: list[EmailTemplateFieldResponse] | None


class EmailComposeRequest(BaseModel):
    """Load a template. `variables` are the values of that template's own
    fields (e.g. the interview date) — company and recruiter details (and, for
    an application, the candidate and job) are filled in by the server."""

    template_key: EmailTemplateKey
    variables: dict[str, str] = Field(default_factory=dict)


class EmailComposeResponse(BaseModel):
    template_key: EmailTemplateKey
    subject: str
    body: str
    variables: dict[str, str]
    # Required template fields that have no value yet; their placeholders
    # are still visible in `body` and must be filled before sending.
    missing_required: list[str]


class EmailDraftRequest(BaseModel):
    """The email exactly as the recruiter has it in the composer, possibly
    edited. Used for both preview and send so the two can never differ."""

    template_key: EmailTemplateKey
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)
    variables: dict[str, str] = Field(default_factory=dict)


class EmailPreviewResponse(BaseModel):
    to: str
    reply_to: str
    subject: str
    html: str
    text: str
    has_call_to_action: bool


class EmailSendResponse(BaseModel):
    sent: bool
    to: str
    subject: str


# --- general email (no application) --------------------------------------

# Generous for a recruiting team, small enough that this can't be turned into
# a bulk-mailer through the company's SMTP account.
MAX_RECIPIENTS_PER_FIELD = 10
MAX_RECIPIENTS_TOTAL = 20


class GeneralEmailDraftRequest(EmailDraftRequest):
    """A draft plus the recipients the sender typed. Every address is
    validated and reduced to a bare email address (a pasted `Name <a@b.com>`
    keeps only `a@b.com`; anything containing line breaks or extra syntax is
    rejected, so nothing can smuggle in extra headers or recipients),
    de-duplicated case-insensitively across To/Cc/Bcc, and capped."""

    to: list[EmailStr] = Field(min_length=1, max_length=MAX_RECIPIENTS_PER_FIELD)
    cc: list[EmailStr] = Field(default_factory=list, max_length=MAX_RECIPIENTS_PER_FIELD)
    bcc: list[EmailStr] = Field(default_factory=list, max_length=MAX_RECIPIENTS_PER_FIELD)

    @model_validator(mode="after")
    def _dedupe_and_cap(self) -> "GeneralEmailDraftRequest":
        seen: set[str] = set()

        def unique(addresses: list[EmailStr]) -> list[EmailStr]:
            kept: list[EmailStr] = []
            for address in addresses:
                key = address.lower()
                if key not in seen:
                    seen.add(key)
                    kept.append(address)
            return kept

        self.to = unique(self.to)
        self.cc = unique(self.cc)
        self.bcc = unique(self.bcc)
        if len(seen) > MAX_RECIPIENTS_TOTAL:
            raise ValueError(f"An email can have at most {MAX_RECIPIENTS_TOTAL} recipients.")
        return self


class GeneralEmailPreviewResponse(BaseModel):
    to: list[str]
    cc: list[str]
    bcc: list[str]
    reply_to: str
    subject: str
    html: str
    text: str
    has_call_to_action: bool


class GeneralEmailSendResponse(BaseModel):
    sent: bool
    to: list[str]
    cc: list[str]
    bcc: list[str]
    subject: str

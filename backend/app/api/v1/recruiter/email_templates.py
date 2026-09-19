"""The predefined email templates. Read-only: templates are defined in code
(app/email_templates) so every organization starts from the same professional
defaults, and editing an email never alters a template."""

from fastapi import APIRouter, Depends

from app.api.deps import require_permission
from app.email_templates import TemplateField, list_templates
from app.models.user import User
from app.schemas.email import EmailTemplateFieldResponse, EmailTemplateResponse

router = APIRouter(prefix="/email-templates", tags=["recruiter-email-templates"])


def _field_response(field: TemplateField) -> EmailTemplateFieldResponse:
    return EmailTemplateFieldResponse(
        key=field.key,
        label=field.label,
        input_type=field.input_type,
        required=field.required,
        options=list(field.options),
        placeholder=field.placeholder,
    )


@router.get("", response_model=list[EmailTemplateResponse])
async def list_email_templates(
    _: User = Depends(require_permission("application.email.send")),
) -> list[EmailTemplateResponse]:
    return [
        EmailTemplateResponse(
            key=template.key,
            name=template.name,
            description=template.description,
            fields=[_field_response(field) for field in template.fields],
            general_fields=(
                None
                if template.general_fields is None
                else [_field_response(field) for field in template.general_fields]
            ),
        )
        for template in list_templates()
    ]

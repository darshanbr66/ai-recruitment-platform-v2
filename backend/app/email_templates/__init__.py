"""Candidate-email templates, placeholder resolution and the HTML layout.
Pure functions and constants — no database, no provider — so they can be
tested in isolation and reused by any future email surface."""

from app.email_templates.layout import RenderedEmail, is_safe_http_url, render_email
from app.email_templates.rendering import PLACEHOLDER_PATTERN, ResolvedText, resolve_placeholders
from app.email_templates.templates import (
    CONTEXT_PLACEHOLDERS,
    KNOWN_PLACEHOLDERS,
    CallToAction,
    EmailTemplate,
    EmailTemplateKey,
    TemplateField,
    get_template,
    list_templates,
)

__all__ = [
    "CONTEXT_PLACEHOLDERS",
    "KNOWN_PLACEHOLDERS",
    "PLACEHOLDER_PATTERN",
    "CallToAction",
    "EmailTemplate",
    "EmailTemplateKey",
    "RenderedEmail",
    "ResolvedText",
    "TemplateField",
    "get_template",
    "is_safe_http_url",
    "list_templates",
    "render_email",
    "resolve_placeholders",
]

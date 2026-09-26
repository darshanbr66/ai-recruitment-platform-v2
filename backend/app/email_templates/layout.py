"""The shared HTML (and plain-text) email layout used by every template.

Built for email clients, not browsers: nested ``role="presentation"``
tables, inline CSS only, web-safe font stack, a 600px container, a
"bulletproof" table-cell button, and no images, scripts or external
resources — so it renders the same in Gmail, Outlook and Apple Mail and
nothing can fail to load. One accent colour, everything else neutral.

Every piece of text is HTML-escaped; the only markup that ever reaches the
output is what this module writes itself. Links are limited to http(s).
"""

import re
from dataclasses import dataclass
from html import escape
from urllib.parse import urlparse

_ACCENT = "#1f3a5f"
_TEXT = "#1f2933"
_MUTED = "#6b7280"
_BORDER = "#e2e8f0"
_PAGE_BG = "#f4f5f7"
_CARD_BG = "#f7f9fb"
_FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

_KV_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9 /&'-]{0,30}):\s+(\S.*)$")
_BLOCK_SPLIT = re.compile(r"\n\s*\n")
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"]+")
_LIST_MARKERS = ("- ", "• ")


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


@dataclass(frozen=True)
class _Paragraph:
    lines: tuple[str, ...]


@dataclass(frozen=True)
class _Details:
    heading: str | None
    rows: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _Bullets:
    items: tuple[str, ...]


_Block = _Paragraph | _Details | _Bullets


def is_safe_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc) and " " not in value


def _parse_blocks(body: str) -> list[_Block]:
    blocks: list[_Block] = []
    for raw in _BLOCK_SPLIT.split(body.strip()):
        lines = [line.rstrip() for line in raw.split("\n") if line.strip()]
        if not lines:
            continue

        if all(line.lstrip().startswith(_LIST_MARKERS) for line in lines):
            blocks.append(_Bullets(tuple(line.lstrip()[2:].strip() for line in lines)))
            continue

        pairs = [_KV_LINE.match(line) for line in lines]
        if all(pairs):
            blocks.append(_Details(None, tuple((m.group(1), m.group(2)) for m in pairs if m)))
            continue

        heading = lines[0]
        rest = [_KV_LINE.match(line) for line in lines[1:]]
        if (
            rest
            and all(rest)
            and len(heading) <= 40
            and not heading.endswith((".", ",", "!", "?", ":"))
        ):
            blocks.append(_Details(heading, tuple((m.group(1), m.group(2)) for m in rest if m)))
            continue

        blocks.append(_Paragraph(tuple(lines)))
    return blocks


def _text(value: str) -> str:
    return escape(value, quote=False)


def _linkify(escaped: str) -> str:
    def replace(match: re.Match[str]) -> str:
        url = match.group(0)
        trailing = ""
        while url and url[-1] in ".,!?:)":
            trailing = url[-1] + trailing
            url = url[:-1]
        return f'<a href="{url}" style="color:{_ACCENT};text-decoration:underline;">{url}</a>{trailing}'

    return _URL_IN_TEXT.sub(replace, escaped)


def _rich(value: str) -> str:
    return _linkify(_text(value))


def _render_block(block: _Block) -> str:
    base = f"font-family:{_FONT};font-size:15px;line-height:1.6;color:{_TEXT};"
    if isinstance(block, _Paragraph):
        content = "<br>".join(_rich(line) for line in block.lines)
        return f'<p style="margin:0 0 18px 0;{base}">{content}</p>'

    if isinstance(block, _Bullets):
        items = "".join(f'<li style="margin:0 0 6px 0;">{_rich(item)}</li>' for item in block.items)
        return f'<ul style="margin:0 0 18px 0;padding-left:22px;{base}">{items}</ul>'

    rows = "".join(
        "<tr>"
        f'<td valign="top" style="padding:6px 16px 6px 0;width:130px;font-family:{_FONT};'
        f'font-size:14px;line-height:1.5;color:{_MUTED};">{_text(label)}</td>'
        f'<td valign="top" style="padding:6px 0;font-family:{_FONT};font-size:14px;'
        f'line-height:1.5;color:{_TEXT};font-weight:600;">{_rich(value)}</td>'
        "</tr>"
        for label, value in block.rows
    )
    heading = (
        f'<p style="margin:0 0 6px 0;font-family:{_FONT};font-size:13px;font-weight:700;'
        f'letter-spacing:0.04em;text-transform:uppercase;color:{_ACCENT};">{_text(block.heading)}</p>'
        if block.heading
        else ""
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:0 0 20px 0;"><tr><td bgcolor="{_CARD_BG}" '
        f'style="background:{_CARD_BG};border:1px solid {_BORDER};border-left:4px solid {_ACCENT};'
        f'padding:14px 18px;">{heading}'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">{rows}</table>'
        "</td></tr></table>"
    )


def _render_button(label: str, url: str) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="margin:8px 0 26px 0;"><tr>'
        f'<td align="center" bgcolor="{_ACCENT}" style="background:{_ACCENT};border-radius:4px;">'
        f'<a href="{escape(url, quote=True)}" target="_blank" '
        f'style="display:inline-block;padding:13px 28px;font-family:{_FONT};font-size:15px;'
        f'font-weight:600;color:#ffffff;text-decoration:none;">{_text(label)}</a>'
        "</td></tr></table>"
    )


def render_email(
    *,
    subject: str,
    body: str,
    company_name: str,
    recruiter_name: str,
    recruiter_email: str,
    job_title: str = "",
    cta_label: str | None = None,
    cta_url: str | None = None,
) -> RenderedEmail:
    """`body` is the already-resolved plain-text body. `job_title` is optional
    (a general email has no role) and only changes the footer wording. `cta_*` add the
    button (and a plain-text link line); both must be present and the URL
    http(s), otherwise no button is rendered. An empty `recruiter_email`
    (a system email for an organization that publishes no contact address)
    drops the "contact ... at" line rather than rendering a blank address."""
    has_cta = bool(cta_label and cta_url and is_safe_http_url(cta_url))
    reason = (
        f"You are receiving this message regarding your application for {job_title} at {company_name}."
        if job_title
        else f"You are receiving this message from {company_name}."
    )

    content = "".join(_render_block(block) for block in _parse_blocks(body))
    if has_cta:
        content += _render_button(cta_label or "", cta_url or "")

    footer_small = f"font-family:{_FONT};font-size:12px;line-height:1.6;color:{_MUTED};"
    contact = (
        f"Questions? Reply to this email or contact {_text(recruiter_name)} at "
        f'<a href="mailto:{escape(recruiter_email, quote=True)}" '
        f'style="color:{_ACCENT};text-decoration:underline;">{_text(recruiter_email)}</a>.'
        if recruiter_email
        else ""
    )
    contact_html = f'<p style="margin:0 0 6px 0;{footer_small}">{contact}</p>' if contact else ""

    html = (
        "<!DOCTYPE html>"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">'
        f"<title>{_text(subject)}</title></head>"
        f'<body style="margin:0;padding:0;background:{_PAGE_BG};">'
        '<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">'
        f"{_text(subject)}</div>"
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'bgcolor="{_PAGE_BG}"><tr><td align="center" style="padding:24px 12px;">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        f'style="width:100%;max-width:600px;background:#ffffff;border:1px solid {_BORDER};">'
        f'<tr><td bgcolor="{_ACCENT}" style="background:{_ACCENT};padding:24px 32px;'
        f'font-family:{_FONT};font-size:20px;font-weight:600;color:#ffffff;">{_text(company_name)}</td></tr>'
        f'<tr><td style="padding:32px 32px 14px 32px;">{content}</td></tr>'
        f'<tr><td style="padding:20px 32px;border-top:1px solid {_BORDER};background:{_CARD_BG};">'
        f'<p style="margin:0 0 6px 0;{footer_small}"><strong style="color:{_TEXT};">'
        f"{_text(recruiter_name)}</strong> · {_text(company_name)}</p>"
        f"{contact_html}"
        f'<p style="margin:0;{footer_small}">{_text(reason)}</p>'
        "</td></tr></table></td></tr></table></body></html>"
    )

    text_parts = [body.strip()]
    if has_cta:
        text_parts.append(f"{cta_label}: {cta_url}")
    contact_text = (
        f"Questions? Reply to this email or contact {recruiter_email}.\n" if recruiter_email else ""
    )
    text_parts.append(f"--\n{recruiter_name} | {company_name}\n{contact_text}{reason}")
    return RenderedEmail(subject=subject, html=html, text="\n\n".join(text_parts))

"""Real resume text extraction (CLAUDE.md § 5: no fake implementations) —
PDF via pypdf, DOCX via python-docx. `.doc` (legacy binary Word format) has
no lightweight pure-Python reader and is rejected with a clear error rather
than silently returning garbage or empty text.
"""

import io

from docx import Document
from pypdf import PdfReader

from app.integrations.ai.base import AIProviderError


def extract_resume_text(*, content: bytes, filename: str) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if suffix == "pdf":
        return _extract_pdf(content)
    if suffix == "docx":
        return _extract_docx(content)
    if suffix == "doc":
        raise AIProviderError(
            "Legacy .doc files can't be read for screening — ask the candidate to "
            "resubmit as PDF or DOCX."
        )
    raise AIProviderError(f"Unsupported resume file type for screening: .{suffix}")


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # pypdf raises a variety of exception types
        raise AIProviderError(f"Could not extract text from this PDF: {exc}") from exc

    text = text.strip()
    if not text:
        raise AIProviderError(
            "No extractable text found in this PDF (it may be a scanned image)."
        )
    return text


def _extract_docx(content: bytes) -> str:
    try:
        document = Document(io.BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:
        raise AIProviderError(f"Could not extract text from this DOCX: {exc}") from exc

    text = text.strip()
    if not text:
        raise AIProviderError("No extractable text found in this DOCX file.")
    return text

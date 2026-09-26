import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.integrations.storage import ResumeStorage, StorageError
from app.models.resume import Resume
from app.services import resume_chunking_service

_PDF_MAGIC = b"%PDF-"
# File signatures for the staff-upload types: DOCX is a ZIP container,
# legacy DOC an OLE2 compound file.
_MAGIC_BY_SUFFIX = {
    ".pdf": _PDF_MAGIC,
    ".docx": b"PK\x03\x04",
    ".doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
}


def validate_resume_upload(*, filename: str, content: bytes, pdf_only: bool = False) -> None:
    """`pdf_only` is the public careers-site rule (the AI screening reads
    the PDF): the extension must be .pdf *and* the bytes must actually be a
    PDF — a renamed executable or document is rejected, not stored."""
    settings = get_settings()
    suffix = Path(filename).suffix.lower()
    if pdf_only:
        if suffix != ".pdf":
            raise AppError("Please upload your resume as a PDF file.", code="invalid_file_type")
    elif suffix not in settings.allowed_resume_extensions:
        allowed = ", ".join(settings.allowed_resume_extensions)
        raise AppError(f"Resume must be one of: {allowed}.", code="invalid_file_type")

    max_bytes = settings.max_resume_size_mb * 1024 * 1024
    if len(content) == 0:
        raise AppError("The uploaded resume is empty.", code="invalid_file")
    if len(content) > max_bytes:
        raise AppError(
            f"Resume must be smaller than {settings.max_resume_size_mb}MB.",
            code="file_too_large",
        )
    if pdf_only and not content.lstrip()[:5].startswith(_PDF_MAGIC):
        raise AppError(
            "The uploaded file is not a valid PDF document.", code="invalid_file_type"
        )
    # Staff uploads may be any allowed type, but the bytes must still be what
    # the extension claims — a renamed executable is never stored.
    magic = _MAGIC_BY_SUFFIX.get(suffix)
    if not pdf_only and magic is not None and not content.lstrip()[: len(magic)].startswith(magic):
        raise AppError(
            f"The uploaded file is not a valid {suffix.lstrip('.').upper()} document.",
            code="invalid_file_type",
        )


async def save_resume(
    db: AsyncSession,
    storage: ResumeStorage,
    *,
    organization_id: uuid.UUID,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    original_filename: str,
    content_type: str,
    content: bytes,
    uploaded_by_user_id: uuid.UUID | None = None,
    pdf_only: bool = False,
) -> Resume:
    validate_resume_upload(filename=original_filename, content=content, pdf_only=pdf_only)

    try:
        saved = await storage.save(
            organization_id=organization_id,
            candidate_id=candidate_id,
            application_id=application_id,
            original_filename=original_filename,
            content_type=content_type,
            content=content,
            uploaded_by_user_id=uploaded_by_user_id,
        )
    except StorageError as exc:
        raise AppError(str(exc), code="storage_error") from exc

    resume = Resume(
        organization_id=organization_id,
        candidate_id=candidate_id,
        application_id=application_id,
        original_filename=original_filename,
        stored_filename=saved.stored_filename,
        storage_path=saved.storage_path,
        storage_provider=saved.storage_provider,
        content_type=content_type,
        size_bytes=saved.size_bytes,
    )
    db.add(resume)
    await db.flush()

    # Best-effort, inline (no background worker is provisioned yet — see
    # resume_chunking_service.py's module docstring): feeds the internal AI
    # matching engine's semantic retrieval. Never fails the upload itself.
    await resume_chunking_service.chunk_and_embed_resume(db, resume)
    return resume


async def get_latest_resume_for_candidate(
    db: AsyncSession, candidate_id: uuid.UUID
) -> Resume | None:
    result = await db.execute(
        select(Resume)
        .where(Resume.candidate_id == candidate_id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def link_existing_resume(
    db: AsyncSession, *, source: Resume, application_id: uuid.UUID
) -> Resume:
    """Attaches a candidate's already-stored resume to another of their
    applications (an HR job match) — a new metadata row pointing at the
    *same* stored file, so the file is neither copied nor re-uploaded, and
    download/preview/screening work for the new application unchanged.
    Stored resume files are never deleted by the application, so sharing
    one between rows is safe. Not re-chunked: the candidate's resume text is
    already embedded once under the original row."""
    resume = Resume(
        organization_id=source.organization_id,
        candidate_id=source.candidate_id,
        application_id=application_id,
        original_filename=source.original_filename,
        stored_filename=source.stored_filename,
        storage_path=source.storage_path,
        storage_provider=source.storage_provider,
        content_type=source.content_type,
        size_bytes=source.size_bytes,
    )
    db.add(resume)
    await db.flush()
    return resume

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.integrations.storage import ResumeStorage, StorageError
from app.models.resume import Resume


def validate_resume_upload(*, filename: str, content: bytes) -> None:
    settings = get_settings()
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.allowed_resume_extensions:
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
) -> Resume:
    validate_resume_upload(filename=original_filename, content=content)

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
    return resume

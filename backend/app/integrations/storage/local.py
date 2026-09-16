import uuid
from pathlib import Path

import anyio

from app.core.config import get_settings
from app.integrations.storage.base import ResumeStorage, SavedFile, StorageError


class LocalResumeStorage(ResumeStorage):
    """Local-disk implementation for development (CLAUDE.md § 3: "local disk
    now, S3-compatible later"). Files live under
    `settings.resume_storage_dir/<organization_id>/<uuid><ext>` — the stored
    filename is always server-generated, never derived from the client's
    original filename, so there is no path-traversal surface and no
    filename-collision risk.
    """

    def __init__(self, *, root: Path | None = None) -> None:
        settings = get_settings()
        self._root = root or Path(settings.resume_storage_dir)

    async def save(
        self, *, organization_id: uuid.UUID, original_filename: str, content: bytes
    ) -> SavedFile:
        suffix = Path(original_filename).suffix.lower()
        stored_filename = f"{uuid.uuid4()}{suffix}"
        org_dir = self._root / str(organization_id)

        try:
            await anyio.Path(org_dir).mkdir(parents=True, exist_ok=True)
            target = org_dir / stored_filename
            await anyio.Path(target).write_bytes(content)
        except OSError as exc:
            raise StorageError("Could not save the uploaded file.") from exc

        storage_path = f"{organization_id}/{stored_filename}"
        return SavedFile(
            stored_filename=stored_filename, storage_path=storage_path, size_bytes=len(content)
        )

    async def read(self, storage_path: str) -> bytes:
        target = self._resolve(storage_path)
        try:
            return await anyio.Path(target).read_bytes()
        except OSError as exc:
            raise StorageError("Could not read the stored file.") from exc

    def _resolve(self, storage_path: str) -> Path:
        """Resolves a stored `organization_id/uuid.ext` path against the
        storage root and refuses to serve anything that would escape it —
        defense in depth even though every `storage_path` we ever write is
        server-generated, never client-controlled."""
        candidate = (self._root / storage_path).resolve()
        root = self._root.resolve()
        if root not in candidate.parents:
            raise StorageError("Invalid storage path.")
        return candidate

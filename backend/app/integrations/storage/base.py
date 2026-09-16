import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass


class StorageError(Exception):
    """Raised for validation failures (bad extension, oversized file) and
    storage-layer I/O failures alike — callers treat both as "could not
    store this upload" (see app/api/v1/public/applications.py)."""


@dataclass(frozen=True)
class SavedFile:
    stored_filename: str
    storage_path: str
    size_bytes: int


class ResumeStorage(ABC):
    """One resume file per save; the caller owns the metadata row
    (app/models/resume.py). `storage_path` is opaque to callers — only the
    implementation that produced it knows how to resolve or read it back.
    """

    @abstractmethod
    async def save(
        self, *, organization_id: uuid.UUID, original_filename: str, content: bytes
    ) -> SavedFile: ...

    @abstractmethod
    async def read(self, storage_path: str) -> bytes: ...

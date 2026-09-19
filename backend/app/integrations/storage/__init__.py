"""File storage abstraction (CLAUDE.md § 3: "AI/embeddings are
provider-agnostic behind interfaces" — the same rule applies to storage).
Route/service code depends on `ResumeStorage`, never on `open()`/`Path` or
a MongoDB driver directly, so swapping implementations touches only this
package.

`get_resume_storage()` is the one place that decides which implementation
backs `ResumeStorage` for a request — selected by
`settings.resume_storage_provider` (RESUME_STORAGE_PROVIDER), not
hardcoded per route the way each router previously constructed
`LocalResumeStorage()` itself.
"""

from app.core.config import get_settings
from app.integrations.storage.base import ResumeFileMetadata, ResumeStorage, SavedFile, StorageError
from app.integrations.storage.local import LocalResumeStorage
from app.integrations.storage.mongo_gridfs import MongoGridFSResumeStorage

__all__ = [
    "ResumeStorage",
    "ResumeFileMetadata",
    "SavedFile",
    "StorageError",
    "LocalResumeStorage",
    "MongoGridFSResumeStorage",
    "get_resume_storage",
    "get_resume_storage_for_provider",
]

_PROVIDERS: dict[str, type[ResumeStorage]] = {
    "local": LocalResumeStorage,
    "mongodb_gridfs": MongoGridFSResumeStorage,
}


def get_resume_storage() -> ResumeStorage:
    """FastAPI dependency for *new* uploads: builds the implementation
    named by `settings.resume_storage_provider` — the provider a fresh
    Resume row will be written with. Cheap to construct per call;
    `MongoGridFSResumeStorage` only wraps the already-open process-wide
    Mongo client (app/db/mongo.py), it does not open a new connection.

    Do not use this to read back an *existing* Resume — its file may have
    been written under a since-changed default (CLAUDE.md task § 16:
    backward compatibility). Use `get_resume_storage_for_provider` with
    that row's own `storage_provider` instead.
    """
    settings = get_settings()
    return get_resume_storage_for_provider(settings.resume_storage_provider)


def get_resume_storage_for_provider(provider: str) -> ResumeStorage:
    """Resolves the `ResumeStorage` implementation for a specific,
    already-known provider name — what every read of an existing Resume
    row must use, keyed off that row's own `storage_provider` rather than
    the current default, so a record written by a previous configuration
    keeps resolving correctly."""
    try:
        return _PROVIDERS[provider]()
    except KeyError as exc:
        raise StorageError(f"Unknown resume storage provider: {provider!r}") from exc

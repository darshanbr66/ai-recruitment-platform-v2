"""File storage abstraction (CLAUDE.md § 3: "AI/embeddings are
provider-agnostic behind interfaces" — the same rule applies to storage).
Route/service code depends on `ResumeStorage`, never on `open()`/`Path`
directly, so swapping the local-disk implementation for an S3-compatible one
later touches only `local.py`, not any caller.
"""

from app.integrations.storage.base import ResumeStorage, SavedFile, StorageError
from app.integrations.storage.local import LocalResumeStorage

__all__ = ["ResumeStorage", "SavedFile", "StorageError", "LocalResumeStorage"]

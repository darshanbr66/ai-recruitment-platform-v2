"""MongoDB-related settings validation (app/core/config.py). Direct
`Settings(...)` construction, not the cached `get_settings()` singleton —
explicit init kwargs (including `None`) take priority over `.env`/process
env in pydantic-settings, so these are isolated from whatever
MONGODB_URI/RESUME_STORAGE_PROVIDER happen to be set in this machine's
backend/.env.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_REQUIRED = {
    "database_url": "postgresql+psycopg://user:pass@localhost:5432/db",
    "jwt_secret_key": "test-secret",
}


def test_mongodb_uri_required_when_provider_is_mongodb_gridfs() -> None:
    with pytest.raises(ValidationError, match="MONGODB_URI"):
        Settings(resume_storage_provider="mongodb_gridfs", mongodb_uri=None, **_REQUIRED)


def test_local_provider_does_not_require_mongodb_uri() -> None:
    settings = Settings(resume_storage_provider="local", mongodb_uri=None, **_REQUIRED)
    assert settings.resume_storage_provider == "local"
    assert settings.mongodb_uri is None


def test_mongodb_gridfs_provider_with_uri_configured_is_valid() -> None:
    settings = Settings(
        resume_storage_provider="mongodb_gridfs",
        mongodb_uri="mongodb://localhost:27017",
        **_REQUIRED,
    )
    assert settings.resume_storage_provider == "mongodb_gridfs"
    assert settings.mongodb_database == "ai_recruitment"


def test_mongodb_database_defaults_to_ai_recruitment() -> None:
    settings = Settings(resume_storage_provider="local", **_REQUIRED)
    assert settings.mongodb_database == "ai_recruitment"


def test_invalid_resume_storage_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(resume_storage_provider="s3", **_REQUIRED)

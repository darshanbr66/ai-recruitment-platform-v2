"""Unit tests for the `ResumeStorage` abstraction: both implementations
must honor the same save/read/open_stream/delete/exists/get_metadata
contract (app/integrations/storage/base.py). `LocalResumeStorage` is
exercised against a real temp directory (cheap, no real integration
concern); `MongoGridFSResumeStorage` against the in-memory fake bucket
(tests/fakes_mongo.py) — no real MongoDB instance required.
"""

import hashlib
import uuid
from pathlib import Path

import pytest
from bson import ObjectId

from app.integrations.storage import get_resume_storage_for_provider
from app.integrations.storage.base import StorageError
from app.integrations.storage.local import LocalResumeStorage
from app.integrations.storage.mongo_gridfs import MongoGridFSResumeStorage
from tests.fakes_mongo import FakeAsyncGridFSBucket

ORG_ID = uuid.uuid4()
CANDIDATE_ID = uuid.uuid4()
APPLICATION_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _save_kwargs(content: bytes, **overrides) -> dict:
    kwargs = dict(
        organization_id=ORG_ID,
        candidate_id=CANDIDATE_ID,
        application_id=APPLICATION_ID,
        original_filename="resume.pdf",
        content_type="application/pdf",
        content=content,
        uploaded_by_user_id=USER_ID,
    )
    kwargs.update(overrides)
    return kwargs


async def _collect(chunks) -> bytes:
    return b"".join([chunk async for chunk in chunks])


# --- LocalResumeStorage -----------------------------------------------


@pytest.fixture
def local_storage(tmp_path: Path) -> LocalResumeStorage:
    return LocalResumeStorage(root=tmp_path)


async def test_local_save_read_roundtrip(local_storage: LocalResumeStorage) -> None:
    saved = await local_storage.save(**_save_kwargs(b"hello world"))
    assert saved.storage_provider == "local"
    assert await local_storage.read(saved.storage_path) == b"hello world"


async def test_local_open_stream_yields_full_content(local_storage: LocalResumeStorage) -> None:
    content = b"a" * 500_000
    saved = await local_storage.save(**_save_kwargs(content))
    chunks = await local_storage.open_stream(saved.storage_path)
    assert await _collect(chunks) == content


async def test_local_exists_and_idempotent_delete(local_storage: LocalResumeStorage) -> None:
    saved = await local_storage.save(**_save_kwargs(b"x"))
    assert await local_storage.exists(saved.storage_path) is True

    await local_storage.delete(saved.storage_path)
    assert await local_storage.exists(saved.storage_path) is False

    # Deleting an already-missing file must not raise (CLAUDE.md task § 8:
    # "handle missing... files gracefully").
    await local_storage.delete(saved.storage_path)


async def test_local_read_missing_file_raises_storage_error(
    local_storage: LocalResumeStorage,
) -> None:
    with pytest.raises(StorageError):
        await local_storage.read("does-not/exist.pdf")


async def test_local_get_metadata(local_storage: LocalResumeStorage) -> None:
    saved = await local_storage.save(**_save_kwargs(b"12345"))
    meta = await local_storage.get_metadata(saved.storage_path)
    assert meta.size_bytes == 5


async def test_local_second_org_reuses_existing_root(local_storage: LocalResumeStorage) -> None:
    """Regression guard for the fix already documented in
    app/integrations/storage/local.py (`mkdir(exist_ok=True)`)."""
    await local_storage.save(**_save_kwargs(b"first"))
    await local_storage.save(**_save_kwargs(b"second"))


# --- MongoGridFSResumeStorage -------------------------------------------


@pytest.fixture
def mongo_storage(monkeypatch) -> MongoGridFSResumeStorage:
    import app.integrations.storage.mongo_gridfs as mongo_gridfs_module

    monkeypatch.setattr(mongo_gridfs_module, "AsyncGridFSBucket", FakeAsyncGridFSBucket)
    monkeypatch.setattr(mongo_gridfs_module, "get_mongo_database", lambda: None)
    return MongoGridFSResumeStorage()


async def test_mongo_save_stores_required_metadata_fields(
    mongo_storage: MongoGridFSResumeStorage,
) -> None:
    content = b"resume bytes"
    saved = await mongo_storage.save(**_save_kwargs(content))
    assert saved.storage_provider == "mongodb_gridfs"

    record = mongo_storage._bucket.files[ObjectId(saved.storage_path)]
    metadata = record["metadata"]
    assert metadata["organization_id"] == str(ORG_ID)
    assert metadata["candidate_id"] == str(CANDIDATE_ID)
    assert metadata["application_id"] == str(APPLICATION_ID)
    assert metadata["uploaded_by_user_id"] == str(USER_ID)
    assert metadata["original_filename"] == "resume.pdf"
    assert metadata["content_type"] == "application/pdf"
    assert metadata["size_bytes"] == len(content)
    assert metadata["checksum_sha256"] == hashlib.sha256(content).hexdigest()
    assert metadata["storage_version"] == 1
    # No JWT/auth material of any kind belongs in Mongo metadata.
    assert "password" not in metadata and "token" not in metadata


async def test_mongo_save_without_uploaded_by_user_id_omits_it(
    mongo_storage: MongoGridFSResumeStorage,
) -> None:
    saved = await mongo_storage.save(**_save_kwargs(b"x", uploaded_by_user_id=None))
    record = mongo_storage._bucket.files[ObjectId(saved.storage_path)]
    assert record["metadata"]["uploaded_by_user_id"] is None


async def test_mongo_read_roundtrip(mongo_storage: MongoGridFSResumeStorage) -> None:
    saved = await mongo_storage.save(**_save_kwargs(b"hello"))
    assert await mongo_storage.read(saved.storage_path) == b"hello"


async def test_mongo_open_stream_yields_full_content(
    mongo_storage: MongoGridFSResumeStorage,
) -> None:
    content = b"abcdefghij" * 100
    saved = await mongo_storage.save(**_save_kwargs(content))
    chunks = await mongo_storage.open_stream(saved.storage_path)
    assert await _collect(chunks) == content


async def test_mongo_exists_and_idempotent_delete(mongo_storage: MongoGridFSResumeStorage) -> None:
    saved = await mongo_storage.save(**_save_kwargs(b"x"))
    assert await mongo_storage.exists(saved.storage_path) is True

    await mongo_storage.delete(saved.storage_path)
    assert await mongo_storage.exists(saved.storage_path) is False

    # Idempotent: a Postgres-side cleanup pass racing a prior delete must
    # not crash (CLAUDE.md task § 8).
    await mongo_storage.delete(saved.storage_path)


async def test_mongo_read_missing_file_raises_storage_error(
    mongo_storage: MongoGridFSResumeStorage,
) -> None:
    with pytest.raises(StorageError):
        await mongo_storage.read(str(ObjectId()))


async def test_mongo_invalid_storage_path_raises_storage_error(
    mongo_storage: MongoGridFSResumeStorage,
) -> None:
    with pytest.raises(StorageError):
        await mongo_storage.read("not-an-object-id")


async def test_mongo_get_metadata(mongo_storage: MongoGridFSResumeStorage) -> None:
    saved = await mongo_storage.save(**_save_kwargs(b"12345"))
    meta = await mongo_storage.get_metadata(saved.storage_path)
    assert meta.size_bytes == 5
    assert meta.checksum_sha256 == hashlib.sha256(b"12345").hexdigest()
    assert meta.filename == saved.stored_filename


# --- provider resolution -------------------------------------------------


def test_get_resume_storage_for_unknown_provider_raises() -> None:
    with pytest.raises(StorageError):
        get_resume_storage_for_provider("s3")

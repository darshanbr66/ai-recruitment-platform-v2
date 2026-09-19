"""Shared in-memory fake for `gridfs.AsyncGridFSBucket` — lets tests
exercise `MongoGridFSResumeStorage` (and anything built on top of it)
without a real MongoDB deployment (CLAUDE.md task § 13: "mocks/fakes for
MongoDB in unit tests... do not require a real MongoDB instance").
"""

from bson import ObjectId
from gridfs.errors import NoFile


class FakeGridOut:
    """Stand-in for `gridfs.asynchronous.grid_file.AsyncGridOut`."""

    def __init__(self, file_id: ObjectId, filename: str, content: bytes, metadata: dict) -> None:
        self._id = file_id
        self.filename = filename
        self._content = content
        self.metadata = metadata
        self.length = len(content)
        self.content_type = None
        self.closed = False

    async def read(self) -> bytes:
        return self._content

    def __aiter__(self):
        content = self._content

        async def _gen():
            chunk_size = 4
            for i in range(0, len(content), chunk_size):
                yield content[i : i + chunk_size]

        return _gen()

    async def close(self) -> None:
        self.closed = True


class FakeAsyncGridFSBucket:
    """Drop-in stand-in for `gridfs.AsyncGridFSBucket`, backed by an
    in-process dict — no network, no real MongoDB deployment."""

    def __init__(self, _db, bucket_name: str = "fs", **_kwargs) -> None:
        self.bucket_name = bucket_name
        self.files: dict[ObjectId, dict] = {}

    async def upload_from_stream(self, filename, source, metadata=None, **_kwargs) -> ObjectId:
        file_id = ObjectId()
        self.files[file_id] = {
            "filename": filename,
            "content": bytes(source),
            "metadata": dict(metadata or {}),
        }
        return file_id

    async def open_download_stream(self, file_id, **_kwargs) -> FakeGridOut:
        record = self.files.get(file_id)
        if record is None:
            raise NoFile(f"no file with id {file_id!r}")
        return FakeGridOut(file_id, record["filename"], record["content"], record["metadata"])

    async def delete(self, file_id, **_kwargs) -> None:
        if file_id not in self.files:
            raise NoFile(f"no file with id {file_id!r}")
        del self.files[file_id]

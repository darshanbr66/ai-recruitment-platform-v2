"""Resume chunking: the pure chunking function, and the embed-and-store flow
with the embedding provider mocked at the one legitimate boundary — a real
Gemini call — the same "mock only at the external API boundary" rule
test_screening.py documents for the screening LLM call."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ai.base import AIProviderError
from app.models.candidate import Candidate, CandidateSource
from app.models.job import Job, JobStatus
from app.models.organization import Organization
from app.models.resume import Resume
from app.models.resume_chunk import EMBEDDING_DIMENSIONS, ResumeChunk
from app.models.user import User
from app.services import resume_chunking_service
from app.services.resume_chunking_service import split_into_chunks


def test_short_text_is_a_single_chunk() -> None:
    assert split_into_chunks("Experienced backend engineer.") == ["Experienced backend engineer."]


def test_empty_text_yields_no_chunks() -> None:
    assert split_into_chunks("   \n\n  ") == []


def test_long_text_is_split_into_multiple_chunks() -> None:
    paragraph = "Skilled in Python and PostgreSQL. " * 100  # well over the chunk size
    chunks = split_into_chunks(paragraph)

    assert len(chunks) > 1
    assert all(len(chunk) <= 1200 + 1 for chunk in chunks)  # +1 for the boundary character kept


def test_chunk_count_is_bounded_for_pathological_input() -> None:
    huge_text = "word " * 200_000

    chunks = split_into_chunks(huge_text)

    assert len(chunks) <= 40


class _FakeEmbeddingProvider:
    name = "fake"
    model = "fake-embed"
    dimension = EMBEDDING_DIMENSIONS

    async def embed(self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        return [[0.01 * (i + 1)] * EMBEDDING_DIMENSIONS for i in range(len(texts))]


class _FailingEmbeddingProvider:
    name = "fake"
    model = "fake-embed"
    dimension = EMBEDDING_DIMENSIONS

    async def embed(self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        raise AIProviderError("The embedding provider is unreachable.")


async def _seed_resume(db_session: AsyncSession, *, filename: str, storage_path: str) -> Resume:
    from app.db.rls import set_rls_bypass, set_tenant_context

    await set_rls_bypass(db_session, enabled=True)
    org = Organization(name="Embed Co", slug=f"embed-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    user = User(organization_id=org.id, email="admin@embed.test", hashed_password="x", full_name="Admin")
    db_session.add(user)
    await db_session.flush()

    candidate = Candidate(
        organization_id=org.id, email="candidate@embed.test", full_name="Candidate",
        source=CandidateSource.RECRUITER_ADDED,
    )
    db_session.add(candidate)
    await db_session.flush()

    job = Job(organization_id=org.id, title="Engineer", description="Engineer role.", status=JobStatus.OPEN, created_by=user.id)
    db_session.add(job)
    await db_session.flush()

    from app.models.application import Application, ApplicationSource

    application = Application(
        organization_id=org.id, candidate_id=candidate.id, job_id=job.id, source=ApplicationSource.RECRUITER_ADDED,
    )
    db_session.add(application)
    await db_session.flush()

    resume = Resume(
        organization_id=org.id,
        candidate_id=candidate.id,
        application_id=application.id,
        original_filename=filename,
        stored_filename=filename,
        storage_path=storage_path,
        storage_provider="local",
        content_type="application/pdf",
        size_bytes=100,
    )
    db_session.add(resume)
    await db_session.flush()
    await set_rls_bypass(db_session, enabled=False)
    # A real request already has its tenant context set by get_current_user
    # before resume_service.save_resume (and therefore chunking) ever runs —
    # set it here so the test exercises the same RLS-scoped path.
    await set_tenant_context(db_session, org.id)
    return resume


@pytest.fixture
def local_pdf_resume(tmp_path, monkeypatch):
    """Writes a real, extractable PDF under the local resume storage dir and
    returns a factory that seeds a matching Resume row."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "resume_storage_dir", str(tmp_path))
    return tmp_path


async def test_chunk_and_embed_resume_creates_chunks(db_session: AsyncSession, local_pdf_resume, monkeypatch) -> None:
    from tests.conftest import make_minimal_pdf

    pdf_bytes = make_minimal_pdf("Backend engineer with Python and PostgreSQL experience. " * 30)
    relative_path = "resume.pdf"
    (local_pdf_resume / relative_path).write_bytes(pdf_bytes)

    resume = await _seed_resume(db_session, filename="resume.pdf", storage_path=relative_path)
    monkeypatch.setattr(resume_chunking_service, "get_embedding_provider", lambda: _FakeEmbeddingProvider())

    chunks = await resume_chunking_service.chunk_and_embed_resume(db_session, resume)

    assert len(chunks) > 0
    assert all(len(c.embedding) == EMBEDDING_DIMENSIONS for c in chunks)
    stored = (
        await db_session.execute(select(ResumeChunk).where(ResumeChunk.resume_id == resume.id))
    ).scalars().all()
    assert len(stored) == len(chunks)


async def test_rechunking_replaces_rather_than_duplicates(db_session: AsyncSession, local_pdf_resume, monkeypatch) -> None:
    from tests.conftest import make_minimal_pdf

    pdf_bytes = make_minimal_pdf("Short resume text.")
    (local_pdf_resume / "resume.pdf").write_bytes(pdf_bytes)
    resume = await _seed_resume(db_session, filename="resume.pdf", storage_path="resume.pdf")
    monkeypatch.setattr(resume_chunking_service, "get_embedding_provider", lambda: _FakeEmbeddingProvider())

    first = await resume_chunking_service.chunk_and_embed_resume(db_session, resume)
    second = await resume_chunking_service.chunk_and_embed_resume(db_session, resume)

    stored = (
        await db_session.execute(select(ResumeChunk).where(ResumeChunk.resume_id == resume.id))
    ).scalars().all()
    assert len(stored) == len(second)
    assert len(first) == len(second)


async def test_embedding_failure_is_best_effort_and_never_raises(db_session: AsyncSession, local_pdf_resume, monkeypatch) -> None:
    from tests.conftest import make_minimal_pdf

    pdf_bytes = make_minimal_pdf("Some resume text.")
    (local_pdf_resume / "resume.pdf").write_bytes(pdf_bytes)
    resume = await _seed_resume(db_session, filename="resume.pdf", storage_path="resume.pdf")
    monkeypatch.setattr(resume_chunking_service, "get_embedding_provider", lambda: _FailingEmbeddingProvider())

    chunks = await resume_chunking_service.chunk_and_embed_resume(db_session, resume)

    assert chunks == []

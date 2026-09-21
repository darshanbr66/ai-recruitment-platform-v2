"""Knowledge layer contracts — deliberately independent of the chatbot.

Sigvi asks a `KnowledgeRetriever` for the entries relevant to a question and
receives plain `KnowledgeEntry` values; it neither knows nor cares where they
come from. Today that is a small curated set matched by keyword
(`keyword_retriever.py`). Replacing it with document ingestion + chunking +
embeddings + pgvector retrieval means writing another `KnowledgeRetriever`
that returns the same entries (a chunk can carry its document title/URL as
`title`/`url`) — the orchestration and the API do not change.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class KnowledgeEntry:
    id: str
    title: str
    #: Public-safe, factual text. Written for a language model to ground on.
    content: str
    #: Lower-case terms (single words) that make this entry relevant.
    keywords: frozenset[str]
    #: Site-relative path a visitor can open for the primary source, if any.
    url: str | None = None


class KnowledgeRetriever(Protocol):
    def retrieve(self, query: str, *, limit: int) -> list[KnowledgeEntry]:
        """The most relevant entries for `query`, best first — empty when
        nothing is relevant (callers must not pad with unrelated entries)."""
        ...

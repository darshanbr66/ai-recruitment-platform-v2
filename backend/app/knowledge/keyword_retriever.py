"""Keyword retrieval over a small, curated entry set.

Honest about what it is: term overlap, not semantic search. It is enough while
the knowledge base is ~a dozen hand-written entries; every entry therefore
lists generous keywords. It is the piece to swap for embeddings + pgvector
when the knowledge base grows (see base.py)."""

import re
from collections.abc import Iterable

from app.knowledge.base import KnowledgeEntry

_TOKEN = re.compile(r"[a-z0-9]+")

# Words that carry no topical signal. Kept small on purpose — stemming/synonyms
# are handled by listing the variants in each entry's keywords.
_STOPWORDS = frozenset(
    "a an and are as at be but by can do does for from how i if in is it me my of on or so "
    "that the this to was what when where which who why will with you your about tell "
    "please should would could have has had get".split()
)


def tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS}


class KeywordKnowledgeRetriever:
    def __init__(self, entries: Iterable[KnowledgeEntry]) -> None:
        self._entries = tuple(entries)

    def retrieve(self, query: str, *, limit: int) -> list[KnowledgeEntry]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scored: list[tuple[int, int, KnowledgeEntry]] = []
        for position, entry in enumerate(self._entries):
            keyword_hits = len(query_tokens & entry.keywords)
            if keyword_hits == 0:
                continue  # a title word alone is too weak a signal to include an entry
            score = 3 * keyword_hits + len(query_tokens & tokenize(entry.title))
            # `-position` keeps the curated order for equal scores.
            scored.append((score, -position, entry))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for _, _, entry in scored[:limit]]

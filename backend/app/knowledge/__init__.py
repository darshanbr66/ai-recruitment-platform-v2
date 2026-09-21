from app.knowledge.base import KnowledgeEntry, KnowledgeRetriever
from app.knowledge.keyword_retriever import KeywordKnowledgeRetriever
from app.knowledge.sigvitas_public import SIGVITAS_PUBLIC_KNOWLEDGE

__all__ = [
    "KnowledgeEntry",
    "KnowledgeRetriever",
    "KeywordKnowledgeRetriever",
    "SIGVITAS_PUBLIC_KNOWLEDGE",
    "get_knowledge_retriever",
]


def get_knowledge_retriever() -> KnowledgeRetriever:
    """The retriever Sigvi uses. Today: keyword matching over the curated
    public entries. Swap this one function to move to embeddings/pgvector."""
    return KeywordKnowledgeRetriever(SIGVITAS_PUBLIC_KNOWLEDGE)

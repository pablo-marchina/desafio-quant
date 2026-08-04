"""RAG modules for NVIDIA knowledge retrieval using Qdrant + sentence-transformers."""

from radar.rag.embeddings import embed_batch, embed_text
from radar.rag.enricher import enrich_from_urls, enrich_nvidia_docs
from radar.rag.retriever import ensure_seeded, get_store, reset, retrieve
from radar.rag.vector_store import VectorStore

__all__ = [
    "VectorStore",
    "embed_text",
    "embed_batch",
    "ensure_seeded",
    "retrieve",
    "reset",
    "get_store",
    "enrich_from_urls",
    "enrich_nvidia_docs",
]

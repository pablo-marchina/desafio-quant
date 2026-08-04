"""Semantic retrieval — embed query, search vector store, return contexts."""

from __future__ import annotations

from src.rag.embeddings import EmbeddingProvider
from src.rag.schemas import RetrievalQuery, RetrievedContext
from src.rag.vector_store import VectorStore


def semantic_retrieve(
    query: RetrievalQuery,
    embedding_model: EmbeddingProvider,
    vector_store: VectorStore,
    top_k: int = 3,
    *,
    product: str | None = None,
    gap_type: str | None = None,
    source_id: str | None = None,
    include_deprecated: bool = False,
    include_expired: bool = False,
) -> list[RetrievedContext]:
    """Retrieve contexts semantically by embedding the query and searching the vector store.

    Parameters
    ----------
    query:
        The retrieval query (gap_type, technology, keywords).
    embedding_model:
        Embedding provider used to vectorize the query.
    vector_store:
        Vector store containing embedded chunks.
    top_k:
        Maximum number of contexts to return.
    product, gap_type, source_id:
        Optional metadata filters applied *before* similarity scoring.

    Returns
    -------
    list[RetrievedContext]
        Up to ``top_k`` contexts sorted by relevance (highest first).
        Returns empty list if the vector store is empty or no match found.
    """
    if vector_store.size == 0:
        return []

    query_text = _build_query_text(query)
    query_vector = embedding_model.embed(query_text)

    results = vector_store.search(
        query_vector,
        top_k=top_k,
        product=product,
        gap_type=gap_type,
        source_id=source_id,
        include_deprecated=include_deprecated,
        include_expired=include_expired,
    )

    contexts: list[RetrievedContext] = []
    for entry in results:
        score = _compute_relevance_from_similarity(entry, query)
        contexts.append(
            RetrievedContext(
                chunk_id=entry.chunk_id,
                source_id=entry.source_id,
                title=entry.title,
                content=entry.content,
                product=entry.product,
                gap_types=list(entry.gap_types),
                url=entry.url,
                relevance_score=score,
                version=entry.version,
                valid_from=entry.valid_from,
                valid_until=entry.valid_until,
                freshness_policy=entry.freshness_policy,
                stale_after_days=entry.stale_after_days,
                is_active=entry.is_active,
                deprecated_at=entry.deprecated_at,
                superseded_by=entry.superseded_by,
            )
        )
    return contexts


def _build_query_text(query: RetrievalQuery) -> str:
    """Build a plain-text query from a RetrievalQuery for embedding."""
    parts: list[str] = []
    if query.gap_type:
        parts.append(query.gap_type.replace("_", " "))
    if query.technology:
        parts.append(query.technology)
    if query.keywords:
        parts.extend(query.keywords)
    return " ".join(parts) if parts else ""


def _compute_relevance_from_similarity(
    entry: object,
    query: RetrievalQuery,
) -> float:
    """Map cosine similarity to a 0-1 relevance score with bonus for metadata matches.

    The raw cosine similarity ([-1, 1]) is mapped to [0, 1].
    Metadata bonuses (gap_type match, technology match) are added on top
    and the result is clamped to [0, 1].
    """
    score = 0.5
    if isinstance(entry, object) and hasattr(entry, "gap_types"):
        if query.gap_type and query.gap_type in entry.gap_types:  # type: ignore[union-attr]
            score += 0.25
    if isinstance(entry, object) and hasattr(entry, "product"):
        if query.technology and query.technology.lower() in entry.product.lower():  # type: ignore[union-attr]
            score += 0.15
    if isinstance(entry, object) and hasattr(entry, "content"):
        content: str = entry.content  # type: ignore[union-attr]
        content_lower = content.lower()
        if query.keywords:
            matched = sum(1 for kw in query.keywords if kw.lower() in content_lower)
            if matched > 0:
                score += 0.1 * min(matched / len(query.keywords), 1.0)
    return round(min(max(score, 0.0), 1.0), 2)

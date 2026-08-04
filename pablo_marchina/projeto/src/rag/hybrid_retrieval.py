"""Hybrid retrieval — BM25 + dense Qdrant + GraphRAG expansion via RRF."""

from __future__ import annotations

import os
from typing import Any

from src.diagnosis.schemas import GAP_TECH_MAP, GapType
from src.rag.embeddings import EmbeddingProvider
from src.rag.graphrag_runtime import graphrag_expand
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext
from src.rag.semantic_retrieval import semantic_retrieve
from src.rag.sparse_retrieval import SparseRetriever
from src.rag.vector_store import VectorStore

_RRF_K = 60


def hybrid_retrieve(
    query: RetrievalQuery,
    chunk_index: ChunkIndex,
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
    """Retrieve contexts using BM25, dense Qdrant, and GraphRAG fusion.

    Gap diagnosis and corpus metadata use related taxonomies: diagnosis-level
    gaps such as ``computer_vision_gap`` and technical corpus tags such as
    ``computer_vision_need``. Every retrieval mechanism receives a query variant
    for each governed alias. In product mode a result is fail-closed when either
    BM25 or Qdrant returns no candidates, so a successful retrieval proves both
    paths participated before GraphRAG expansion and RRF fusion.
    """
    if top_k <= 0:
        return []

    retrieve_top_k = max(top_k * 2, 5)
    requested_gap = gap_type or query.gap_type
    variants = _query_variants(query, requested_gap)
    bm25_retriever = SparseRetriever(chunk_index)

    lexical_rankings: list[list[RetrievedContext]] = []
    semantic_rankings: list[list[RetrievedContext]] = []
    graph_rankings: list[list[RetrievedContext]] = []

    for variant in variants:
        lexical = bm25_retriever.retrieve(variant, top_k=retrieve_top_k)
        lexical_rankings.append(lexical)

        semantic: list[RetrievedContext] = []
        if vector_store.size > 0:
            semantic = semantic_retrieve(
                variant,
                embedding_model,
                vector_store,
                top_k=retrieve_top_k,
                product=product,
                gap_type=variant.gap_type,
                source_id=source_id,
                include_deprecated=include_deprecated,
                include_expired=include_expired,
            )
        semantic_rankings.append(semantic)

        seed_results = semantic or lexical
        graph_results, _graph_metrics = graphrag_expand(
            seed_contexts=seed_results[:top_k],
            corpus_contexts=chunk_index.retrieve(
                variant,
                top_k=max(retrieve_top_k * 3, 15),
            ),
            query=variant,
            top_k=retrieve_top_k,
        )
        graph_rankings.append(graph_results)

    lexical_results = _deduplicate_rankings(lexical_rankings)
    semantic_results = _deduplicate_rankings(semantic_rankings)

    product_mode = os.getenv("APP_MODE", "").casefold() == "product"
    if product_mode and vector_store.size > 0 and (
        not lexical_results or not semantic_results
    ):
        return []

    fused = _rrf_fuse_many(
        lexical_rankings + semantic_rankings + graph_rankings,
        max(top_k * 3, top_k),
    )
    _attach_requested_gap_alias(fused, requested_gap)
    filtered = _apply_filters(fused, product, requested_gap, source_id)
    return filtered[:top_k]


def _query_variants(
    query: RetrievalQuery,
    requested_gap: str | None,
) -> list[RetrievalQuery]:
    if not requested_gap:
        return [query]
    aliases = sorted(_gap_type_aliases(requested_gap))
    return [query.model_copy(update={"gap_type": alias}) for alias in aliases]


def _deduplicate_rankings(
    rankings: list[list[RetrievedContext]],
) -> list[RetrievedContext]:
    seen: set[str] = set()
    result: list[RetrievedContext] = []
    for ranking in rankings:
        for context in ranking:
            if context.chunk_id in seen:
                continue
            seen.add(context.chunk_id)
            result.append(context)
    return result


def _attach_requested_gap_alias(
    contexts: list[RetrievedContext],
    requested_gap: str | None,
) -> None:
    if not requested_gap:
        return
    aliases = _gap_type_aliases(requested_gap)
    for context in contexts:
        if aliases.intersection(context.gap_types) and requested_gap not in context.gap_types:
            context.gap_types.append(requested_gap)


def _rrf_fuse(
    lexical: list[RetrievedContext],
    semantic: list[RetrievedContext],
    top_k: int,
) -> list[RetrievedContext]:
    """Backward-compatible two-list RRF fusion."""
    return _rrf_fuse_many([lexical, semantic], top_k)


def _rrf_fuse_many(
    ranked_lists: list[list[RetrievedContext]],
    top_k: int,
) -> list[RetrievedContext]:
    """Fuse BM25, dense Qdrant, and GraphRAG ranked lists using RRF."""
    rrf_scores: dict[str, float] = {}
    contexts: dict[str, RetrievedContext] = {}

    for ranked in ranked_lists:
        for rank, ctx in enumerate(ranked):
            rrf_scores[ctx.chunk_id] = rrf_scores.get(ctx.chunk_id, 0.0) + 1.0 / (
                _RRF_K + rank + 1
            )
            if ctx.chunk_id not in contexts:
                contexts[ctx.chunk_id] = ctx

    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)
    fused = [contexts[cid] for cid in sorted_ids[:top_k]]

    max_score = max(rrf_scores.values()) if rrf_scores else 1.0
    for ctx in fused:
        ctx.relevance_score = round(
            min(max(rrf_scores.get(ctx.chunk_id, 0.0) / max_score, 0.0), 1.0),
            4,
        )

    return fused


def _gap_type_aliases(gap_type: str) -> set[str]:
    """Return diagnosis and technical taxonomy aliases for corpus retrieval."""
    aliases = {gap_type}
    try:
        diagnosis_gap = GapType(gap_type)
    except ValueError:
        return aliases
    aliases.update(
        technical_gap.value for technical_gap in GAP_TECH_MAP.get(diagnosis_gap, [])
    )
    return aliases


def _apply_filters(
    contexts: list[RetrievedContext],
    product: str | None = None,
    gap_type: str | None = None,
    source_id: str | None = None,
) -> list[RetrievedContext]:
    """Post-filter a list of contexts by governed metadata criteria."""
    result = contexts
    if product:
        p_lower = product.lower()
        result = [c for c in result if c.product.lower() == p_lower]
    if gap_type:
        aliases = _gap_type_aliases(gap_type)
        result = [c for c in result if aliases.intersection(c.gap_types)]
    if source_id:
        result = [c for c in result if c.source_id == source_id]
    return result


class HybridRetrieval:
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query")
        chunk_index = kwargs.get("chunk_index")
        embedding_model = kwargs.get("embedding_model")
        vector_store = kwargs.get("vector_store")
        if (
            not isinstance(query, RetrievalQuery)
            or not isinstance(chunk_index, ChunkIndex)
            or not isinstance(embedding_model, EmbeddingProvider)
            or not isinstance(vector_store, VectorStore)
        ):
            return contexts
        return hybrid_retrieve(
            query=query,
            chunk_index=chunk_index,
            embedding_model=embedding_model,
            vector_store=vector_store,
            top_k=kwargs.get("top_k", 3),
            product=kwargs.get("product"),
            gap_type=kwargs.get("gap_type"),
            source_id=kwargs.get("source_id"),
            include_deprecated=kwargs.get("include_deprecated", False),
            include_expired=kwargs.get("include_expired", False),
        )

"""HybridRagRetriever — unified retrieval service for Hybrid RAG.

Orchestrates dense, sparse, fusion, and reranking steps.
Handles fallback chains and degraded mode recording.
"""

from __future__ import annotations

from src.rag.embeddings import EmbeddingProvider
from src.rag.fusion import reciprocal_rank_fusion
from src.rag.query_planner import build_query_plan
from src.rag.reranker import NoOpReranker, Reranker
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import (
    QueryPlan,
    RagEvidenceChunk,
    RagEvidenceChunkList,
    RetrievalMode,
    RetrievalQuery,
    RetrievedContext,
)
from src.rag.semantic_retrieval import semantic_retrieve
from src.rag.sparse_retrieval import SparseRetriever
from src.rag.vector_store import VectorStore


def _default_retrieval_mode(
    has_sparse: bool,
    has_reranker: bool,
    configured_mode: str,
) -> RetrievalMode:
    """Resolve the effective retrieval mode based on available components."""
    mode_map: dict[str, RetrievalMode] = {
        "dense_only": RetrievalMode.DENSE_ONLY,
        "sparse_only": RetrievalMode.SPARSE_ONLY,
        "hybrid": RetrievalMode.HYBRID,
        "hybrid_with_rerank": RetrievalMode.HYBRID_WITH_RERANK,
    }
    preferred = mode_map.get(configured_mode)
    if preferred is None:
        if has_reranker and has_sparse:
            return RetrievalMode.HYBRID_WITH_RERANK
        if has_sparse:
            return RetrievalMode.HYBRID
        return RetrievalMode.DENSE_ONLY

    # Fallback chain
    if preferred == RetrievalMode.HYBRID_WITH_RERANK and not has_reranker:
        if has_sparse:
            return RetrievalMode.HYBRID
        return RetrievalMode.DENSE_ONLY
    if preferred in (RetrievalMode.HYBRID, RetrievalMode.SPARSE_ONLY) and not has_sparse:
        return RetrievalMode.DENSE_ONLY
    return preferred


class HybridRagRetriever:
    """Unified retrieval service for Hybrid RAG.

    Parameters
    ----------
    chunk_index:
        Lexical ChunkIndex for dense retrieval fallback and sparse index.
    embedding_model:
        Embedding provider for dense/semantic retrieval.
    vector_store:
        Vector store for dense retrieval.
    reranker:
        Reranker instance (default NoOpReranker).
    sparse_retriever:
        SparseRetriever instance.  If None, sparse is disabled.
    dense_weight:
        Weight for dense results in fusion (default 0.5).
    sparse_weight:
        Weight for sparse results in fusion (default 0.5).
    retrieval_mode:
        Configured retrieval mode string.
    """

    def __init__(
        self,
        chunk_index: ChunkIndex,
        embedding_model: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
        reranker: Reranker | None = None,
        sparse_retriever: SparseRetriever | None = None,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
        retrieval_mode: str = "dense_only",
    ) -> None:
        self._idx = chunk_index
        self._embedder = embedding_model
        self._store = vector_store
        self._reranker = reranker or NoOpReranker()
        self._sparse = sparse_retriever
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight
        self._config_mode = retrieval_mode

        has_sparse = sparse_retriever is not None and sparse_retriever.is_ready
        has_ce = self._reranker.__class__.__name__ == "OptionalCrossEncoderReranker" and (
            getattr(self._reranker, "is_available", False) or getattr(self._reranker, "_load_error", "") == ""
        )

        self._resolved_mode = _default_retrieval_mode(has_sparse, has_ce, retrieval_mode)

    @property
    def resolved_mode(self) -> RetrievalMode:
        """Effective retrieval mode after fallback resolution."""
        return self._resolved_mode

    def retrieve(
        self,
        query_plan: QueryPlan | None = None,
        mode: str | None = None,
        top_k: int = 5,
    ) -> RagEvidenceChunkList:
        """Execute retrieval according to the resolved mode.

        Parameters
        ----------
        query_plan:
            Structured query plan.  If None, uses empty plan.
        mode:
            Override retrieval mode for this call.  If None, uses resolved mode.
        top_k:
            Maximum chunks to return.

        Returns
        -------
        RagEvidenceChunkList
            Retrieved chunks with metadata.
        """
        if query_plan is None:
            query_plan = build_query_plan()

        effective_mode = self._resolved_mode
        if mode is not None:
            effective_mode = _default_retrieval_mode(
                self._sparse is not None and self._sparse.is_ready,
                False,
                mode,
            )

        retrieval_query = RetrievalQuery(
            gap_type=query_plan.metadata_filters.get("gap_type"),
            technology=(" ".join(query_plan.technology_filters) if query_plan.technology_filters else None),
            keywords=query_plan.keyword_query.split() if query_plan.keyword_query else [],
        )

        fallback_reason = ""
        degraded = False
        used_mode = effective_mode.value

        dense_chunks: list[RagEvidenceChunk] = []
        sparse_chunks: list[RagEvidenceChunk] = []

        if effective_mode in (
            RetrievalMode.DENSE_ONLY,
            RetrievalMode.HYBRID,
            RetrievalMode.HYBRID_WITH_RERANK,
        ):
            dense_chunks = self._retrieve_dense(retrieval_query, top_k)
            if not dense_chunks and effective_mode not in (
                RetrievalMode.HYBRID,
                RetrievalMode.HYBRID_WITH_RERANK,
            ):
                fallback_reason = "dense_retrieval_empty"

        if effective_mode in (
            RetrievalMode.SPARSE_ONLY,
            RetrievalMode.HYBRID,
            RetrievalMode.HYBRID_WITH_RERANK,
        ):
            if self._sparse is not None and self._sparse.is_ready:
                sparse_raw = self._sparse.retrieve(retrieval_query, top_k=top_k)
                sparse_chunks = [_retrieved_to_evidence(c, "sparse_only") for c in sparse_raw]
            else:
                fallback_reason = "sparse_not_available"
                degraded = True
                if effective_mode == RetrievalMode.SPARSE_ONLY:
                    # Fall back to dense
                    dense_chunks = self._retrieve_dense(retrieval_query, top_k)
                    used_mode = "dense_only"

        # Fusion
        if effective_mode in (RetrievalMode.HYBRID, RetrievalMode.HYBRID_WITH_RERANK):
            if dense_chunks and sparse_chunks:
                fused = reciprocal_rank_fusion(
                    dense_chunks,
                    sparse_chunks,
                    top_k=top_k,
                    dense_weight=self._dense_weight,
                    sparse_weight=self._sparse_weight,
                )
            elif dense_chunks:
                fused = dense_chunks[:top_k]
                for c in fused:
                    c.score_fused = c.score_dense
            else:
                fused = []
                fallback_reason = "both_dense_and_sparse_empty"
                degraded = True

            if effective_mode == RetrievalMode.HYBRID_WITH_RERANK and fused:
                try:
                    query_text = query_plan.primary_query or query_plan.keyword_query or ""
                    reranked = self._reranker.rerank(query_text, fused, top_k=top_k)
                    used_mode = "hybrid_with_rerank"
                    fused = reranked
                except Exception:
                    fallback_reason = "reranker_failed"
                    degraded = True
                    used_mode = "hybrid"

            chunks = fused
        elif effective_mode == RetrievalMode.DENSE_ONLY:
            chunks = dense_chunks
        elif effective_mode == RetrievalMode.SPARSE_ONLY:
            chunks = sparse_chunks
        else:
            chunks = []

        total_raw = len(dense_chunks) + len(sparse_chunks)

        # Update retrieval_mode on each chunk
        for c in chunks:
            c.retrieval_mode = used_mode

        return RagEvidenceChunkList(
            chunks=chunks,
            retrieval_mode=used_mode,
            total_raw=total_raw,
            total_returned=len(chunks),
            fallback_reason=fallback_reason,
            degraded=degraded,
        )

    def _retrieve_dense(
        self,
        query: RetrievalQuery,
        top_k: int,
    ) -> list[RagEvidenceChunk]:
        """Run dense/semantic retrieval via existing infrastructure."""
        if self._store is not None and self._store.size > 0 and self._embedder is not None:
            ctxs = semantic_retrieve(query, self._embedder, self._store, top_k=top_k)
            if ctxs:
                return [_retrieved_to_evidence(c, "dense_only") for c in ctxs]

        # Fallback to lexical index
        ctxs = self._idx.retrieve(query, top_k=top_k)
        return [_retrieved_to_evidence(c, "dense_only") for c in ctxs]


def _retrieved_to_evidence(ctx: RetrievedContext, mode: str) -> RagEvidenceChunk:
    """Convert a RetrievedContext to a RagEvidenceChunk."""
    section = _guess_section(ctx.content)

    return RagEvidenceChunk(
        chunk_id=ctx.chunk_id,
        source_title=ctx.title,
        source_url=ctx.url,
        section=section,
        text=ctx.content,
        score_dense=ctx.relevance_score,
        score_sparse=0.0,
        score_fused=0.0,
        score_rerank=0.0,
        retrieval_mode=mode,
        corpus_version=ctx.version,
        metadata_json={
            "source_id": ctx.source_id,
            "product": ctx.product,
            "gap_types": list(ctx.gap_types),
            "is_active": ctx.is_active,
        },
    )


def _guess_section(content: str) -> str:
    """Guess section heading from chunk content (first ## or # line)."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("# "):
            return stripped.lstrip("# ").strip()
    return content[:80].strip()

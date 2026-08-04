from __future__ import annotations

from typing import Any

from src.quality.constants import (
    METRIC_RAG_AVG_DENSE_SCORE,
    METRIC_RAG_AVG_FUSED_SCORE,
    METRIC_RAG_AVG_SPARSE_SCORE,
    METRIC_RAG_DEGRADED_MODE,
    METRIC_RAG_FALLBACK_COUNT,
    METRIC_RAG_RETRIEVAL_SUCCESS,
    METRIC_RAG_SOURCE_COVERAGE,
)
from src.rag.schemas import RagEvidenceChunkList


def evaluate_rag_retrieval(result: RagEvidenceChunkList) -> dict[str, Any]:
    """Evaluate RAG retrieval quality for a single query.

    Returns metric key-value pairs suitable for the quality system.
    """
    chunks = result.chunks
    total = len(chunks)

    has_results = total > 0
    success = 1.0 if has_results else 0.0
    degraded = 1.0 if result.degraded else 0.0
    fallback_count = 1 if result.fallback_reason else 0

    # Source coverage
    unique_sources = len({c.chunk_id for c in chunks})
    with_url = sum(1 for c in chunks if c.source_url)
    source_coverage = round(with_url / total, 4) if total > 0 else 0.0

    # Average scores
    dense_scores = [c.score_dense for c in chunks if c.score_dense is not None and c.score_dense > 0]
    sparse_scores = [c.score_sparse for c in chunks if c.score_sparse is not None and c.score_sparse > 0]
    fused_scores = [c.score_fused for c in chunks if c.score_fused is not None and c.score_fused > 0]

    avg_dense = round(sum(dense_scores) / len(dense_scores), 4) if dense_scores else 0.0
    avg_sparse = round(sum(sparse_scores) / len(sparse_scores), 4) if sparse_scores else 0.0
    avg_fused = round(sum(fused_scores) / len(fused_scores), 4) if fused_scores else 0.0

    return {
        METRIC_RAG_RETRIEVAL_SUCCESS: success,
        METRIC_RAG_DEGRADED_MODE: degraded,
        METRIC_RAG_FALLBACK_COUNT: fallback_count,
        METRIC_RAG_SOURCE_COVERAGE: source_coverage,
        METRIC_RAG_AVG_DENSE_SCORE: avg_dense,
        METRIC_RAG_AVG_SPARSE_SCORE: avg_sparse,
        METRIC_RAG_AVG_FUSED_SCORE: avg_fused,
        "total_raw": result.total_raw,
        "total_returned": result.total_returned,
        "retrieval_mode": result.retrieval_mode,
        "fallback_reason": result.fallback_reason or "",
        "unique_sources": unique_sources,
    }

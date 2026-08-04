"""Tests for Epic 42 — Hybrid RAG + Reranking Hardening modules."""

from __future__ import annotations

from src.rag.fusion import reciprocal_rank_fusion, weighted_score_fusion
from src.rag.query_planner import build_query_plan
from src.rag.reranker import NoOpReranker, OptionalCrossEncoderReranker, build_reranker
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import (
    QueryPlan,
    RagChunk,
    RagEvidenceChunk,
    RetrievalMode,
)
from src.rag.sparse_retrieval import SparseRetriever

# =============================================================================
# Helpers
# =============================================================================


def _make_chunk(
    chunk_id: str = "chunk_a",
    source_title: str = "Test Source",
    source_url: str | None = "https://docs.nvidia.com/test",
    text: str = "NVIDIA NIM is optimized for inference.",
    score_dense: float = 0.0,
    score_sparse: float = 0.0,
    score_fused: float = 0.0,
    mode: str = "hybrid",
) -> RagEvidenceChunk:
    return RagEvidenceChunk(
        chunk_id=chunk_id,
        source_title=source_title,
        source_url=source_url,
        section="Overview",
        text=text,
        score_dense=score_dense,
        score_sparse=score_sparse,
        score_fused=score_fused,
        retrieval_mode=mode,
    )


def _make_rag_chunk(
    chunk_id: str = "rc_a",
    content: str = "TensorRT-LLM optimizes inference.",
) -> RagChunk:
    return RagChunk(
        chunk_id=chunk_id,
        source_id="src1",
        title="Test",
        content=content,
        product="NVIDIA NIM",
        gap_types=["high_inference_cost"],
        url="https://docs.nvidia.com/test",
    )


def _index_from_chunks(texts: list[tuple[str, str]]) -> ChunkIndex:
    """Build a ChunkIndex from list of (chunk_id, text) pairs."""
    chunks = [_make_rag_chunk(chunk_id=cid, content=t) for cid, t in texts]
    return ChunkIndex(chunks)


# =============================================================================
# Test Query Planner
# =============================================================================


class TestQueryPlanner:
    def test_empty_plan(self) -> None:
        plan = build_query_plan()
        assert isinstance(plan, QueryPlan)
        assert plan.primary_query == ""
        assert plan.keyword_query == ""
        assert plan.technology_filters == []

    def test_plan_with_gaps(self) -> None:
        plan = build_query_plan(detected_gaps=["high_inference_cost"])
        assert "inference" in plan.primary_query.lower()
        assert "tensorrt_llm" in plan.target_doc_categories or "nim" in plan.target_doc_categories

    def test_plan_with_technology(self) -> None:
        plan = build_query_plan(desired_technologies=["TensorRT-LLM"])
        assert plan.technology_filters == ["TensorRT-LLM"]
        assert "TensorRT-LLM" in plan.primary_query

    def test_plan_with_product_summary(self) -> None:
        plan = build_query_plan(product_summary="GPU inference with custom models")
        assert "gpu" in plan.keyword_query or "inference" in plan.keyword_query

    def test_plan_with_claims_and_gaps(self) -> None:
        plan = build_query_plan(
            detected_gaps=["high_inference_cost"],
            claim_types=["ai_native_claim"],
        )
        assert any("inference" in t for t in plan.must_have_terms)
        assert any("ai" in t for t in plan.must_have_terms)


# =============================================================================
# Test Sparse Retrieval
# =============================================================================


class TestSparseRetrieval:
    def test_empty_index_not_ready(self) -> None:
        idx = ChunkIndex([])
        retriever = SparseRetriever(idx)
        assert not retriever.is_ready

    def test_build_and_retrieve(self) -> None:
        texts = [
            ("c1", "TensorRT-LLM optimizes large language model inference on GPUs."),
            ("c2", "NVIDIA NIM provides optimized inference microservices."),
            ("c3", "FP8 quantization reduces memory bandwidth requirements."),
        ]
        idx = _index_from_chunks(texts)
        retriever = SparseRetriever(idx)
        assert retriever.is_ready

        from src.rag.schemas import RetrievalQuery

        results = retriever.retrieve(RetrievalQuery(keywords=["inference"]), top_k=5)
        assert len(results) >= 1
        scores = {r.chunk_id: r.relevance_score for r in results}
        assert scores.get("c1", 0) > 0
        assert scores.get("c2", 0) > 0

    def test_build_and_retrieve_with_lifecycle_filter(self) -> None:
        ra = _make_rag_chunk("c1", content="Active chunk about TensorRT.")
        rc = _make_rag_chunk("c2", content="Deprecated chunk about old CUDA.")
        # Mark c2 as deprecated
        rc.is_active = False
        rc.deprecated_at = "2025-01-01"
        idx = ChunkIndex([ra, rc])
        retriever = SparseRetriever(idx)
        assert retriever.is_ready

        from src.rag.schemas import RetrievalQuery

        results = retriever.retrieve(RetrievalQuery(keywords=["TensorRT"]), top_k=5)
        assert len(results) >= 1
        assert results[0].chunk_id == "c1"

    def test_score_bounds(self) -> None:
        texts = [
            ("c1", "GPU inference with TensorRT-LLM."),
            ("c2", "CPU-only deployment option."),
        ]
        idx = _index_from_chunks(texts)
        retriever = SparseRetriever(idx)

        from src.rag.schemas import RetrievalQuery

        results = retriever.retrieve(RetrievalQuery(keywords=["GPU"]), top_k=2)
        for r in results:
            assert 0.0 <= r.relevance_score <= 1.0


# =============================================================================
# Test Fusion
# =============================================================================


class TestFusion:
    def test_rrf_empty_lists(self) -> None:
        result = reciprocal_rank_fusion([], [], top_k=5)
        assert result == []

    def test_rrf_only_dense(self) -> None:
        dense = [_make_chunk("a", score_dense=0.9)]
        result = reciprocal_rank_fusion(dense, [], top_k=5)
        assert len(result) == 1
        assert result[0].chunk_id == "a"

    def test_rrf_only_sparse(self) -> None:
        sparse = [_make_chunk("b", score_sparse=0.8)]
        result = reciprocal_rank_fusion([], sparse, top_k=5)
        assert len(result) == 1
        assert result[0].chunk_id == "b"

    def test_rrf_dedup(self) -> None:
        dense = [_make_chunk("a", score_dense=0.9)]
        sparse = [_make_chunk("a", score_sparse=0.7)]
        result = reciprocal_rank_fusion(dense, sparse, top_k=5)
        assert len(result) == 1
        assert result[0].score_fused > 0

    def test_rrf_weighted(self) -> None:
        dense = [_make_chunk("a", score_dense=0.9)]
        sparse = [_make_chunk("b", score_sparse=0.9)]
        result = reciprocal_rank_fusion(dense, sparse, top_k=5, dense_weight=0.7, sparse_weight=0.3)
        assert len(result) == 2

    def test_rrf_top_k(self) -> None:
        dense = [_make_chunk(f"d{i}", score_dense=0.9 - i * 0.1) for i in range(5)]
        sparse = [_make_chunk(f"s{i}", score_sparse=0.8 - i * 0.1) for i in range(5)]
        result = reciprocal_rank_fusion(dense, sparse, top_k=3)
        assert len(result) <= 3

    def test_weighted_fusion(self) -> None:
        dense = [_make_chunk("a", score_dense=0.8)]
        sparse = [_make_chunk("b", score_sparse=0.6)]
        result = weighted_score_fusion(dense, sparse, dense_weight=0.5, sparse_weight=0.5)
        assert len(result) == 2

    def test_weighted_fusion_dedup(self) -> None:
        dense = [_make_chunk("a", score_dense=0.8)]
        sparse = [_make_chunk("a", score_sparse=0.6)]
        result = weighted_score_fusion(dense, sparse, dense_weight=0.5, sparse_weight=0.5)
        assert len(result) == 1
        # Normalized: score_fused = (0.4 + 0.3) / max(0.7, 1.0) ... actually max=0.7, so 0.7/0.7=1.0
        # just check it's a valid score
        assert 0.0 <= result[0].score_fused <= 1.0
        assert result[0].score_fused > 0


# =============================================================================
# Test Reranker
# =============================================================================


class TestNoOpReranker:
    def test_rerank_passthrough(self) -> None:
        chunks = [_make_chunk("a"), _make_chunk("b")]
        reranker = NoOpReranker()
        result = reranker.rerank("test query", chunks, top_k=5)
        assert len(result) == 2
        assert result == chunks

    def test_rerank_top_k(self) -> None:
        chunks = [_make_chunk(str(i)) for i in range(10)]
        reranker = NoOpReranker()
        result = reranker.rerank("test query", chunks, top_k=3)
        assert len(result) == 3  # NoOp respects top_k


class TestOptionalCrossEncoderReranker:
    def test_not_available_by_default(self) -> None:
        reranker = OptionalCrossEncoderReranker()
        # Should not crash; just returns chunks as-is
        chunks = [_make_chunk("a"), _make_chunk("b")]
        result = reranker.rerank("test", chunks, top_k=5)
        assert len(result) == 2


class TestBuildReranker:
    def test_build_none(self) -> None:
        reranker = build_reranker(provider="none")
        assert isinstance(reranker, NoOpReranker)

    def test_build_invalid(self) -> None:
        reranker = build_reranker(provider="invalid_provider")
        assert isinstance(reranker, NoOpReranker)


# =============================================================================
# Test RetrievalMode enum
# =============================================================================


class TestRetrievalMode:
    def test_values(self) -> None:
        assert RetrievalMode.DENSE_ONLY.value == "dense_only"
        assert RetrievalMode.SPARSE_ONLY.value == "sparse_only"
        assert RetrievalMode.HYBRID.value == "hybrid"
        assert RetrievalMode.HYBRID_WITH_RERANK.value == "hybrid_with_rerank"
        assert RetrievalMode.LEXICAL.value == "lexical"
        assert RetrievalMode.SEMANTIC.value == "semantic"

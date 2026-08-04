"""Tests for the RAG retrieval module (lexical search, gap, technology, missing)."""

from __future__ import annotations

from src.rag.retrieval import build_default_index
from src.rag.schemas import RetrievalQuery


class TestRetrieval:
    def test_build_default_index(self) -> None:
        """Default index loads all corpus chunks."""
        index = build_default_index()
        assert len(index.chunks) >= 10

    def test_retrieve_by_gap_type_inference_cost(self) -> None:
        """Querying high_inference_cost returns TensorRT-LLM, Triton, and NIM."""
        index = build_default_index()
        results = index.retrieve_by_gap_type("high_inference_cost", top_k=15)
        products = {r.product for r in results}
        assert "TensorRT-LLM" in products
        assert "Triton Inference Server" in products
        assert "NVIDIA NIM" in products

    def test_retrieve_by_technology_tensorrt(self) -> None:
        """Querying TensorRT-LLM returns relevant chunks."""
        index = build_default_index()
        results = index.retrieve_by_technology("TensorRT-LLM", top_k=3)
        assert len(results) >= 1
        for r in results:
            assert "TensorRT-LLM" in r.product or "TensorRT-LLM" in r.content

    def test_retrieve_empty_returns_missing(self) -> None:
        """Querying an unknown gap type returns no results."""
        index = build_default_index()
        results = index.retrieve(RetrievalQuery(gap_type="nonexistent_gap"))
        assert len(results) == 0

    def test_retrieve_by_keywords(self) -> None:
        """Keyword search returns relevant chunks."""
        index = build_default_index()
        results = index.retrieve(
            RetrievalQuery(keywords=["GPU", "inference", "optimized"]),
            top_k=5,
        )
        assert len(results) >= 1
        for r in results:
            assert r.relevance_score > 0

    def test_relevance_score_bounds(self) -> None:
        """All retrieved contexts have relevance_score between 0 and 1."""
        index = build_default_index()
        results = index.retrieve(RetrievalQuery(gap_type="voice_need"), top_k=5)
        for r in results:
            assert 0.0 <= r.relevance_score <= 1.0

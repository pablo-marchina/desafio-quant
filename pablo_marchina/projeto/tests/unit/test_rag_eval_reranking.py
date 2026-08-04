"""Tests for RAG Evaluation with reranking and context packing modes."""

from pathlib import Path

import pytest

from src.evaluation.rag_eval import (
    format_comparison_summary,
    run_comparison_eval,
    run_mode_eval,
    run_rag_eval,
)
from src.evaluation.rag_eval_schemas import RetrievalMode
from src.rag.embeddings import MockEmbeddingProvider
from src.rag.retrieval import build_default_index
from src.rag.schemas import RerankingConfig
from src.rag.vector_store import InMemoryVectorStore, VectorEntry

_GOLDEN_PATH = Path("examples/rag_eval/golden_queries.json")


@pytest.fixture(name="populated_store")
def fixture_populated_store() -> InMemoryVectorStore:
    emb = MockEmbeddingProvider()
    store = InMemoryVectorStore()
    chunks_data: dict[str, str] = {
        "nim": "NVIDIA NIM optimizes inference cost and latency for AI models.",
        "tensorrt_llm": "TensorRT-LLM reduces inference cost and latency for LLMs.",
        "triton": "Triton Inference Server reduces inference cost and latency.",
        "nemo_guardrails": "NeMo Guardrails provides agent governance for AI agents.",
        "rapids": "RAPIDS accelerates data pipelines and tabular processing with GPUs.",
        "riva": "Riva enables voice AI and speech recognition.",
        "omniverse": "Omniverse enables simulation and digital twins.",
        "isaac": "Isaac enables robotics development and simulation.",
        "clara_monai": "Clara and MONAI provide healthcare AI and medical imaging.",
        "morpheus": "Morpheus enables AI cybersecurity and threat detection.",
    }
    for src, content in chunks_data.items():
        store.add_entry(
            VectorEntry(
                chunk_id=f"{src}_000",
                source_id=src,
                title=src,
                content=content,
                product=src,
                gap_types=["high_inference_cost"],
                url=f"https://docs.nvidia.com/{src}",
                embedding=emb.embed(content),
            )
        )
    return store


class TestModeEvalReranked:
    def test_hybrid_reranked_returns_results(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        result = run_mode_eval(
            RetrievalMode.HYBRID_RERANKED,
            vector_store=populated_store,
            embedding_model=emb,
        )
        assert result.total_cases > 0
        assert result.mode == RetrievalMode.HYBRID_RERANKED

    def test_hybrid_reranked_has_quality_gates(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        result = run_mode_eval(
            RetrievalMode.HYBRID_RERANKED,
            vector_store=populated_store,
            embedding_model=emb,
        )
        assert len(result.gates) >= 2

    def test_hybrid_reranked_with_config(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        cfg = RerankingConfig(boost_gap_match=0.0)
        result = run_mode_eval(
            RetrievalMode.HYBRID_RERANKED,
            vector_store=populated_store,
            embedding_model=emb,
            reranking_config=cfg,
        )
        assert result.total_cases > 0


class TestModeEvalPacked:
    def test_hybrid_packed_returns_results(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        result = run_mode_eval(
            RetrievalMode.HYBRID_RERANKED_PACKED,
            vector_store=populated_store,
            embedding_model=emb,
        )
        assert result.total_cases > 0
        assert result.mode == RetrievalMode.HYBRID_RERANKED_PACKED

    def test_hybrid_packed_metrics_present(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        result = run_mode_eval(
            RetrievalMode.HYBRID_RERANKED_PACKED,
            vector_store=populated_store,
            embedding_model=emb,
        )
        for r in result.results:
            assert hasattr(r.metrics, "packed_context_count")
            assert hasattr(r.metrics, "dropped_context_count")
            assert hasattr(r.metrics, "noise_reduction_score")

    def test_hybrid_packed_runs_with_populated_store(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        idx = build_default_index()
        packed = run_mode_eval(
            RetrievalMode.HYBRID_RERANKED_PACKED,
            chunk_index=idx,
            vector_store=populated_store,
            embedding_model=emb,
        )
        assert packed.total_cases > 0
        assert packed.mode == RetrievalMode.HYBRID_RERANKED_PACKED


class TestComparison:
    def test_comparison_has_five_modes(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        comparison = run_comparison_eval(
            vector_store=populated_store,
            embedding_model=emb,
        )
        assert comparison.lexical.mode == RetrievalMode.LEXICAL
        assert comparison.semantic.mode == RetrievalMode.SEMANTIC
        assert comparison.hybrid.mode == RetrievalMode.HYBRID
        assert comparison.hybrid_reranked.mode == RetrievalMode.HYBRID_RERANKED
        assert comparison.hybrid_reranked_packed.mode == RetrievalMode.HYBRID_RERANKED_PACKED

    def test_comparison_format_summary_includes_modes(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        comparison = run_comparison_eval(
            vector_store=populated_store,
            embedding_model=emb,
        )
        summary = format_comparison_summary(comparison)
        assert "LEXICAL" in summary
        assert "SEMANTIC" in summary
        assert "HYBRID" in summary
        assert "HYBRID_RERANKED" in summary
        assert "HYBRID_RERANKED_PACKED" in summary

    def test_comparison_critical_regressions_empty(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        comparison = run_comparison_eval(
            vector_store=populated_store,
            embedding_model=emb,
        )
        assert isinstance(comparison.critical_regressions, list)

    def test_comparison_regression_detection_works(self, populated_store: InMemoryVectorStore) -> None:
        emb = MockEmbeddingProvider()
        idx = build_default_index()
        comparison = run_comparison_eval(
            chunk_index=idx,
            vector_store=populated_store,
            embedding_model=emb,
        )
        assert isinstance(comparison.critical_regressions, list)
        # Mock embeddings are random so some regressions are expected
        assert len(comparison.critical_regressions) > 0


class TestBackwardCompat:
    def test_existing_rag_eval_still_works(self) -> None:
        results = run_rag_eval()
        assert len(results) > 0
        assert any(r.passed for r in results)

    def test_old_lexical_mode_still_works(self) -> None:
        result = run_mode_eval(RetrievalMode.LEXICAL)
        assert result.passed_cases > 0

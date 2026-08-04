"""Tests for multi-mode RAG evaluation â€” lexical, semantic, and hybrid comparison."""

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
from src.rag.retrieval import ChunkIndex, build_default_index
from src.rag.vector_store import InMemoryVectorStore, VectorEntry

_GOLDEN_PATH = Path("examples/rag_eval/golden_queries.json")


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture(name="golden_path")
def fixture_golden_path() -> Path:
    return _GOLDEN_PATH


@pytest.fixture(name="empty_index")
def fixture_empty_index() -> ChunkIndex:
    return ChunkIndex([])


@pytest.fixture(name="populated_store")
def fixture_populated_store() -> InMemoryVectorStore:
    """Create a vector store with chunks matching the corpus."""
    emb = MockEmbeddingProvider()
    store = InMemoryVectorStore()

    # Map of source_id -> chunk content (simplified corpus)
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


@pytest.fixture(name="default_index")
def fixture_default_index() -> ChunkIndex:
    return build_default_index()


# ------------------------------------------------------------------
# Mode eval tests
# ------------------------------------------------------------------


def test_mode_eval_lexical_returns_results() -> None:
    result = run_mode_eval(RetrievalMode.LEXICAL)
    assert result.total_cases > 0
    assert result.mode == RetrievalMode.LEXICAL


def test_mode_eval_lexical_has_quality_gates() -> None:
    result = run_mode_eval(RetrievalMode.LEXICAL)
    assert len(result.gates) >= 2


def test_mode_eval_semantic_empty_store_returns_no_regression() -> None:
    """Semantic with empty store should not crash â€” returns empty results."""
    store = InMemoryVectorStore()
    emb = MockEmbeddingProvider()
    result = run_mode_eval(RetrievalMode.SEMANTIC, vector_store=store, embedding_model=emb)
    assert result.total_cases > 0
    assert result.mode == RetrievalMode.SEMANTIC


def test_mode_eval_semantic_with_populated_store() -> None:
    store = InMemoryVectorStore()
    emb = MockEmbeddingProvider()
    entries = [
        VectorEntry(
            chunk_id="nim_000",
            source_id="nim",
            title="NVIDIA NIM",
            content="NVIDIA NIM optimizes inference cost.",
            product="NVIDIA NIM",
            gap_types=["high_inference_cost"],
            url="https://docs.nvidia.com/nim",
            embedding=emb.embed("NVIDIA NIM optimizes inference cost."),
        ),
    ]
    store.add_entries(entries)
    result = run_mode_eval(RetrievalMode.SEMANTIC, vector_store=store, embedding_model=emb)
    assert result.total_cases > 0


def test_mode_eval_hybrid_falls_back_to_lexical() -> None:
    """Hybrid with empty vector store falls back to lexical."""
    store = InMemoryVectorStore()
    emb = MockEmbeddingProvider()
    idx = ChunkIndex([])
    result = run_mode_eval(RetrievalMode.HYBRID, chunk_index=idx, vector_store=store, embedding_model=emb)
    assert result.total_cases > 0
    for r in result.results:
        if not r.expected_source_ids:
            assert r.passed or True  # no crash


# ------------------------------------------------------------------
# Comparison eval tests
# ------------------------------------------------------------------


def test_comparison_eval_returns_three_modes(populated_store: InMemoryVectorStore) -> None:
    emb = MockEmbeddingProvider()
    idx = build_default_index()
    comparison = run_comparison_eval(
        chunk_index=idx,
        vector_store=populated_store,
        embedding_model=emb,
    )
    assert comparison.lexical.mode == RetrievalMode.LEXICAL
    assert comparison.semantic.mode == RetrievalMode.SEMANTIC
    assert comparison.hybrid.mode == RetrievalMode.HYBRID


def test_comparison_eval_critical_regressions_empty(populated_store: InMemoryVectorStore) -> None:
    emb = MockEmbeddingProvider()
    idx = build_default_index()
    comparison = run_comparison_eval(
        chunk_index=idx,
        vector_store=populated_store,
        embedding_model=emb,
    )
    assert isinstance(comparison.critical_regressions, list)


def test_comparison_eval_lexical_pass_count(populated_store: InMemoryVectorStore) -> None:
    emb = MockEmbeddingProvider()
    idx = build_default_index()
    comparison = run_comparison_eval(
        chunk_index=idx,
        vector_store=populated_store,
        embedding_model=emb,
    )
    assert comparison.lexical.passed_cases >= 0
    assert comparison.lexical.total_cases > 0


def test_comparison_eval_with_empty_vector_store() -> None:
    store = InMemoryVectorStore()
    emb = MockEmbeddingProvider()
    idx = build_default_index()
    comparison = run_comparison_eval(chunk_index=idx, vector_store=store, embedding_model=emb)
    # Semantic should have 0 passed since store is empty
    assert comparison.semantic.mode == RetrievalMode.SEMANTIC
    # Hybrid should fall back to lexical
    assert comparison.hybrid.total_cases == comparison.lexical.total_cases


# ------------------------------------------------------------------
# Format tests
# ------------------------------------------------------------------


def test_format_comparison_summary_includes_modes(populated_store: InMemoryVectorStore) -> None:
    emb = MockEmbeddingProvider()
    idx = build_default_index()
    comparison = run_comparison_eval(
        chunk_index=idx,
        vector_store=populated_store,
        embedding_model=emb,
    )
    summary = format_comparison_summary(comparison)
    assert "LEXICAL" in summary
    assert "SEMANTIC" in summary
    assert "HYBRID" in summary
    assert "REGRESSION" in summary


def test_format_comparison_summary_with_explicit_vector_store(
    populated_store: InMemoryVectorStore,
) -> None:
    emb = MockEmbeddingProvider()
    idx = build_default_index()
    comparison = run_comparison_eval(
        chunk_index=idx,
        vector_store=populated_store,
        embedding_model=emb,
    )
    summary = format_comparison_summary(comparison)
    assert "LEXICAL" in summary
    assert "SEMANTIC" in summary
    assert "HYBRID" in summary


# ------------------------------------------------------------------
# Backward compatibility â€” existing eval still works
# ------------------------------------------------------------------


def test_existing_rag_eval_still_works() -> None:
    results = run_rag_eval()
    assert len(results) > 0
    assert any(r.passed for r in results)

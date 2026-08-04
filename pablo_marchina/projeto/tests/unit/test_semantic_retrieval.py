"""Tests for src.rag.semantic_retrieval â€” semantic_retrieve()."""

from src.rag.embeddings import MockEmbeddingProvider
from src.rag.schemas import RetrievalQuery, RetrievedContext
from src.rag.semantic_retrieval import _build_query_text, semantic_retrieve
from src.rag.vector_store import InMemoryVectorStore, VectorEntry


def _make_store() -> InMemoryVectorStore:
    """Create a populated vector store for testing."""
    emb = MockEmbeddingProvider()
    store = InMemoryVectorStore()
    entries = [
        VectorEntry(
            chunk_id="nim_000",
            source_id="nim",
            title="NVIDIA NIM",
            content="NVIDIA NIM optimizes inference cost and latency.",
            product="NVIDIA NIM",
            gap_types=["high_inference_cost", "high_latency", "external_api_dependency"],
            url="https://docs.nvidia.com/nim",
            embedding=emb.embed("NVIDIA NIM optimizes inference cost and latency."),
        ),
        VectorEntry(
            chunk_id="tensorrt_llm_000",
            source_id="tensorrt_llm",
            title="TensorRT-LLM",
            content="TensorRT-LLM reduces inference cost and latency.",
            product="TensorRT-LLM",
            gap_types=["high_inference_cost", "high_latency"],
            url="https://docs.nvidia.com/tensorrt-llm",
            embedding=emb.embed("TensorRT-LLM reduces inference cost and latency."),
        ),
        VectorEntry(
            chunk_id="nim_001",
            source_id="nim",
            title="NVIDIA NIM",
            content="NIM can replace external API dependencies.",
            product="NVIDIA NIM",
            gap_types=["external_api_dependency"],
            url="https://docs.nvidia.com/nim",
            embedding=emb.embed("NIM can replace external API dependencies."),
        ),
    ]
    store.add_entries(entries)
    return store


def test_semantic_retrieve_returns_contexts() -> None:
    store = _make_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost", keywords=["inference"])

    results = semantic_retrieve(query, emb, store, top_k=3)
    assert len(results) > 0
    assert all(isinstance(r, RetrievedContext) for r in results)


def test_semantic_retrieve_preserves_provenance() -> None:
    store = _make_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = semantic_retrieve(query, emb, store, top_k=3)
    for r in results:
        assert r.source_id, f"Missing source_id on {r.chunk_id}"
        assert r.url, f"Missing url on {r.chunk_id}"
        assert r.product, f"Missing product on {r.chunk_id}"


def test_semantic_retrieve_empty_store() -> None:
    store = InMemoryVectorStore()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = semantic_retrieve(query, emb, store, top_k=3)
    assert results == []


def test_semantic_retrieve_filter_by_product() -> None:
    store = _make_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = semantic_retrieve(query, emb, store, top_k=5, product="TensorRT-LLM")
    assert all(r.product == "TensorRT-LLM" for r in results)


def test_semantic_retrieve_filter_by_gap_type() -> None:
    store = _make_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = semantic_retrieve(query, emb, store, top_k=5, gap_type="external_api_dependency")
    assert all("external_api_dependency" in r.gap_types for r in results)


def test_semantic_retrieve_filter_by_source_id() -> None:
    store = _make_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = semantic_retrieve(query, emb, store, top_k=5, source_id="tensorrt_llm")
    assert all(r.source_id == "tensorrt_llm" for r in results)


def test_semantic_retrieve_top_k_respected() -> None:
    store = _make_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = semantic_retrieve(query, emb, store, top_k=1)
    assert len(results) == 1


def test_semantic_retrieve_relevance_score_in_range() -> None:
    store = _make_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = semantic_retrieve(query, emb, store, top_k=3)
    for r in results:
        assert 0.0 <= r.relevance_score <= 1.0


def test_semantic_retrieve_combined_filter() -> None:
    store = _make_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = semantic_retrieve(
        query,
        emb,
        store,
        top_k=5,
        product="NVIDIA NIM",
        gap_type="external_api_dependency",
    )
    for r in results:
        assert r.product == "NVIDIA NIM"
        assert "external_api_dependency" in r.gap_types


def test_build_query_text_with_gap_type() -> None:
    q = RetrievalQuery(gap_type="high_inference_cost")
    text = _build_query_text(q)
    assert "high inference cost" in text


def test_build_query_text_with_technology() -> None:
    q = RetrievalQuery(gap_type="high_latency", technology="TensorRT-LLM")
    text = _build_query_text(q)
    assert "high latency" in text
    assert "TensorRT-LLM" in text


def test_build_query_text_with_keywords() -> None:
    q = RetrievalQuery(gap_type="voice_need", keywords=["speech", "recognition"])
    text = _build_query_text(q)
    assert "voice need" in text
    assert "speech" in text
    assert "recognition" in text


def test_build_query_text_empty() -> None:
    q = RetrievalQuery()
    text = _build_query_text(q)
    assert text == ""

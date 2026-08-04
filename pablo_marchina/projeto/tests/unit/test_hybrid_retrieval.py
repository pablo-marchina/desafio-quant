"""Tests for src.rag.hybrid_retrieval â€” hybrid_retrieve() with RRF fusion."""

from src.rag.embeddings import MockEmbeddingProvider
from src.rag.hybrid_retrieval import _rrf_fuse, hybrid_retrieve
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RagChunk, RetrievalQuery, RetrievedContext
from src.rag.vector_store import InMemoryVectorStore, VectorEntry


def _make_index() -> ChunkIndex:
    """Create a ChunkIndex with two chunks for testing."""
    chunks = [
        RagChunk(
            chunk_id="nim_000",
            source_id="nim",
            title="NVIDIA NIM",
            content="NVIDIA NIM optimizes inference cost.",
            product="NVIDIA NIM",
            gap_types=["high_inference_cost", "high_latency"],
            url="https://docs.nvidia.com/nim",
        ),
        RagChunk(
            chunk_id="tensorrt_llm_000",
            source_id="tensorrt_llm",
            title="TensorRT-LLM",
            content="TensorRT-LLM reduces inference cost and latency.",
            product="TensorRT-LLM",
            gap_types=["high_inference_cost", "high_latency"],
            url="https://docs.nvidia.com/tensorrt-llm",
        ),
        RagChunk(
            chunk_id="nim_001",
            source_id="nim",
            title="NVIDIA NIM",
            content="NIM can replace external API dependencies.",
            product="NVIDIA NIM",
            gap_types=["external_api_dependency"],
            url="https://docs.nvidia.com/nim",
        ),
    ]
    return ChunkIndex(chunks)


def _make_vector_store(seed_texts: dict[str, str] | None = None) -> InMemoryVectorStore:
    """Populate a vector store with entries matching the index."""
    emb = MockEmbeddingProvider()
    store = InMemoryVectorStore()
    defaults = {
        "nim_000": "NVIDIA NIM optimizes inference cost.",
        "tensorrt_llm_000": "TensorRT-LLM reduces inference cost and latency.",
        "nim_001": "NIM can replace external API dependencies.",
    }
    texts = seed_texts or defaults
    for cid, text in texts.items():
        store.add_entry(
            VectorEntry(
                chunk_id=cid,
                source_id=cid.split("_")[0],
                title="",
                content=text,
                product="NVIDIA NIM" if cid.startswith("nim") else "TensorRT-LLM",
                gap_types=["high_inference_cost"] if "nim" in cid else ["high_latency"],
                url="https://docs.nvidia.com/test",
                embedding=emb.embed(text),
            )
        )
    return store


def test_hybrid_retrieve_falls_back_to_lexical_when_vector_store_empty() -> None:
    index = _make_index()
    store = InMemoryVectorStore()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = hybrid_retrieve(query, index, emb, store, top_k=3)
    assert len(results) > 0
    assert results[0].source_id in ("nim", "tensorrt_llm")


def test_hybrid_retrieve_with_semantic_and_lexical() -> None:
    index = _make_index()
    store = _make_vector_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = hybrid_retrieve(query, index, emb, store, top_k=3)
    assert len(results) > 0
    # Should include results from both sources
    assert all(isinstance(r, RetrievedContext) for r in results)


def test_hybrid_retrieve_preserves_provenance() -> None:
    index = _make_index()
    store = _make_vector_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = hybrid_retrieve(query, index, emb, store, top_k=3)
    for r in results:
        assert r.source_id, f"Missing source_id on {r.chunk_id}"
        assert r.url, f"Missing url on {r.chunk_id}"
        assert r.product, f"Missing product on {r.chunk_id}"


def test_hybrid_retrieve_top_k_respected() -> None:
    index = _make_index()
    store = _make_vector_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = hybrid_retrieve(query, index, emb, store, top_k=2)
    assert len(results) <= 2


def test_hybrid_retrieve_relevance_score_in_range() -> None:
    index = _make_index()
    store = _make_vector_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = hybrid_retrieve(query, index, emb, store, top_k=3)
    for r in results:
        assert 0.0 <= r.relevance_score <= 1.0


def test_hybrid_retrieve_filter_by_product() -> None:
    index = _make_index()
    store = _make_vector_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = hybrid_retrieve(query, index, emb, store, top_k=5, product="NVIDIA NIM")
    if results:
        assert all(r.product == "NVIDIA NIM" for r in results)


def test_hybrid_retrieve_filter_by_gap_type() -> None:
    index = _make_index()
    store = _make_vector_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = hybrid_retrieve(query, index, emb, store, top_k=5, gap_type="high_latency")
    if results:
        assert all("high_latency" in r.gap_types for r in results)


def test_hybrid_retrieve_filter_by_source_id() -> None:
    index = _make_index()
    store = _make_vector_store()
    emb = MockEmbeddingProvider()
    query = RetrievalQuery(gap_type="high_inference_cost")

    results = hybrid_retrieve(query, index, emb, store, top_k=5, source_id="nim")
    if results:
        assert all(r.source_id == "nim" for r in results)


def test_rrf_fuse_both_empty() -> None:
    result = _rrf_fuse([], [], top_k=3)
    assert result == []


def test_rrf_fuse_only_lexical() -> None:
    ctx = RetrievedContext(
        chunk_id="a",
        source_id="s1",
        title="",
        content="",
        product="P1",
        gap_types=[],
        url=None,
        relevance_score=0.5,
    )
    result = _rrf_fuse([ctx], [], top_k=3)
    assert len(result) == 1
    assert result[0].chunk_id == "a"


def test_rrf_fuse_only_semantic() -> None:
    ctx = RetrievedContext(
        chunk_id="b",
        source_id="s2",
        title="",
        content="",
        product="P2",
        gap_types=[],
        url=None,
        relevance_score=0.5,
    )
    result = _rrf_fuse([], [ctx], top_k=3)
    assert len(result) == 1
    assert result[0].chunk_id == "b"


def test_rrf_fuse_merges_deduplicated() -> None:
    ctx_a = RetrievedContext(
        chunk_id="a",
        source_id="s1",
        title="",
        content="",
        product="P1",
        gap_types=[],
        url=None,
        relevance_score=0.5,
    )
    ctx_b = RetrievedContext(
        chunk_id="b",
        source_id="s2",
        title="",
        content="",
        product="P2",
        gap_types=[],
        url=None,
        relevance_score=0.5,
    )
    # Same element in both lists should appear once
    result = _rrf_fuse([ctx_a, ctx_b], [ctx_b], top_k=3)
    assert len(result) <= 2
    ids = [r.chunk_id for r in result]
    assert ids.count("b") == 1

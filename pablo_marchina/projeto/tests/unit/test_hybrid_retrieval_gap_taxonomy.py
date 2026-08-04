from __future__ import annotations

from src.rag.embeddings import EmbeddingProvider
from src.rag.hybrid_retrieval import (
    _apply_filters,
    _gap_type_aliases,
    hybrid_retrieve,
)
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RagChunk, RetrievalQuery, RetrievedContext
from src.rag.vector_store import InMemoryVectorStore, VectorEntry


class _DeterministicEmbeddingProvider(EmbeddingProvider):
    def embed(self, text: str) -> list[float]:
        normalized = text.casefold()
        if "computer vision" in normalized or "tensorrt" in normalized:
            return [1.0, 0.0]
        return [0.0, 1.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


def _context(chunk_id: str, product: str, gap_types: list[str]) -> RetrievedContext:
    return RetrievedContext(
        chunk_id=chunk_id,
        source_id=f"source-{chunk_id}",
        title=product,
        content=f"Official NVIDIA context for {product}.",
        product=product,
        gap_types=gap_types,
        url=f"https://docs.nvidia.com/{chunk_id}",
        relevance_score=0.9,
    )


def _chunk(
    chunk_id: str,
    product: str,
    gap_types: list[str],
    content: str,
) -> RagChunk:
    return RagChunk(
        chunk_id=chunk_id,
        source_id=f"source-{chunk_id}",
        title=product,
        content=content,
        product=product,
        gap_types=gap_types,
        url=f"https://docs.nvidia.com/{chunk_id}",
    )


def _entry(chunk: RagChunk, embedding: list[float]) -> VectorEntry:
    return VectorEntry(
        chunk_id=chunk.chunk_id,
        source_id=chunk.source_id,
        title=chunk.title,
        content=chunk.content,
        product=chunk.product,
        gap_types=list(chunk.gap_types),
        url=chunk.url,
        embedding=embedding,
    )


def _vision_fixture() -> tuple[ChunkIndex, InMemoryVectorStore]:
    tensor_rt = _chunk(
        "tensorrt-cv",
        "TensorRT",
        ["computer_vision_need", "high_latency"],
        "TensorRT accelerates industrial computer vision inference and object detection.",
    )
    riva = _chunk(
        "riva-speech",
        "NVIDIA Riva",
        ["voice_need"],
        "Riva provides speech recognition and text to speech services.",
    )
    index = ChunkIndex([tensor_rt, riva])
    store = InMemoryVectorStore()
    store.add_entries(
        [
            _entry(tensor_rt, [1.0, 0.0]),
            _entry(riva, [0.0, 1.0]),
        ]
    )
    return index, store


def test_diagnosis_gap_expands_to_technical_corpus_alias() -> None:
    aliases = _gap_type_aliases("computer_vision_gap")
    assert "computer_vision_gap" in aliases
    assert "computer_vision_need" in aliases


def test_alias_aware_filter_keeps_tensor_rt_context_and_rejects_voice() -> None:
    contexts = [
        _context("tensorrt", "TensorRT", ["computer_vision_need", "high_latency"]),
        _context("riva", "NVIDIA Riva", ["voice_need"]),
    ]

    filtered = _apply_filters(contexts, gap_type="computer_vision_gap")

    assert [context.product for context in filtered] == ["TensorRT"]


def test_hybrid_retrieval_translates_gap_before_bm25_dense_and_graph(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("RAG_VECTOR_BACKEND", "in_memory")
    index, store = _vision_fixture()

    contexts = hybrid_retrieve(
        query=RetrievalQuery(
            gap_type="computer_vision_gap",
            technology="TensorRT",
        ),
        chunk_index=index,
        embedding_model=_DeterministicEmbeddingProvider(),
        vector_store=store,
        top_k=3,
        gap_type="computer_vision_gap",
    )

    assert contexts
    assert {context.product for context in contexts} == {"TensorRT"}
    assert all("computer_vision_gap" in context.gap_types for context in contexts)
    assert all("computer_vision_need" in context.gap_types for context in contexts)


def test_product_hybrid_retrieval_fails_closed_without_dense_gap_candidate(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("RAG_VECTOR_BACKEND", "in_memory")
    index, store = _vision_fixture()
    store.remove_entry("tensorrt-cv")
    monkeypatch.setenv("APP_MODE", "product")

    contexts = hybrid_retrieve(
        query=RetrievalQuery(
            gap_type="computer_vision_gap",
            technology="TensorRT",
        ),
        chunk_index=index,
        embedding_model=_DeterministicEmbeddingProvider(),
        vector_store=store,
        top_k=3,
        gap_type="computer_vision_gap",
    )

    assert contexts == []

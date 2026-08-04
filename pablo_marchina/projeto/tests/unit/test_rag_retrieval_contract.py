from __future__ import annotations

from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RagChunk, RetrievalQuery


def _chunk(source_id: str, product: str, index: int, *, gap: str = "high_latency") -> RagChunk:
    return RagChunk(
        chunk_id=f"{source_id}_{index:03d}",
        source_id=source_id,
        title=product,
        content=f"{product} production inference latency guidance section {index}",
        product=product,
        nvidia_technology=product,
        gap_types=[gap],
        url=f"https://docs.nvidia.com/{source_id}/{index}",
    )


def test_gap_and_technology_query_is_conjunctive() -> None:
    index = ChunkIndex(
        [
            _chunk("nim", "NVIDIA NIM", 0),
            _chunk("nim", "NVIDIA NIM", 1),
            _chunk("triton", "Triton Inference Server", 0),
            _chunk("triton", "Triton Inference Server", 1),
        ]
    )

    results = index.retrieve(
        RetrievalQuery(gap_type="high_latency", technology="Triton Inference Server"),
        top_k=3,
    )

    assert results
    assert {result.source_id for result in results} == {"triton"}


def test_gap_query_covers_sources_before_duplicate_chunks() -> None:
    index = ChunkIndex(
        [
            *[_chunk("nim", "NVIDIA NIM", idx) for idx in range(5)],
            *[_chunk("tensorrt_llm", "TensorRT-LLM", idx) for idx in range(5)],
            *[_chunk("triton", "Triton Inference Server", idx) for idx in range(5)],
        ]
    )

    results = index.retrieve(RetrievalQuery(gap_type="high_latency"), top_k=3)

    assert [result.source_id for result in results] == ["nim", "tensorrt_llm", "triton"]


def test_keyword_query_uses_governed_aliases_not_incidental_content() -> None:
    chunks = [
        _chunk("nim", "NVIDIA NIM", 0),
        _chunk("riva", "NVIDIA Riva", 0, gap="voice_need"),
    ]
    chunks[1].content = "Navigation script mentions inference but the governed Riva aliases do not."
    index = ChunkIndex(chunks)

    results = index.retrieve(RetrievalQuery(keywords=["inference"]), top_k=3)

    assert [result.source_id for result in results] == ["nim"]


def test_keyword_normalization_matches_hyphenated_aliases() -> None:
    index = ChunkIndex(
        [
            _chunk("cudf", "cuDF", 0, gap="slow_data_pipeline"),
            _chunk("nim", "NVIDIA NIM", 0),
        ]
    )

    hyphenated = index.retrieve(RetrievalQuery(keywords=["open-source"]), top_k=5)
    spaced = index.retrieve(RetrievalQuery(keywords=["open source"]), top_k=5)

    assert [item.source_id for item in hyphenated] == ["cudf"]
    assert [item.source_id for item in spaced] == ["cudf"]

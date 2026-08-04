from __future__ import annotations

from pathlib import Path

from src.rag.ingestion import chunk_document, load_markdown_document
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RagChunk, RagDocument, RetrievalQuery


def _chunk(
    chunk_id: str,
    source_id: str,
    product: str,
    content: str,
    gaps: list[str],
) -> RagChunk:
    return RagChunk(
        chunk_id=chunk_id,
        source_id=source_id,
        title=product,
        content=content,
        product=product,
        nvidia_technology=product,
        gap_types=gaps,
        url=f"https://example.com/{source_id}",
    )


def test_gap_and_technology_query_is_an_intersection() -> None:
    chunks = [
        _chunk(
            "nim_000",
            "nim",
            "NVIDIA NIM",
            "NIM can deploy models optimized with TensorRT-LLM.",
            ["high_inference_cost"],
        ),
        _chunk(
            "tensorrt_000",
            "tensorrt",
            "TensorRT",
            "TensorRT accelerates general deep-learning inference.",
            ["high_inference_cost"],
        ),
        _chunk(
            "tensorrt_llm_000",
            "tensorrt_llm",
            "TensorRT-LLM",
            "TensorRT-LLM reduces LLM inference cost.",
            ["high_inference_cost"],
        ),
        _chunk(
            "triton_000",
            "triton",
            "Triton Inference Server",
            "Triton serves optimized inference workloads.",
            ["high_inference_cost"],
        ),
    ]

    results = ChunkIndex(chunks).retrieve(
        RetrievalQuery(
            gap_type="high_inference_cost",
            technology="TensorRT-LLM",
        ),
        top_k=3,
    )

    assert [result.source_id for result in results] == ["tensorrt_llm"]


def test_tensorrt_query_does_not_match_tensorrt_llm_product() -> None:
    chunks = [
        _chunk(
            "tensorrt_000",
            "tensorrt",
            "TensorRT",
            "TensorRT accelerates computer vision inference.",
            ["computer_vision_need"],
        ),
        _chunk(
            "tensorrt_llm_000",
            "tensorrt_llm",
            "TensorRT-LLM",
            "TensorRT-LLM optimizes large language model inference.",
            ["computer_vision_need"],
        ),
    ]

    results = ChunkIndex(chunks).retrieve(
        RetrievalQuery(
            gap_type="computer_vision_need",
            technology="TensorRT",
        ),
        top_k=3,
    )

    assert [result.source_id for result in results] == ["tensorrt"]


def test_safe_short_alias_matches_descriptive_product_name() -> None:
    chunks = [
        _chunk(
            "triton_000",
            "triton",
            "Triton Inference Server",
            "Triton serves optimized inference workloads.",
            ["high_latency"],
        )
    ]

    results = ChunkIndex(chunks).retrieve(
        RetrievalQuery(gap_type="high_latency", technology="Triton"),
        top_k=3,
    )

    assert [result.source_id for result in results] == ["triton"]


def test_broad_gap_query_round_robins_sources() -> None:
    chunks: list[RagChunk] = []
    for source_id, product in (
        ("nim", "NVIDIA NIM"),
        ("tensorrt_llm", "TensorRT-LLM"),
        ("triton", "Triton Inference Server"),
    ):
        for index in range(4):
            chunks.append(
                _chunk(
                    f"{source_id}_{index:03d}",
                    source_id,
                    product,
                    f"Chunk {index} about inference cost.",
                    ["high_inference_cost"],
                )
            )

    results = ChunkIndex(chunks).retrieve(
        RetrievalQuery(gap_type="high_inference_cost"),
        top_k=3,
    )

    assert {result.source_id for result in results} == {
        "nim",
        "tensorrt_llm",
        "triton",
    }


def test_html_source_is_cleaned_before_indexing(tmp_path: Path) -> None:
    path = tmp_path / "nim.md"
    path.write_text(
        """
        <!doctype html>
        <html>
          <head>
            <meta property="og:title" content="NVIDIA NIM">
            <style>.noise { display: none; }</style>
            <script>const navigationNoise = true;</script>
          </head>
          <body>
            <nav>Navigation noise</nav>
            <main>
              <h1>NVIDIA NIM</h1>
              <p>NIM provides production inference microservices.</p>
              <p>It reduces deployment complexity for AI models.</p>
            </main>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    document = load_markdown_document(path)

    assert document is not None
    assert document.title == "NVIDIA NIM"
    assert "production inference microservices" in document.raw_text
    assert "navigationNoise" not in document.raw_text
    assert "<style" not in document.raw_text


def test_unstructured_documents_are_bounded_without_losing_tail_content() -> None:
    paragraphs = [f"Paragraph {index} " + ("useful content " * 80) for index in range(20)]
    document = RagDocument(
        source_id="bounded",
        title="Bounded document",
        raw_text="\n\n".join(paragraphs),
    )

    chunks = chunk_document(document, {})

    assert 1 < len(chunks) <= 5
    assert "Paragraph 0" in chunks[0].content
    assert "Paragraph 19" in chunks[-1].content

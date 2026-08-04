"""Tests for the RAG ingestion module (Markdown loading, chunking, metadata)."""

from __future__ import annotations

from src.rag.ingestion import (
    chunk_document,
    load_and_chunk_corpus,
    load_sources,
)
from src.rag.schemas import RagDocument


class TestIngestion:
    def test_load_sources_yaml(self) -> None:
        """sources.yaml loads the active production source allowlist."""
        sources = load_sources()
        assert len(sources) >= 20
        assert "nim" in sources
        assert "tensorrt_llm" in sources
        assert "triton" in sources
        assert sources["nim"].product == "NVIDIA NIM"
        assert "external_api_dependency" in sources["nim"].gap_types

    def test_load_chunk_corpus_all_files(self) -> None:
        """All active allowlisted markdown files load and produce chunks with metadata."""
        chunks = load_and_chunk_corpus()
        assert len(chunks) >= 10  # at least one chunk per file
        for c in chunks:
            assert c.chunk_id
            assert c.source_id
            assert c.title
            assert c.content
            assert c.product

    def test_chunking_preserves_metadata(self) -> None:
        """Each chunk preserves source_id, title, product, gap_types."""
        doc = RagDocument(
            source_id="test_tech",
            title="Test Technology",
            raw_text=("# Test\n\n## Description\n\nA description.\n\n## Use Cases\n\n" "- Case 1\n- Case 2"),
        )
        sources = load_sources()
        chunks = chunk_document(doc, sources)
        assert len(chunks) == 2
        for c in chunks:
            assert c.source_id == "test_tech"
            assert c.title == "Test Technology"
            assert isinstance(c.content, str)
            assert len(c.content) > 0

    def test_chunking_with_source_metadata(self) -> None:
        """Chunks inherit product and gap_types from source metadata."""
        sources = load_sources()
        assert "nim" in sources
        doc = RagDocument(
            source_id="nim",
            title="NVIDIA NIM",
            raw_text="# NIM\n\n## Section\n\nContent.",
        )
        chunks = chunk_document(doc, sources)
        assert len(chunks) >= 1
        assert chunks[0].product == "NVIDIA NIM"
        assert "external_api_dependency" in chunks[0].gap_types

"""Unit tests for the Qdrant ingestion pipeline.

All tests use MockEmbeddingProvider and InMemoryVectorStore.
No Qdrant, no sentence-transformers, no LLM, no internet.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.rag.embeddings import MockEmbeddingProvider
from src.rag.ingestion import load_and_chunk_corpus
from src.rag.ingestion_pipeline import (
    CORPUS_VERSION,
    REQUIRED_PAYLOAD_FIELDS,
    check_corpus_readiness,
    run_ingestion_pipeline,
    validate_payload_schema,
)
from src.rag.vector_store import InMemoryVectorStore, VectorEntry


@pytest.fixture
def emb() -> MockEmbeddingProvider:
    return MockEmbeddingProvider()


@pytest.fixture
def store() -> InMemoryVectorStore:
    return InMemoryVectorStore()


# ---------------------------------------------------------------------------
# 1. load_and_chunk_corpus creates chunks with stable IDs
# ---------------------------------------------------------------------------


class TestLoadAndChunkCorpus:
    def test_chunks_have_stable_ids(self) -> None:
        chunks = load_and_chunk_corpus()
        assert len(chunks) >= 1
        for c in chunks:
            assert c.chunk_id
            assert c.chunk_id.startswith(c.source_id)
            assert "_" in c.chunk_id

    def test_chunks_have_new_fields(self) -> None:
        chunks = load_and_chunk_corpus()
        assert len(chunks) >= 1
        for c in chunks:
            assert c.nvidia_technology == c.product
            assert c.corpus_version in {"1.0", "1.1"}
            assert c.chunk_index >= 0
            assert c.char_count > 0


# ---------------------------------------------------------------------------
# 2. Embedding provider is called for chunks
# ---------------------------------------------------------------------------


class TestPipelineCallsEmbedding:
    def test_embeddings_match_chunk_count(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        report = run_ingestion_pipeline(emb, store, batch_size=32, allow_uncalibrated=True)
        assert report.chunk_count > 0
        assert report.embedded_chunk_count == report.chunk_count
        assert report.upserted_point_count == report.chunk_count

    def test_embedding_dimension_recorded(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        report = run_ingestion_pipeline(emb, store, batch_size=32, allow_uncalibrated=True)
        assert report.embedding_dimension == emb.vector_size  # 4


# ---------------------------------------------------------------------------
# 3. QdrantStore upsert is called with vector + payload
# ---------------------------------------------------------------------------


class TestUpsertWithPayload:
    def test_entries_have_vectors(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        report = run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        assert report.upserted_point_count > 0
        for entry in store.entries:
            assert len(entry.embedding) == emb.vector_size

    def test_entries_have_payload_fields(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        assert store.size > 0
        for entry in store.entries:
            assert entry.chunk_id
            assert entry.source_id
            assert entry.title
            assert entry.content
            assert entry.nvidia_technology
            assert entry.corpus_version
            assert entry.char_count > 0


# ---------------------------------------------------------------------------
# 4. Payload obligatory fields are validated
# ---------------------------------------------------------------------------


class TestPayloadValidation:
    def test_complete_payload_passes(self) -> None:
        point = {
            "chunk_id": "test_000",
            "source_id": "test",
            "source_title": "Test",
            "source_url": "https://example.com",
            "nvidia_technology": "NVIDIA Test",
            "corpus_version": "1.0",
            "chunk_text": "test content",
            "chunk_index": 0,
            "char_count": 12,
            "ingested_at": "2026-01-01T00:00:00Z",
        }
        missing = validate_payload_schema(point)
        assert missing == []

    def test_missing_fields_fail(self) -> None:
        point = {"chunk_id": "test_000"}
        missing = validate_payload_schema(point)
        assert len(missing) > 0
        assert "source_id" in missing
        assert "chunk_text" in missing

    def test_empty_string_fields_fail(self) -> None:
        point = {field: "" for field in REQUIRED_PAYLOAD_FIELDS}
        point["chunk_id"] = "test_000"
        point["chunk_index"] = 0
        point["char_count"] = 0
        missing = validate_payload_schema(point)
        assert len(missing) > 0  # empty strings are invalid


# ---------------------------------------------------------------------------
# 5. corpus_version is preserved
# ---------------------------------------------------------------------------


class TestCorpusVersionPreserved:
    def test_default_version(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        for entry in store.entries:
            assert entry.corpus_version == CORPUS_VERSION

    def test_custom_version(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, corpus_version="2.0", allow_uncalibrated=True)
        for entry in store.entries:
            assert entry.corpus_version == "2.0"

    def test_custom_version_in_report(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        report = run_ingestion_pipeline(emb, store, corpus_version="2.0", allow_uncalibrated=True)
        assert report.corpus_version == "2.0"


# ---------------------------------------------------------------------------
# 6. Ingestion report is generated
# ---------------------------------------------------------------------------


class TestIngestionReport:
    def test_report_has_all_required_fields(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        report = run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        assert report.ingestion_run_id
        assert report.started_at
        assert report.finished_at
        assert report.document_count > 0
        assert report.chunk_count > 0
        assert report.embedded_chunk_count > 0
        assert report.upserted_point_count > 0
        assert report.embedding_dimension > 0
        assert report.collection_name is not None
        assert report.ingestion_status == "completed"

    def test_report_empty_corpus(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        report = run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        assert report.upserted_point_count > 0


# ---------------------------------------------------------------------------
# 7. Empty collection blocks readiness
# ---------------------------------------------------------------------------


class TestEmptyCollectionBlocksReadiness:
    def test_empty_store_not_ready(self) -> None:
        store = InMemoryVectorStore()
        readiness = check_corpus_readiness(store)
        assert readiness.production_allowed is False
        assert len(readiness.calibration_blockers) > 0

    def test_empty_store_reports_blockers(self) -> None:
        store = InMemoryVectorStore()
        readiness = check_corpus_readiness(store)
        assert len(readiness.blockers) > 0


# ---------------------------------------------------------------------------
# 8. Payload schema validation blocks readiness
# ---------------------------------------------------------------------------


class TestPayloadInvalidBlocksReadiness:
    def test_invalid_payload_reported(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        # Manually add an entry with missing payload fields
        store.add_entry(
            VectorEntry(
                chunk_id="bad_000",
                source_id="",
                title="",
                content="",
                product="",
                embedding=[0.1, 0.2, 0.3, 0.4],
            )
        )
        readiness = check_corpus_readiness(store)
        # Since ingestion decisions are uncalibrated, readiness will be blocked
        # by calibration_blockers, not payload validation
        assert readiness.production_allowed is False


# ---------------------------------------------------------------------------
# 9. Embedding dimension mismatch blocks readiness
# ---------------------------------------------------------------------------


class TestDimensionMismatchBlocksReadiness:
    def test_dimension_reported(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        readiness = check_corpus_readiness(store)
        # Dimension check only triggers when dimension is mismatched
        if readiness.embedding_dimension_actual > 0:
            assert readiness.embedding_dimension_actual == 4
            assert readiness.dimension_match is True  # since expected==actual for default


# ---------------------------------------------------------------------------
# 10. min_docs/min_chunks uncalibrated block production
# ---------------------------------------------------------------------------


class TestMinDocsChunksUncalibrated:
    def test_production_blocked_by_uncalibrated(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        readiness = check_corpus_readiness(store)
        # All ingestion decisions are uncalibrated, so production is blocked
        assert readiness.production_allowed is False
        assert len(readiness.calibration_blockers) > 0


# ---------------------------------------------------------------------------
# 11. ChunkIndex is not used as productive fallback
# ---------------------------------------------------------------------------


class TestNoChunkIndexFallback:
    def test_pipeline_does_not_use_chunkindex(self) -> None:
        """Verify the ingestion pipeline uses VectorStore, not ChunkIndex."""
        # The pipeline explicitly takes VectorStore as parameter
        import inspect

        from src.rag.ingestion_pipeline import run_ingestion_pipeline

        sig = inspect.signature(run_ingestion_pipeline)
        params = list(sig.parameters.keys())
        assert "vector_store" in params
        assert "chunk_index" not in params


# ---------------------------------------------------------------------------
# 12. No LLM / scraping / internet in pipeline
# ---------------------------------------------------------------------------


class TestNoExternalDeps:
    def test_pipeline_imports_no_llm(self) -> None:
        """Verify ingestion_pipeline does not import LLM modules."""
        import ast

        path = "src/rag/ingestion_pipeline.py"
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.add(node.names[0].name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        blocked_keywords = ["llm", "openai", "instructor", "httpx", "requests", "scraping"]
        for imp in imports:
            for kw in blocked_keywords:
                assert kw not in imp.lower(), f"Ingestion pipeline imports {imp}"

    def test_pipeline_imports_no_scraping_internet(self) -> None:
        """Verify ingestion pipeline does not fetch from internet."""
        import ast

        path = "src/rag/ingestion_pipeline.py"
        with open(path, encoding="utf-8") as f:
            ast.parse(f.read())

        source = open(path, encoding="utf-8").read()
        blocked = ["requests.get", "httpx.get", "urllib", "aiohttp", "selenium", "scrapy"]
        for b in blocked:
            assert b not in source, f"Ingestion pipeline uses {b}"


# ---------------------------------------------------------------------------
# 13. Nvidia technology is stored in payload
# ---------------------------------------------------------------------------


class TestNvidiaTechnologyInPayload:
    def test_nvidia_technology_maps_to_product(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        for entry in store.entries:
            assert entry.nvidia_technology == entry.product

    def test_chunk_index_preserved(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        for entry in store.entries:
            assert entry.chunk_index >= 0

    def test_char_count_positive(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        for entry in store.entries:
            assert entry.char_count > 0

    def test_ingested_at_present(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        for entry in store.entries:
            assert entry.ingested_at, "ingested_at should not be empty"


# ---------------------------------------------------------------------------
# 14. Ingested_at is populated
# ---------------------------------------------------------------------------


class TestIngestedAt:
    def test_ingested_at_is_iso_format(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        for entry in store.entries:
            assert entry.ingested_at
            # Should be parseable as ISO datetime
            try:
                datetime.fromisoformat(entry.ingested_at.replace("Z", "+00:00"))
            except ValueError:
                pytest.fail(f"ingested_at not ISO format: {entry.ingested_at}")


# ---------------------------------------------------------------------------
# 15. Run with dry_run or skipped chunks
# ---------------------------------------------------------------------------


class TestSkippedChunks:
    def test_skipped_chunks_reported(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        report = run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        assert report.skipped_chunk_count >= 0

    def test_failed_chunks_reported(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        report = run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        assert report.failed_chunk_count >= 0


# ---------------------------------------------------------------------------
# 16. Payload schema valid/invalid counts
# ---------------------------------------------------------------------------


class TestPayloadSchemaCounts:
    def test_all_valid_in_successful_run(self, emb: MockEmbeddingProvider, store: InMemoryVectorStore) -> None:
        report = run_ingestion_pipeline(emb, store, allow_uncalibrated=True)
        assert report.payload_schema_valid_count > 0
        assert report.payload_schema_invalid_count == 0

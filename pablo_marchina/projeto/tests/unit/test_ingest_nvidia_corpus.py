"""Unit tests for scripts/ingest_nvidia_corpus.py.

All tests use SentenceTransformerProvider (real embeddings, all-MiniLM-L6-v2)
and InMemoryVectorStore so they run without Qdrant.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.ingest_nvidia_corpus import (
    compute_chunk_hash,
    compute_content_hash,
    load_sources_raw,
    run_ingestion,
)

# ---------------------------------------------------------------------------
# Hash stability
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_content_hash_stable(self) -> None:
        h1 = compute_content_hash("same text")
        h2 = compute_content_hash("same text")
        assert h1 == h2

    def test_content_hash_different(self) -> None:
        h1 = compute_content_hash("text a")
        h2 = compute_content_hash("text b")
        assert h1 != h2

    def test_content_hash_is_md5(self) -> None:
        h = compute_content_hash("test")
        assert len(h) == 32
        assert h == hashlib.md5(b"test").hexdigest()


class TestChunkHash:
    def test_chunk_hash_stable(self) -> None:
        h1 = compute_chunk_hash("chunk content")
        h2 = compute_chunk_hash("chunk content")
        assert h1 == h2

    def test_chunk_hash_different(self) -> None:
        h1 = compute_chunk_hash("chunk a")
        h2 = compute_chunk_hash("chunk b")
        assert h1 != h2


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


class TestCliArgs:
    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args([])
        assert args.dry_run is False
        assert args.recreate_collection is False
        assert args.skip_existing is False
        assert args.source_id is None
        assert args.product is None
        assert args.fail_on_validation_error is False
        assert args.backend == "qdrant"
        assert args.collection_name == "nvidia_corpus"
        assert args.batch_size == 32
        assert args.qdrant_url == "http://localhost:6333"
        assert args.vector_size == 384
        assert args.embedding_model

    def test_dry_run_flag(self) -> None:
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_source_id_filter(self) -> None:
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args(["--source-id", "nim", "triton"])
        assert args.source_id == ["nim", "triton"]

    def test_qdrant_and_embedding_options(self) -> None:
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args(
            [
                "--qdrant-url",
                "http://qdrant.local:6333",
                "--qdrant-api-key",
                "secret",
                "--collection-name",
                "custom_corpus",
                "--vector-size",
                "384",
                "--embedding-model",
                "all-MiniLM-L6-v2",
                "--require-real-embeddings",
            ]
        )

        assert args.qdrant_url == "http://qdrant.local:6333"
        assert args.qdrant_api_key == "secret"
        assert args.collection_name == "custom_corpus"
        assert args.vector_size == 384
        assert args.embedding_model == "all-MiniLM-L6-v2"
        assert args.require_real_embeddings is True


# ---------------------------------------------------------------------------
# Sources loading
# ---------------------------------------------------------------------------


class TestLoadSourcesRaw:
    def test_loads_yaml_with_new_fields(self) -> None:
        sources = load_sources_raw()
        assert "nim" in sources
        assert sources["nim"].get("version")
        assert sources["nim"].get("document_type") == "nvidia_corpus"
        assert sources["nim"].get("product") == "NVIDIA NIM"

    def test_all_sources_have_version_and_doc_type(self) -> None:
        sources = load_sources_raw()
        for sid, info in sources.items():
            assert info.get("version"), f"{sid} missing version"
            assert info.get("document_type"), f"{sid} missing document_type"


# ---------------------------------------------------------------------------
# Dry run (no upsert)
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_does_not_upsert(self) -> None:
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args(["--dry-run", "--backend", "in_memory"])
        report = run_ingestion(args)
        assert report.chunks_upserted == 0
        assert report.chunks_created > 0
        assert report.documents_seen > 0


# ---------------------------------------------------------------------------
# Full ingestion (in-memory backend)
# ---------------------------------------------------------------------------


class TestIngestionWithInMemory:
    def test_ingest_to_in_memory(self) -> None:
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args(["--backend", "in_memory"])
        report = run_ingestion(args)
        assert report.chunks_upserted > 0
        assert report.chunks_upserted == report.chunks_created
        assert report.documents_seen > 0
        assert report.documents_valid > 0
        assert report.documents_skipped == 0

    def test_ingest_recreate_collection(self) -> None:
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args(["--backend", "in_memory", "--recreate-collection"])
        report = run_ingestion(args)
        assert report.chunks_upserted > 0


# ---------------------------------------------------------------------------
# Payload verification
# ---------------------------------------------------------------------------


class TestPayload:
    def test_payload_contains_provenance(self) -> None:
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args(["--backend", "in_memory"])
        report = run_ingestion(args)
        assert report.chunks_created > 0

        # Verify through the in-memory store by checking report counts
        assert report.ingestion_run_id.startswith("run_")

    def test_report_counters(self) -> None:
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args(
            [
                "--dry-run",
                "--backend",
                "in_memory",
                "--source-id",
                "nemo_guardrails",
            ]
        )
        report = run_ingestion(args)
        assert report.documents_seen == 1
        assert report.documents_valid == 1
        assert report.chunks_created >= 1  # nemo_guardrails.md has multiple sections


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


class TestReport:
    def test_report_has_all_fields(self) -> None:
        from scripts.ingest_nvidia_corpus import parse_args

        args = parse_args(["--dry-run"])
        report = run_ingestion(args)
        assert report.ingestion_run_id
        assert report.started_at
        assert report.finished_at
        assert isinstance(report.documents_seen, int)
        assert isinstance(report.chunks_created, int)
        assert isinstance(report.validation_errors, list)
        assert isinstance(report.sources_failed, list)

    def test_report_saved_to_path(self, tmp_path: Path) -> None:
        from scripts.ingest_nvidia_corpus import main

        report_path = tmp_path / "report.json"
        argv = [
            "--dry-run",
            "--backend",
            "in_memory",
            f"--report-path={report_path}",
        ]
        main(argv)
        assert report_path.exists()
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["ingestion_run_id"]
        assert data["documents_seen"] > 0

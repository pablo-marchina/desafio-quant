from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.services.product.health_executor import _validate_ingestion_manifest


def _write_corpus(tmp_path: Path, *, finished_at: datetime, content: str = "governed corpus content") -> Path:
    corpus_dir = tmp_path / "nvidia_corpus"
    corpus_dir.mkdir()
    document = corpus_dir / "nim.md"
    document.write_text(content, encoding="utf-8")
    (corpus_dir / "sources.yaml").write_text(
        "sources:\n  nim:\n    is_active: true\n",
        encoding="utf-8",
    )
    source_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
    (corpus_dir / ".ingestion_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ingestion_run_id": "run_test",
                "finished_at": finished_at.isoformat(),
                "collection_name": "nvidia_corpus_test",
                "backend": "qdrant",
                "documents_valid": 1,
                "chunks_created": 2,
                "chunks_upserted": 2,
                "source_hashes": {"nim": source_hash},
            }
        ),
        encoding="utf-8",
    )
    return corpus_dir


def test_recent_hash_matched_manifest_is_valid(tmp_path: Path) -> None:
    corpus_dir = _write_corpus(tmp_path, finished_at=datetime.now(UTC))
    with patch.dict(
        "os.environ",
        {"QDRANT_COLLECTION": "nvidia_corpus_test", "RAG_INDEX_MAX_AGE_HOURS": "24"},
    ):
        valid, detail = _validate_ingestion_manifest(corpus_dir)

    assert valid is True
    assert "hash-matched Qdrant index" in detail


def test_ungoverned_markdown_fixture_does_not_pollute_source_set(tmp_path: Path) -> None:
    corpus_dir = _write_corpus(tmp_path, finished_at=datetime.now(UTC))
    (corpus_dir / "temporary_test_fixture.md").write_text("not an active governed source", encoding="utf-8")
    with patch.dict("os.environ", {"QDRANT_COLLECTION": "nvidia_corpus_test"}):
        valid, detail = _validate_ingestion_manifest(corpus_dir)

    assert valid is True
    assert "1 document(s)" in detail


def test_manifest_fails_closed_when_corpus_changes_after_ingestion(tmp_path: Path) -> None:
    corpus_dir = _write_corpus(tmp_path, finished_at=datetime.now(UTC))
    (corpus_dir / "nim.md").write_text("changed after ingestion", encoding="utf-8")
    with patch.dict("os.environ", {"QDRANT_COLLECTION": "nvidia_corpus_test"}):
        valid, detail = _validate_ingestion_manifest(corpus_dir)

    assert valid is False
    assert "changed after ingestion" in detail


def test_manifest_fails_when_index_is_too_old(tmp_path: Path) -> None:
    corpus_dir = _write_corpus(tmp_path, finished_at=datetime.now(UTC) - timedelta(hours=25))
    with patch.dict(
        "os.environ",
        {"QDRANT_COLLECTION": "nvidia_corpus_test", "RAG_INDEX_MAX_AGE_HOURS": "24"},
    ):
        valid, detail = _validate_ingestion_manifest(corpus_dir)

    assert valid is False
    assert "RAG_INDEX_MAX_AGE_HOURS=24" in detail


def test_manifest_fails_when_active_source_document_is_missing(tmp_path: Path) -> None:
    corpus_dir = _write_corpus(tmp_path, finished_at=datetime.now(UTC))
    (corpus_dir / "sources.yaml").write_text(
        "sources:\n  nim:\n    is_active: true\n  tensorrt_llm:\n    is_active: true\n",
        encoding="utf-8",
    )
    with patch.dict("os.environ", {"QDRANT_COLLECTION": "nvidia_corpus_test"}):
        valid, detail = _validate_ingestion_manifest(corpus_dir)

    assert valid is False
    assert "source set mismatch" in detail
    assert "tensorrt_llm" in detail

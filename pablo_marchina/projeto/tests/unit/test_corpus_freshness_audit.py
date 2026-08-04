"""Tests for NVIDIA corpus freshness/versioning audit."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from scripts.audit_nvidia_corpus_freshness import (
    format_report,
    main,
    run_audit,
)
from scripts.sync_nvidia_sources import update_sources_yaml
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RagChunk, RetrievalQuery
from src.rag.vector_store import InMemoryVectorStore, VectorEntry


def test_detects_stale_source(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, _source_yaml(last_checked_at="2026-05-01T00:00:00Z"))

    report = run_audit(manifest, now=_now())

    assert report.stale_sources == 1
    assert report.details["stale_sources"][0]["source_id"] == "nim"


def test_detects_expired_source(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, _source_yaml(valid_until="2026-06-01T00:00:00Z"))

    report = run_audit(manifest, now=_now())

    assert report.expired_sources == 1
    assert report.details["expired_sources"][0]["source_id"] == "nim"


def test_detects_missing_metadata(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        """
sources:
  nim:
    title: NVIDIA NIM
    product: NVIDIA NIM
    gap_types: [high_latency]
    version: "1.0"
    document_type: nvidia_corpus
    is_active: true
""",
    )

    report = run_audit(manifest, now=_now())

    assert report.missing_metadata
    assert "last_checked_at" in report.missing_metadata[0]["missing_fields"]
    assert "content_hash" in report.missing_metadata[0]["missing_fields"]


def test_detects_duplicate_active_versions(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        """
sources:
  nim:
    title: NVIDIA NIM
    product: NVIDIA NIM
    gap_types: [high_latency]
    document_type: nvidia_corpus
    versions:
      - version: "1.0"
        content_hash: aaa
        collected_at: "2026-06-01T00:00:00Z"
        last_checked_at: "2026-06-01T00:00:00Z"
        valid_from: "2026-06-01T00:00:00Z"
        freshness_policy: weekly
        stale_after_days: 7
        is_active: true
      - version: "1.1"
        content_hash: bbb
        collected_at: "2026-06-10T00:00:00Z"
        last_checked_at: "2026-06-10T00:00:00Z"
        valid_from: "2026-06-10T00:00:00Z"
        freshness_policy: weekly
        stale_after_days: 7
        is_active: true
""",
    )

    report = run_audit(manifest, now=_now())

    assert report.duplicate_active_versions == [{"source_id": "nim", "active_versions": ["1.0", "1.1"]}]


def test_detects_deprecated_and_superseded_sources(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path,
        _source_yaml(
            is_active=False,
            deprecated_at="2026-06-10T00:00:00Z",
            superseded_by="1.1",
            deprecation_reason="superseded_by_new_content_hash",
        ),
    )

    report = run_audit(manifest, now=_now())

    assert report.deprecated_sources == 1
    assert report.superseded_sources == 1


def test_report_contains_expected_counters(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, _source_yaml())

    report = run_audit(manifest, now=_now())
    data = json.loads(format_report(report, "json"))

    assert data["audit_run_id"].startswith("audit_")
    assert data["sources_seen"] == 1
    assert data["active_sources"] == 1
    assert data["stale_sources"] == 0
    assert data["expired_sources"] == 0


def test_fail_on_stale_exits_with_error(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, _source_yaml(last_checked_at="2026-05-01T00:00:00Z"))

    with pytest.raises(SystemExit) as exc:
        main(["--sources-path", str(manifest), "--fail-on-stale"])

    assert exc.value.code == 1


def test_fail_on_expired_exits_with_error(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path, _source_yaml(valid_until="2026-06-01T00:00:00Z"))

    with pytest.raises(SystemExit) as exc:
        main(["--sources-path", str(manifest), "--fail-on-expired"])

    assert exc.value.code == 1


def test_new_content_hash_creates_new_active_version(tmp_path: Path) -> None:
    sources_path = _write_manifest(tmp_path, _source_yaml(content_hash="oldhash"))
    entry = {
        "source_id": "nim",
        "title": "NVIDIA NIM",
        "url": "https://docs.nvidia.com/nim/latest/",
        "product": "NVIDIA NIM",
        "gap_types": ["high_latency"],
        "version": "1.0",
        "document_type": "nvidia_corpus",
        "freshness_policy": "weekly",
        "stale_after_days": 7,
    }

    update_sources_yaml(
        entry,
        sources_path=sources_path,
        content_hash="newhash",
        checked_at="2026-06-10T00:00:00Z",
    )

    updated = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    versions = updated["sources"]["nim"]["versions"]
    assert versions[0]["is_active"] is False
    assert versions[0]["superseded_by"] == "1.1"
    assert versions[1]["version"] == "1.1"
    assert versions[1]["previous_content_hash"] == "oldhash"
    assert updated["sources"]["nim"]["content_hash"] == "newhash"


def test_retrieval_ignores_deprecated_and_expired_by_default() -> None:
    chunks = [
        _chunk("active", is_active=True),
        _chunk("deprecated", is_active=False, deprecated_at="2026-06-01T00:00:00Z"),
        _chunk("expired", is_active=True, valid_until="2026-06-01T00:00:00Z"),
    ]
    index = ChunkIndex(chunks)

    contexts = index.retrieve(RetrievalQuery(gap_type="high_latency"), top_k=5)

    assert [ctx.source_id for ctx in contexts] == ["active"]


def test_vector_store_filters_inactive_entries_by_default() -> None:
    store = InMemoryVectorStore()
    store.add_entries(
        [
            _entry("active", is_active=True),
            _entry("deprecated", is_active=False, deprecated_at="2026-06-01T00:00:00Z"),
        ]
    )

    results = store.search([1.0, 0.0], top_k=5)

    assert [entry.source_id for entry in results] == ["active"]


def _write_manifest(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _source_yaml(
    *,
    content_hash: str = "abc123",
    last_checked_at: str = "2026-06-10T00:00:00Z",
    valid_until: str | None = None,
    is_active: bool = True,
    deprecated_at: str | None = None,
    superseded_by: str | None = None,
    deprecation_reason: str | None = None,
) -> str:
    return yaml.safe_dump(
        {
            "sources": {
                "nim": {
                    "title": "NVIDIA NIM",
                    "url": "https://docs.nvidia.com/nim/latest/",
                    "product": "NVIDIA NIM",
                    "gap_types": ["high_latency"],
                    "version": "1.0",
                    "document_type": "nvidia_corpus",
                    "content_hash": content_hash,
                    "previous_content_hash": None,
                    "collected_at": "2026-06-10T00:00:00Z",
                    "last_checked_at": last_checked_at,
                    "valid_from": "2026-06-10T00:00:00Z",
                    "valid_until": valid_until,
                    "freshness_policy": "weekly",
                    "stale_after_days": 7,
                    "is_active": is_active,
                    "deprecated_at": deprecated_at,
                    "superseded_by": superseded_by,
                    "deprecation_reason": deprecation_reason,
                    "versions": [
                        {
                            "version": "1.0",
                            "content_hash": content_hash,
                            "previous_content_hash": None,
                            "collected_at": "2026-06-10T00:00:00Z",
                            "last_checked_at": last_checked_at,
                            "valid_from": "2026-06-10T00:00:00Z",
                            "valid_until": valid_until,
                            "freshness_policy": "weekly",
                            "stale_after_days": 7,
                            "is_active": is_active,
                            "deprecated_at": deprecated_at,
                            "superseded_by": superseded_by,
                            "deprecation_reason": deprecation_reason,
                        }
                    ],
                }
            }
        },
        sort_keys=False,
    )


def _chunk(
    source_id: str,
    *,
    is_active: bool,
    valid_until: str | None = None,
    deprecated_at: str | None = None,
) -> RagChunk:
    return RagChunk(
        chunk_id=f"{source_id}_000",
        source_id=source_id,
        title=source_id,
        content="NVIDIA latency optimization",
        product="NVIDIA NIM",
        gap_types=["high_latency"],
        is_active=is_active,
        valid_until=valid_until,
        deprecated_at=deprecated_at,
    )


def _entry(
    source_id: str,
    *,
    is_active: bool,
    deprecated_at: str | None = None,
) -> VectorEntry:
    return VectorEntry(
        chunk_id=f"{source_id}_000",
        source_id=source_id,
        title=source_id,
        content="NVIDIA latency optimization",
        product="NVIDIA NIM",
        gap_types=["high_latency"],
        embedding=[1.0, 0.0],
        is_active=is_active,
        deprecated_at=deprecated_at,
    )


def _now() -> datetime:
    return datetime(2026, 6, 10, tzinfo=UTC)

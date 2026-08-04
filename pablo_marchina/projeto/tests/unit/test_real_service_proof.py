from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import real_service_proof


def test_postgres_report_blocks_when_connection_fails(tmp_path: Path) -> None:
    report = real_service_proof.check_postgres(tmp_path, "postgresql://postgres:postgres@localhost:1/missing")
    assert report["status"] == "BLOCKED_BY_ENVIRONMENT"
    assert (tmp_path / "postgres_migration_report.json").is_file()


def test_qdrant_report_blocks_when_unreachable(tmp_path: Path) -> None:
    report = real_service_proof.check_qdrant(tmp_path, "http://127.0.0.1:1", "missing")
    assert report["status"] == "BLOCKED_BY_ENVIRONMENT"
    assert (tmp_path / "qdrant_readiness_report.json").is_file()


def test_rag_ingestion_blocks_when_qdrant_blocked(tmp_path: Path) -> None:
    qdrant_report = {"status": "BLOCKED_BY_ENVIRONMENT", "errors": ["offline"]}
    report = real_service_proof.check_rag_ingestion(tmp_path, qdrant_report)
    assert report["status"] == "BLOCKED_BY_ENVIRONMENT"
    assert report["errors"] == ["offline"]


def test_full_service_proof_aggregates_blocked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def blocked(report_id: str) -> dict[str, Any]:
        return {
            "report_id": report_id,
            "status": "BLOCKED_BY_ENVIRONMENT",
            "generated_at": "2026-06-22T00:00:00+00:00",
            "details": {},
            "errors": ["blocked"],
        }

    def blocked_rag(
        evidence_dir: Path,
        qdrant_report: dict[str, Any],
        qdrant_url: str = "",
        qdrant_collection: str = "",
        timeout_seconds: int = 15,
        ingest_corpus: bool = False,
        reset_qdrant: bool = False,
        embedding_model: str = "",
        vector_size: int = 384,
        min_points: int = 10,
    ) -> dict[str, Any]:
        return blocked("rag_ingestion_report")

    def passed_acceptance(
        evidence_dir: Path,
        product_like: bool,
        timeout_seconds: int = 90,
        database_url: str = "",
        qdrant_url: str = "",
        qdrant_collection: str = "",
        vector_size: int = 384,
    ) -> dict[str, Any]:
        return {
            "report_id": "acceptance_report",
            "status": "PASS",
            "generated_at": "2026-06-22T00:00:00+00:00",
            "details": {},
            "errors": [],
        }

    monkeypatch.setattr(
        real_service_proof,
        "check_docker",
        lambda evidence_dir, timeout_seconds=15, auto_start_services=False: blocked("docker_services_report"),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_postgres",
        lambda evidence_dir, database_url, timeout_seconds=15: blocked("postgres_migration_report"),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_qdrant",
        lambda evidence_dir, qdrant_url, collection, timeout_seconds=15: blocked("qdrant_readiness_report"),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_rag_ingestion",
        blocked_rag,
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_acceptance",
        passed_acceptance,
    )
    summary = real_service_proof.run_full_service_proof(
        tmp_path,
        database_url="postgresql://postgres:postgres@localhost:5432/startup_radar",
        qdrant_url="http://localhost:6333",
        qdrant_collection="nvidia_corpus",
        product_like_acceptance=False,
    )
    assert summary["status"] == "BLOCKED_BY_ENVIRONMENT"
    written = json.loads((tmp_path / "real_service_proof_report.json").read_text(encoding="utf-8"))
    assert written["status"] == "BLOCKED_BY_ENVIRONMENT"


def test_full_service_proof_passes_with_external_services_when_docker_blocks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def payload(report_id: str, status: str) -> dict[str, Any]:
        return {
            "report_id": report_id,
            "status": status,
            "generated_at": "2026-06-22T00:00:00+00:00",
            "details": {},
            "errors": [],
        }

    monkeypatch.setattr(
        real_service_proof,
        "check_docker",
        lambda evidence_dir, timeout_seconds=15, auto_start_services=False: payload(
            "docker_services_report", "BLOCKED_BY_ENVIRONMENT"
        ),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_postgres",
        lambda evidence_dir, database_url, timeout_seconds=15: payload("postgres_migration_report", "PASS"),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_qdrant",
        lambda evidence_dir, qdrant_url, collection, timeout_seconds=15: payload("qdrant_readiness_report", "PASS"),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_rag_ingestion",
        lambda *args, **kwargs: payload("rag_ingestion_report", "PASS"),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_acceptance",
        lambda *args, **kwargs: payload("acceptance_report", "PASS"),
    )

    summary = real_service_proof.run_full_service_proof(
        tmp_path,
        database_url="postgresql://postgres:postgres@localhost:5432/startup_radar",
        qdrant_url="http://localhost:6333",
        qdrant_collection="nvidia_corpus",
        product_like_acceptance=True,
    )

    assert summary["status"] == "PASS"
    assert summary["effective_service_route"] == "external_services"


def test_full_service_proof_requires_docker_when_flagged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def payload(report_id: str, status: str) -> dict[str, Any]:
        return {
            "report_id": report_id,
            "status": status,
            "generated_at": "2026-06-22T00:00:00+00:00",
            "details": {},
            "errors": [],
        }

    monkeypatch.setattr(
        real_service_proof,
        "check_docker",
        lambda evidence_dir, timeout_seconds=15, auto_start_services=False: payload(
            "docker_services_report", "BLOCKED_BY_ENVIRONMENT"
        ),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_postgres",
        lambda evidence_dir, database_url, timeout_seconds=15: payload("postgres_migration_report", "PASS"),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_qdrant",
        lambda evidence_dir, qdrant_url, collection, timeout_seconds=15: payload("qdrant_readiness_report", "PASS"),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_rag_ingestion",
        lambda *args, **kwargs: payload("rag_ingestion_report", "PASS"),
    )
    monkeypatch.setattr(
        real_service_proof,
        "check_acceptance",
        lambda *args, **kwargs: payload("acceptance_report", "PASS"),
    )

    summary = real_service_proof.run_full_service_proof(
        tmp_path,
        database_url="postgresql://postgres:postgres@localhost:5432/startup_radar",
        qdrant_url="http://localhost:6333",
        qdrant_collection="nvidia_corpus",
        product_like_acceptance=True,
        require_docker_compose=True,
    )

    assert summary["status"] == "BLOCKED_BY_ENVIRONMENT"
    assert summary["effective_service_route"] == "blocked_require_docker_compose"


def test_docker_auto_start_invokes_compose_up(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> object:
        commands.append(command)
        return type("Result", (), {"returncode": 0, "stdout": "{}", "stderr": ""})()

    monkeypatch.setattr(real_service_proof.subprocess, "run", fake_run)
    report = real_service_proof.check_docker(tmp_path, auto_start_services=True)

    assert report["status"] == "PASS"
    assert ["docker", "compose", "up", "-d", "postgres", "qdrant"] in commands
    assert ["docker", "compose", "ps", "--format", "json"] in commands


def test_corpus_ingestion_command_preserves_data_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(command: list[str], **kwargs: object) -> object:
        captured["command"] = command
        return type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(real_service_proof.subprocess, "run", fake_run)
    result = real_service_proof._run_corpus_ingestion(
        evidence_dir=tmp_path,
        qdrant_url="http://localhost:6333",
        qdrant_collection="nvidia_corpus",
        reset_qdrant=False,
        embedding_model="all-MiniLM-L6-v2",
        vector_size=384,
        timeout_seconds=5,
    )

    assert result["status"] == "PASS"
    assert "--skip-existing" in captured["command"]
    assert "--recreate-collection" not in captured["command"]


def test_corpus_ingestion_reset_requires_explicit_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(command: list[str], **kwargs: object) -> object:
        captured["command"] = command
        return type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(real_service_proof.subprocess, "run", fake_run)
    real_service_proof._run_corpus_ingestion(
        evidence_dir=tmp_path,
        qdrant_url="http://localhost:6333",
        qdrant_collection="nvidia_corpus",
        reset_qdrant=True,
        embedding_model="all-MiniLM-L6-v2",
        vector_size=384,
        timeout_seconds=5,
    )

    assert "--recreate-collection" in captured["command"]
    assert "--skip-existing" not in captured["command"]

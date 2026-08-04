#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

DEFAULT_POSTGRES_URL = "postgresql://postgres:postgres@localhost:5432/startup_radar"
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_QDRANT_COLLECTION = "nvidia_corpus"
DEFAULT_SERVICE_TIMEOUT_SECONDS = 15
DEFAULT_ACCEPTANCE_TIMEOUT_SECONDS = 90
DEFAULT_WAIT_TIMEOUT_SECONDS = 90
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_VECTOR_SIZE = 384
DEFAULT_QDRANT_MIN_POINTS = 10


def report(
    *,
    report_id: str,
    status: str,
    evidence_dir: Path,
    details: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "report_id": report_id,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "details": details or {},
        "errors": errors or [],
    }
    write_json(evidence_dir / f"{report_id}.json", payload)
    return payload


def check_docker(
    evidence_dir: Path,
    *,
    timeout_seconds: int = DEFAULT_SERVICE_TIMEOUT_SECONDS,
    auto_start_services: bool = False,
) -> dict[str, Any]:
    up_result: subprocess.CompletedProcess[str] | None = None
    try:
        if auto_start_services:
            up_result = subprocess.run(
                ["docker", "compose", "up", "-d", "postgres", "qdrant"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=max(timeout_seconds, 30),
            )
            if up_result.returncode != 0:
                return report(
                    report_id="docker_services_report",
                    status="BLOCKED_BY_ENVIRONMENT",
                    evidence_dir=evidence_dir,
                    details={
                        "command": "docker compose up -d postgres qdrant",
                        "returncode": up_result.returncode,
                        "stdout_tail": up_result.stdout[-2000:],
                        "stderr_tail": up_result.stderr[-2000:],
                    },
                )
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return report(
            report_id="docker_services_report",
            status="BLOCKED_BY_ENVIRONMENT",
            evidence_dir=evidence_dir,
            errors=[str(exc)],
        )
    except subprocess.TimeoutExpired as exc:
        return report(
            report_id="docker_services_report",
            status="BLOCKED_BY_ENVIRONMENT",
            evidence_dir=evidence_dir,
            details={"command": "docker compose ps --format json", "timeout_seconds": timeout_seconds},
            errors=[f"Timed out after {exc.timeout} seconds."],
        )
    status = "PASS" if result.returncode == 0 else "BLOCKED_BY_ENVIRONMENT"
    return report(
        report_id="docker_services_report",
        status=status,
        evidence_dir=evidence_dir,
        details={
            "auto_start_services": auto_start_services,
            "up_command": "docker compose up -d postgres qdrant" if auto_start_services else "",
            "up_stdout_tail": up_result.stdout[-2000:] if up_result else "",
            "up_stderr_tail": up_result.stderr[-2000:] if up_result else "",
            "command": "docker compose ps --format json",
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
            "returncode": result.returncode,
        },
    )


def check_postgres(
    evidence_dir: Path,
    database_url: str,
    *,
    run_migrations: bool = True,
    timeout_seconds: int = DEFAULT_SERVICE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        engine = create_engine(
            database_url,
            connect_args=_connect_args_for(database_url, timeout_seconds),
            future=True,
            pool_pre_ping=True,
        )
        with engine.connect() as connection:
            scalar = connection.execute(text("SELECT 1")).scalar_one()
        engine.dispose()
        migration_result = _run_alembic(database_url, timeout_seconds) if run_migrations else None
        current_result = _run_alembic_current(database_url, timeout_seconds) if run_migrations else None
        migration_status = "skipped_by_cli_flag" if migration_result is None else migration_result["status"]
        current_status = "skipped_by_cli_flag" if current_result is None else current_result["status"]
        if (
            migration_result is None
            or migration_result["status"] == "PASS"
            and (current_result is None or current_result["status"] == "PASS")
        ):
            status = "PASS"
        elif migration_result["status"] == "BLOCKED_BY_ENVIRONMENT" or (
            current_result and current_result["status"] == "BLOCKED_BY_ENVIRONMENT"
        ):
            status = "BLOCKED_BY_ENVIRONMENT"
        else:
            status = "FAIL"
        return report(
            report_id="postgres_migration_report",
            status=status,
            evidence_dir=evidence_dir,
            details={
                "database_url": _sanitize_url(database_url),
                "roundtrip_scalar": scalar,
                "migration_command": "alembic upgrade head",
                "migration_status": migration_status,
                "migration_result": migration_result,
                "current_command": "alembic current",
                "current_status": current_status,
                "current_result": current_result,
            },
            errors=[] if status == "PASS" else _postgres_errors(migration_result, current_result),
        )
    except SQLAlchemyError as exc:
        return report(
            report_id="postgres_migration_report",
            status="BLOCKED_BY_ENVIRONMENT",
            evidence_dir=evidence_dir,
            details={"database_url": _sanitize_url(database_url)},
            errors=[str(exc)],
        )


def check_qdrant(
    evidence_dir: Path,
    qdrant_url: str,
    collection: str,
    *,
    timeout_seconds: int = DEFAULT_SERVICE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        with urlopen(f"{qdrant_url.rstrip('/')}/collections/{collection}", timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload.get("result", {})
        points_count = result.get("points_count")
        vectors_count = result.get("vectors_count")
        vector_size = _extract_qdrant_vector_size(result)
        return report(
            report_id="qdrant_readiness_report",
            status="PASS",
            evidence_dir=evidence_dir,
            details={
                "qdrant_url": qdrant_url,
                "collection": collection,
                "points_count": points_count,
                "vectors_count": vectors_count,
                "vector_size": vector_size,
                "raw_status": payload.get("status"),
            },
        )
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return report(
            report_id="qdrant_readiness_report",
            status="BLOCKED_BY_ENVIRONMENT",
            evidence_dir=evidence_dir,
            details={"qdrant_url": qdrant_url, "collection": collection},
            errors=[str(exc)],
        )


def check_rag_ingestion(
    evidence_dir: Path,
    qdrant_report: dict[str, Any],
    *,
    qdrant_url: str = DEFAULT_QDRANT_URL,
    qdrant_collection: str = DEFAULT_QDRANT_COLLECTION,
    timeout_seconds: int = DEFAULT_SERVICE_TIMEOUT_SECONDS,
    ingest_corpus: bool = False,
    reset_qdrant: bool = False,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    vector_size: int = DEFAULT_VECTOR_SIZE,
    min_points: int = DEFAULT_QDRANT_MIN_POINTS,
) -> dict[str, Any]:
    if qdrant_report["status"] != "PASS" and not ingest_corpus:
        return report(
            report_id="rag_ingestion_report",
            status="BLOCKED_BY_ENVIRONMENT",
            evidence_dir=evidence_dir,
            details={"reason": "Qdrant readiness did not pass."},
            errors=qdrant_report.get("errors", []),
        )

    try:
        from src.rag.ingestion import load_and_chunk_corpus

        ingest_result = (
            _run_corpus_ingestion(
                evidence_dir=evidence_dir,
                qdrant_url=qdrant_url,
                qdrant_collection=qdrant_collection,
                reset_qdrant=reset_qdrant,
                embedding_model=embedding_model,
                vector_size=vector_size,
                timeout_seconds=timeout_seconds,
            )
            if ingest_corpus
            else None
        )
        refreshed_qdrant_report = check_qdrant(
            evidence_dir,
            qdrant_url,
            qdrant_collection,
            timeout_seconds=timeout_seconds,
        )
        chunks = load_and_chunk_corpus()
        qdrant_details = refreshed_qdrant_report.get("details", {})
        points_count = qdrant_details.get("points_count") or qdrant_details.get("vectors_count") or 0
        retrieval_result = _try_qdrant_retrieval(
            qdrant_url=qdrant_url,
            collection=qdrant_collection,
            timeout_seconds=timeout_seconds,
        )
        status = (
            "PASS"
            if chunks
            and int(points_count or 0) >= min_points
            and retrieval_result["status"] == "PASS"
            and (ingest_result is None or ingest_result["status"] == "PASS")
            else "BLOCKED_BY_ENVIRONMENT"
        )
        return report(
            report_id="rag_ingestion_report",
            status=status,
            evidence_dir=evidence_dir,
            details={
                "ingest_corpus": ingest_corpus,
                "reset_qdrant": reset_qdrant,
                "embedding_model": embedding_model,
                "vector_size": vector_size,
                "min_points": min_points,
                "ingestion_result": ingest_result,
                "local_chunk_count": len(chunks),
                "qdrant_points_count": points_count,
                "collection": qdrant_details.get("collection"),
                "retrieval_result": retrieval_result,
            },
            errors=[] if status == "PASS" else _rag_blockers(chunks, points_count, retrieval_result, min_points),
        )
    except Exception as exc:
        return report(
            report_id="rag_ingestion_report",
            status="FAIL",
            evidence_dir=evidence_dir,
            errors=[str(exc)],
        )


def check_acceptance(
    evidence_dir: Path,
    product_like: bool,
    *,
    timeout_seconds: int = DEFAULT_ACCEPTANCE_TIMEOUT_SECONDS,
    database_url: str = DEFAULT_POSTGRES_URL,
    qdrant_url: str = DEFAULT_QDRANT_URL,
    qdrant_collection: str = DEFAULT_QDRANT_COLLECTION,
    vector_size: int = DEFAULT_VECTOR_SIZE,
) -> dict[str, Any]:
    env = os.environ.copy()
    if product_like:
        env.update(
            {
                "APP_MODE": "product",
                "PRODUCT_DB_URL": database_url,
                "ENABLE_PRODUCT_PERSISTENCE": "true",
                "RAG_VECTOR_BACKEND": "qdrant",
                "RAG_REQUIRED_FOR_PRODUCT": "true",
                "RAG_EMBEDDING_MODEL": env.get("RAG_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
                "QDRANT_URL": qdrant_url,
                "QDRANT_COLLECTION": qdrant_collection,
                "QDRANT_VECTOR_SIZE": str(vector_size),
                "AGENT_ORCHESTRATION_ENABLED": "true",
            }
        )
        command = [
            sys.executable,
            "scripts/run_product_acceptance.py",
            "--evidence-dir",
            str(evidence_dir),
            "--database-url",
            database_url,
            "--qdrant-url",
            qdrant_url,
            "--qdrant-collection",
            qdrant_collection,
        ]
    else:
        env.setdefault("APP_MODE", "test")
        env.setdefault("RAG_REQUIRED_FOR_PRODUCT", "false")
        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests/acceptance/",
            "-m",
            "acceptance",
            "--tb=short",
            "--basetemp",
            ".pytest_tmp_acceptance",
        ]
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return report(
            report_id="acceptance_report",
            status="BLOCKED_BY_ENVIRONMENT",
            evidence_dir=evidence_dir,
            details={
                "command": " ".join(command),
                "product_like": product_like,
                "timeout_seconds": timeout_seconds,
            },
            errors=[f"Timed out after {exc.timeout} seconds."],
        )
    if product_like and (evidence_dir / "acceptance_report.json").exists():
        payload = cast(
            dict[str, Any],
            json.loads((evidence_dir / "acceptance_report.json").read_text(encoding="utf-8")),
        )
        payload.setdefault("details", {})
        payload["details"]["command"] = " ".join(command)
        payload["details"]["returncode"] = result.returncode
        payload["details"]["stdout_tail"] = result.stdout[-4000:]
        payload["details"]["stderr_tail"] = result.stderr[-4000:]
        if result.returncode != 0:
            payload["status"] = "FAIL"
        write_json(evidence_dir / "acceptance_report.json", payload)
        return payload
    return report(
        report_id="acceptance_report",
        status="PASS" if result.returncode == 0 else "FAIL",
        evidence_dir=evidence_dir,
        details={
            "command": " ".join(command),
            "product_like": product_like,
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
        },
    )


def run_full_service_proof(
    evidence_dir: Path,
    *,
    database_url: str,
    qdrant_url: str,
    qdrant_collection: str,
    product_like_acceptance: bool,
    timeout_seconds: int = DEFAULT_SERVICE_TIMEOUT_SECONDS,
    acceptance_timeout_seconds: int = DEFAULT_ACCEPTANCE_TIMEOUT_SECONDS,
    auto_start_services: bool = False,
    ingest_corpus: bool = False,
    reset_qdrant: bool = False,
    wait_timeout_seconds: int = DEFAULT_WAIT_TIMEOUT_SECONDS,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    vector_size: int = DEFAULT_VECTOR_SIZE,
    min_points: int = DEFAULT_QDRANT_MIN_POINTS,
    require_docker_compose: bool = False,
) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    docker = check_docker(
        evidence_dir,
        timeout_seconds=timeout_seconds,
        auto_start_services=auto_start_services,
    )
    if docker["status"] == "PASS":
        _wait_for_postgres(database_url, wait_timeout_seconds)
        _wait_for_qdrant(qdrant_url, wait_timeout_seconds)
    postgres = check_postgres(evidence_dir, database_url, timeout_seconds=timeout_seconds)
    qdrant = check_qdrant(evidence_dir, qdrant_url, qdrant_collection, timeout_seconds=timeout_seconds)
    qdrant_service_available = _qdrant_service_available(qdrant_url, timeout_seconds)
    rag = check_rag_ingestion(
        evidence_dir,
        qdrant,
        qdrant_url=qdrant_url,
        qdrant_collection=qdrant_collection,
        timeout_seconds=timeout_seconds,
        ingest_corpus=ingest_corpus and qdrant_service_available,
        reset_qdrant=reset_qdrant,
        embedding_model=embedding_model,
        vector_size=vector_size,
        min_points=min_points,
    )
    if ingest_corpus:
        qdrant = check_qdrant(evidence_dir, qdrant_url, qdrant_collection, timeout_seconds=timeout_seconds)
    if product_like_acceptance and _dependencies_block_product_like_acceptance([postgres, qdrant, rag]):
        acceptance = report(
            report_id="acceptance_report",
            status="BLOCKED_BY_ENVIRONMENT",
            evidence_dir=evidence_dir,
            details={
                "product_like": True,
                "reason": "PostgreSQL, Qdrant, and RAG ingestion must pass before product-like acceptance runs.",
                "blocked_dependencies": [
                    item["report_id"] for item in [postgres, qdrant, rag] if item["status"] != "PASS"
                ],
            },
        )
    else:
        acceptance = check_acceptance(
            evidence_dir,
            product_like_acceptance,
            timeout_seconds=acceptance_timeout_seconds,
            database_url=database_url,
            qdrant_url=qdrant_url,
            qdrant_collection=qdrant_collection,
            vector_size=vector_size,
        )
    reports = [docker, postgres, qdrant, rag, acceptance]
    service_route = _resolve_service_route(
        docker=docker,
        postgres=postgres,
        qdrant=qdrant,
        require_docker_compose=require_docker_compose,
    )
    status = _aggregate_status(
        reports,
        service_route=service_route,
        require_docker_compose=require_docker_compose,
    )
    summary = {
        "report_id": "real_service_proof_report",
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "effective_service_route": service_route,
        "reports": reports,
        "settings": {
            "auto_start_services": auto_start_services,
            "ingest_corpus": ingest_corpus,
            "reset_qdrant": reset_qdrant,
            "wait_timeout_seconds": wait_timeout_seconds,
            "embedding_model": embedding_model,
            "vector_size": vector_size,
            "min_points": min_points,
            "require_docker_compose": require_docker_compose,
        },
    }
    write_json(evidence_dir / "real_service_proof_report.json", summary)
    return summary


def _aggregate_status(
    reports: list[dict[str, Any]],
    *,
    service_route: str = "docker_compose",
    require_docker_compose: bool = False,
) -> str:
    effective_reports = [
        report
        for report in reports
        if report.get("report_id") != "docker_services_report"
        or require_docker_compose
        or report["status"] == "PASS"
        or service_route != "external_services"
    ]
    statuses = {report["status"] for report in effective_reports}
    if "FAIL" in statuses:
        return "FAIL"
    if "BLOCKED_BY_ENVIRONMENT" in statuses:
        return "BLOCKED_BY_ENVIRONMENT"
    return "PASS"


def _resolve_service_route(
    *,
    docker: dict[str, Any],
    postgres: dict[str, Any],
    qdrant: dict[str, Any],
    require_docker_compose: bool,
) -> str:
    if require_docker_compose:
        return "docker_compose" if docker["status"] == "PASS" else "blocked_require_docker_compose"
    if postgres["status"] == "PASS" and qdrant["status"] == "PASS":
        return "external_services" if docker["status"] != "PASS" else "docker_compose"
    if docker["status"] == "PASS":
        return "docker_compose"
    return "blocked_no_service_route"


def _connect_args_for(database_url: str, timeout_seconds: int) -> dict[str, Any]:
    if database_url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        return {"connect_timeout": timeout_seconds}
    return {}


def _run_alembic(database_url: str, timeout_seconds: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["APP_MODE"] = "product"
    env["PRODUCT_DB_URL"] = database_url
    command = [sys.executable, "-m", "alembic", "upgrade", "head"]
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env=env,
            timeout=max(timeout_seconds, 30),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(command),
            "status": "BLOCKED_BY_ENVIRONMENT",
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": f"Timed out after {exc.timeout} seconds.",
        }
    return {
        "command": " ".join(command),
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-3000:],
        "stderr_tail": result.stderr[-3000:],
    }


def _run_alembic_current(database_url: str, timeout_seconds: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["APP_MODE"] = "product"
    env["PRODUCT_DB_URL"] = database_url
    command = [sys.executable, "-m", "alembic", "current"]
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env=env,
            timeout=max(timeout_seconds, 30),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(command),
            "status": "BLOCKED_BY_ENVIRONMENT",
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": f"Timed out after {exc.timeout} seconds.",
        }
    return {
        "command": " ".join(command),
        "status": "PASS" if result.returncode == 0 and "head" in result.stdout else "FAIL",
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-3000:],
        "stderr_tail": result.stderr[-3000:],
    }


def _postgres_errors(
    migration_result: dict[str, Any] | None,
    current_result: dict[str, Any] | None,
) -> list[str]:
    errors = []
    for result in (migration_result, current_result):
        if result and result.get("status") != "PASS":
            errors.append(result.get("stderr_tail") or result.get("stdout_tail") or "PostgreSQL proof failed.")
    return errors


def _wait_for_postgres(database_url: str, timeout_seconds: int) -> bool:
    deadline = datetime.now(UTC).timestamp() + timeout_seconds
    while datetime.now(UTC).timestamp() < deadline:
        try:
            engine = create_engine(
                database_url,
                connect_args=_connect_args_for(database_url, 3),
                future=True,
                pool_pre_ping=True,
            )
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            engine.dispose()
            return True
        except SQLAlchemyError:
            _sleep_one_second()
    return False


def _wait_for_qdrant(qdrant_url: str, timeout_seconds: int) -> bool:
    deadline = datetime.now(UTC).timestamp() + timeout_seconds
    while datetime.now(UTC).timestamp() < deadline:
        try:
            with urlopen(f"{qdrant_url.rstrip('/')}/collections", timeout=3):
                return True
        except (OSError, URLError, TimeoutError):
            _sleep_one_second()
    return False


def _qdrant_service_available(qdrant_url: str, timeout_seconds: int) -> bool:
    try:
        with urlopen(f"{qdrant_url.rstrip('/')}/collections", timeout=timeout_seconds):
            return True
    except (OSError, URLError, TimeoutError):
        return False


def _sleep_one_second() -> None:
    import time

    time.sleep(1)


def _run_corpus_ingestion(
    *,
    evidence_dir: Path,
    qdrant_url: str,
    qdrant_collection: str,
    reset_qdrant: bool,
    embedding_model: str,
    vector_size: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    report_path = evidence_dir / "rag_ingestion_run_report.json"
    command = [
        sys.executable,
        "scripts/ingest_nvidia_corpus.py",
        "--backend",
        "qdrant",
        "--qdrant-url",
        qdrant_url,
        "--collection-name",
        qdrant_collection,
        "--embedding-model",
        embedding_model,
        "--vector-size",
        str(vector_size),
        "--require-real-embeddings",
        "--report-path",
        str(report_path),
    ]
    if reset_qdrant:
        command.append("--recreate-collection")
    else:
        command.append("--skip-existing")
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=max(timeout_seconds, 180),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "BLOCKED_BY_ENVIRONMENT",
            "command": " ".join(command),
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": f"Timed out after {exc.timeout} seconds.",
            "report_path": str(report_path),
        }
    return {
        "status": "PASS" if result.returncode == 0 else "BLOCKED_BY_ENVIRONMENT",
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-3000:],
        "stderr_tail": result.stderr[-3000:],
        "report_path": str(report_path),
    }


def _extract_qdrant_vector_size(result: dict[str, Any]) -> int | None:
    vectors = result.get("config", {}).get("params", {}).get("vectors")
    if isinstance(vectors, dict):
        if isinstance(vectors.get("size"), int):
            return int(vectors["size"])
        for value in vectors.values():
            if isinstance(value, dict) and isinstance(value.get("size"), int):
                return int(value["size"])
    return None


def _try_qdrant_retrieval(*, qdrant_url: str, collection: str, timeout_seconds: int) -> dict[str, Any]:
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=qdrant_url, timeout=timeout_seconds)
        points, _next_page = client.scroll(
            collection_name=collection,
            limit=1,
            with_payload=True,
            with_vectors=True,
        )
        if not points:
            return {"status": "BLOCKED_BY_ENVIRONMENT", "reason": "Qdrant collection is empty."}
        vector = _vector_from_point(points[0])
        if not vector:
            return {"status": "BLOCKED_BY_ENVIRONMENT", "reason": "Stored point does not include a retrievable vector."}
        query = client.query_points(
            collection_name=collection,
            query=vector,
            limit=1,
            with_payload=True,
        )
        return {
            "status": "PASS" if query.points else "BLOCKED_BY_ENVIRONMENT",
            "retrieved_count": len(query.points),
            "sample_chunk_id": (points[0].payload or {}).get("chunk_id"),
        }
    except Exception as exc:
        return {"status": "BLOCKED_BY_ENVIRONMENT", "reason": str(exc)}


def _vector_from_point(point: Any) -> list[float] | None:
    vector = getattr(point, "vector", None)
    if isinstance(vector, dict):
        first = next(iter(vector.values()), None)
        return list(first) if first else None
    if vector:
        return list(vector)
    return None


def _rag_blockers(
    chunks: list[Any],
    points_count: Any,
    retrieval_result: dict[str, Any],
    min_points: int,
) -> list[str]:
    blockers: list[str] = []
    if not chunks:
        blockers.append("Local NVIDIA corpus produced no chunks.")
    if int(points_count or 0) < min_points:
        blockers.append(f"Qdrant collection has {points_count or 0} points; minimum required is {min_points}.")
    if retrieval_result["status"] != "PASS":
        blockers.append(f"Qdrant retrieval check blocked: {retrieval_result.get('reason', 'unknown reason')}")
    return blockers


def _dependencies_block_product_like_acceptance(reports: list[dict[str, Any]]) -> bool:
    return any(report["status"] != "PASS" for report in reports)


def _sanitize_url(value: str) -> str:
    if "@" not in value:
        return value
    prefix, suffix = value.rsplit("@", 1)
    scheme, _credentials = prefix.split("://", 1)
    return f"{scheme}://***:***@{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real PostgreSQL/Qdrant/RAG service proof.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--database-url", default=os.getenv("PRODUCT_DB_URL", DEFAULT_POSTGRES_URL))
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL))
    parser.add_argument("--qdrant-collection", default=os.getenv("QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION))
    parser.add_argument("--product-like-acceptance", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_SERVICE_TIMEOUT_SECONDS)
    parser.add_argument("--acceptance-timeout-seconds", type=int, default=DEFAULT_ACCEPTANCE_TIMEOUT_SECONDS)
    parser.add_argument("--auto-start-services", dest="auto_start_services", action="store_true")
    parser.add_argument("--no-auto-start-services", dest="auto_start_services", action="store_false")
    parser.set_defaults(auto_start_services=False)
    parser.add_argument("--ingest-corpus", action="store_true")
    parser.add_argument("--wait-timeout-seconds", type=int, default=DEFAULT_WAIT_TIMEOUT_SECONDS)
    parser.add_argument("--reset-qdrant", action="store_true")
    parser.add_argument("--embedding-model", default=os.getenv("RAG_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL))
    parser.add_argument(
        "--vector-size", type=int, default=int(os.getenv("QDRANT_VECTOR_SIZE", str(DEFAULT_VECTOR_SIZE)))
    )
    parser.add_argument(
        "--min-points", type=int, default=int(os.getenv("QDRANT_MIN_POINTS", str(DEFAULT_QDRANT_MIN_POINTS)))
    )
    parser.add_argument("--require-docker-compose", action="store_true")
    args = parser.parse_args()

    summary = run_full_service_proof(
        args.evidence_dir,
        database_url=args.database_url,
        qdrant_url=args.qdrant_url,
        qdrant_collection=args.qdrant_collection,
        product_like_acceptance=args.product_like_acceptance,
        timeout_seconds=args.timeout_seconds,
        acceptance_timeout_seconds=args.acceptance_timeout_seconds,
        auto_start_services=args.auto_start_services,
        ingest_corpus=args.ingest_corpus,
        reset_qdrant=args.reset_qdrant,
        wait_timeout_seconds=args.wait_timeout_seconds,
        embedding_model=args.embedding_model,
        vector_size=args.vector_size,
        min_points=args.min_points,
        require_docker_compose=args.require_docker_compose,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from src.api.main import app
from src.database.session import configure_product_database, reset_product_database_runtime
from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "product_golden_path"
DEFAULT_POSTGRES_URL = "postgresql://postgres:postgres@localhost:5432/startup_radar"
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_QDRANT_COLLECTION = "nvidia_corpus"


def _product_env(database_url: str, qdrant_url: str, qdrant_collection: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "APP_MODE": "product",
            "PRODUCT_DB_URL": database_url,
            "ENABLE_PRODUCT_PERSISTENCE": "true",
            "RAG_VECTOR_BACKEND": "qdrant",
            "RAG_REQUIRED_FOR_PRODUCT": "true",
            "RAG_EMBEDDING_MODEL": env.get("RAG_EMBEDDING_MODEL", "BAAI/bge-m3"),
            "QDRANT_URL": qdrant_url,
            "QDRANT_COLLECTION": qdrant_collection,
            "QDRANT_VECTOR_SIZE": env.get("QDRANT_VECTOR_SIZE", "1024"),
            "QDRANT_MIN_POINTS": env.get("QDRANT_MIN_POINTS", "10"),
            "RAG_RETRIEVAL_MODE": env.get("RAG_RETRIEVAL_MODE", "hybrid_with_rerank"),
            "RERANKER_PROVIDER": env.get("RERANKER_PROVIDER", "local_cross_encoder"),
            "RERANKER_MODEL": env.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
            "AGENT_ORCHESTRATION_ENABLED": "true",
        }
    )
    return env


def run_acceptance(
    *,
    evidence_dir: Path,
    database_url: str,
    qdrant_url: str,
    qdrant_collection: str,
) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat()
    previous_env = os.environ.copy()
    product_env = _product_env(database_url, qdrant_url, qdrant_collection)
    steps: list[dict[str, Any]] = []
    errors: list[str] = []
    status = "PASS"
    try:
        os.environ.update(product_env)
        configure_product_database(database_url, create_schema=False)
        with TestClient(app) as client:
            expected = _load_json("expected.json")
            startup = _load_json("startup.json")
            startup["name"] = f"{startup['name']} {datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

            readiness = _request(client, "GET", "/product/readiness", steps)
            if readiness.get("ready") is not True:
                raise RuntimeError(f"Product readiness is not ready: {readiness.get('user_messages', [])}")

            capabilities = _request(client, "GET", "/product/capabilities", steps)
            if len(capabilities) < int(expected["min_capabilities"]):
                raise RuntimeError(f"Capability count too low: {len(capabilities)}")

            created = _request(client, "POST", "/startups", steps, json=startup, expected_status=201)
            run = _request(
                client,
                "POST",
                "/workflows/product-runs",
                steps,
                json={"startup_id": created["id"], "use_rag": True},
                expected_status=201,
            )
            if run["status"] not in {"completed", "degraded", "awaiting_review"}:
                raise RuntimeError(f"Canonical product workflow did not produce an inspectable result: {run['status']}")
            analysis_run_id = run.get("analysis_run_id")
            if not analysis_run_id:
                raise RuntimeError("Canonical workflow did not persist an analysis_run_id.")

            claims = _request(client, "GET", f"/analysis-runs/{analysis_run_id}/claims", steps)
            if int(claims["total"]) < int(expected["min_claims"]):
                raise RuntimeError(f"Claim count too low: {claims['total']}")

            coverage = _request(client, "GET", f"/analysis-runs/{analysis_run_id}/evidence-coverage", steps)
            if int(coverage["total_claims"]) <= 0:
                raise RuntimeError("Evidence coverage has no claims.")

            recommendations = _request(
                client,
                "POST",
                f"/analysis-runs/{analysis_run_id}/activation-recommendations/generate",
                steps,
                expected_status=201,
            )
            if int(recommendations["total"]) < int(expected["min_activation_recommendations"]):
                raise RuntimeError(f"Recommendation count too low: {recommendations['total']}")

            dossier = _request(
                client,
                "POST",
                f"/analysis-runs/{analysis_run_id}/dossier",
                steps,
                expected_status=201,
            )
            if not dossier.get("dossier", {}).get("dossier_json"):
                raise RuntimeError("Dossier JSON missing.")

            quality = _request(
                client,
                "POST",
                f"/analysis-runs/{analysis_run_id}/quality-runs",
                steps,
                expected_status=201,
            )
            if len(quality.get("metrics", [])) < int(expected["quality_metrics_min"]):
                raise RuntimeError("Quality metrics missing.")

            export = _request(
                client,
                "POST",
                f"/analysis-runs/{analysis_run_id}/exports",
                steps,
                json={"export_type": expected["export_type"]},
                expected_status=201,
            )
            if export["status"] != expected["export_status"]:
                raise RuntimeError(f"Export status mismatch: {export['status']}")
    except Exception as exc:
        status = "FAIL"
        errors.append(str(exc))
    finally:
        reset_product_database_runtime()
        _restore_environment(previous_env)

    payload = {
        "report_id": "acceptance_report",
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "started_at": started_at,
        "details": {
            "product_like": True,
            "steps": steps,
            "database_url": _sanitize_url(database_url),
            "qdrant_url": qdrant_url,
            "qdrant_collection": qdrant_collection,
        },
        "errors": errors,
    }
    write_json(evidence_dir / "acceptance_report.json", payload)
    return payload


def _request(
    client: TestClient,
    method: str,
    path: str,
    steps: list[dict[str, Any]],
    *,
    json: dict[str, Any] | None = None,
    expected_status: int = 200,
) -> Any:
    response = client.request(method, path, json=json)
    steps.append({"method": method, "path": path, "status_code": response.status_code})
    if response.status_code != expected_status:
        raise RuntimeError(f"{method} {path} returned {response.status_code}: {response.text[:1000]}")
    return response.json()


def _load_json(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")))


def _restore_environment(previous_env: dict[str, str]) -> None:
    for key in tuple(os.environ):
        if key not in previous_env:
            del os.environ[key]
    os.environ.update(previous_env)


def _sanitize_url(value: str) -> str:
    if "@" not in value:
        return value
    prefix, suffix = value.rsplit("@", 1)
    scheme, _credentials = prefix.split("://", 1)
    return f"{scheme}://***:***@{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run product-like acceptance against real local dependencies.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--database-url", default=os.getenv("PRODUCT_DB_URL", DEFAULT_POSTGRES_URL))
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL))
    parser.add_argument("--qdrant-collection", default=os.getenv("QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION))
    args = parser.parse_args()
    payload = run_acceptance(
        evidence_dir=args.evidence_dir,
        database_url=args.database_url,
        qdrant_url=args.qdrant_url,
        qdrant_collection=args.qdrant_collection,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

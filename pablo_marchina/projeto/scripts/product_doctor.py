#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.load_product_env import load_product_env
from scripts.local_proof_doctor import DEFAULT_TIMEOUT_SECONDS, run_doctor
from src.config.product_config_validator import validate_product_configuration
from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED_BY_ENVIRONMENT"


def build_product_doctor_report(
    *,
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    configuration_only: bool = False,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    require_docker_compose: bool = False,
    external_services_ok: bool = True,
) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    load_product_env()
    config_report = validate_product_configuration().model_dump()
    service_report: dict[str, Any] | None = None
    if not configuration_only:
        service_report = run_doctor(
            evidence_dir=evidence_dir,
            database_url=os.getenv("PRODUCT_DB_URL", "postgresql://postgres:postgres@localhost:5432/startup_radar"),
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            qdrant_collection=os.getenv("QDRANT_COLLECTION", "nvidia_corpus"),
            embedding_model=os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/BAAI/bge-m3"),
            timeout_seconds=timeout_seconds,
            require_docker_compose=require_docker_compose,
            external_services_ok=external_services_ok,
        )

    status = _aggregate_status(
        config_status=str(config_report["status"]),
        service_status=None if service_report is None else str(service_report["status"]),
    )
    report = {
        "report_id": "product_doctor_report",
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "configuration_only": configuration_only,
        "product_configuration": config_report,
        "service_doctor": service_report,
        "next_actions": _next_actions(config_report, service_report),
    }
    write_json(evidence_dir / "product_doctor_report.json", report)
    return report


def _aggregate_status(*, config_status: str, service_status: str | None) -> str:
    if config_status != PASS:
        return FAIL
    if service_status is None:
        return PASS
    if service_status == PASS:
        return PASS
    if service_status == BLOCKED:
        return BLOCKED
    return FAIL


def _next_actions(config_report: dict[str, Any], service_report: dict[str, Any] | None) -> list[str]:
    actions: list[str] = []
    for check in config_report.get("checks", []):
        if check.get("status") == FAIL:
            actions.append(str(check.get("reason", "Fix product configuration.")))
    if service_report:
        actions.extend(str(action) for action in service_report.get("next_actions", []))
    return list(dict.fromkeys(actions))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate product runtime configuration and required services.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--configuration-only", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--require-docker-compose", action="store_true")
    parser.add_argument("--external-services-ok", dest="external_services_ok", action="store_true")
    parser.add_argument("--no-external-services-ok", dest="external_services_ok", action="store_false")
    parser.add_argument("--allow-blocked-report", action="store_true")
    parser.set_defaults(external_services_ok=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_product_doctor_report(
        evidence_dir=args.evidence_dir,
        configuration_only=args.configuration_only,
        timeout_seconds=args.timeout_seconds,
        require_docker_compose=args.require_docker_compose,
        external_services_ok=args.external_services_ok,
    )
    status = report["status"]
    print(f"{status}: product doctor")
    for action in report["next_actions"]:
        print(f"  - {action}")
    if status == PASS or (status == BLOCKED and args.allow_blocked_report):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

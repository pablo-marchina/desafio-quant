#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"
BLOCKING_STATUSES = {"FAIL", "BLOCKED_BY_ENVIRONMENT", "PENDING", "TBD", "NOT_RUN"}
PENDING_PREFIXES = ("PENDING_", "TBD_")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check final security and release artifacts.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    required = [
        "security_scan_report.json",
        "release_artifact_manifest.json",
        "license_inventory.json",
        "secret_scan_report.json",
        "dependency_vulnerability_report.json",
        "sast_report.json",
        "sbom_report.json",
        "container_scan_report.json",
        "openssf_scorecard_report.json",
        "no_hidden_manual_steps_report.json",
    ]
    legacy_aliases = {"sbom_report.json": "sbom.json"}
    accepted_exceptions = _load_accepted_exceptions(args.evidence_dir / "security_exception_ledger.csv")
    missing = [name for name in required if not (args.evidence_dir / name).exists()]
    missing = [
        name
        for name in missing
        if name not in legacy_aliases or not (args.evidence_dir / legacy_aliases[name]).exists()
    ]
    failures = [f"missing {name}" for name in missing]
    security_path = args.evidence_dir / "security_scan_report.json"
    if security_path.exists():
        security = json.loads(security_path.read_text(encoding="utf-8"))
        if security.get("status") == "FAIL":
            failures.append("security_scan_report.json has FAIL status")
    license_path = args.evidence_dir / "license_inventory.json"
    if license_path.exists():
        license_inventory = json.loads(license_path.read_text(encoding="utf-8"))
        if "python_dependency_count" not in license_inventory:
            failures.append("license_inventory.json is not a dependency manifest inventory")
    for name in required:
        path = args.evidence_dir / name
        if not path.exists() and name in legacy_aliases:
            path = args.evidence_dir / legacy_aliases[name]
        if path.exists() and path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            status = str(payload.get("status", "NOT_RUN"))
            if _is_blocking_status(status) and name not in accepted_exceptions:
                failures.append(f"{name} has blocking status {status}")
    if failures:
        print("FAIL: security/release artifacts missing")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: security/release artifact gate")
    return 0


def _is_blocking_status(status: str) -> bool:
    return status in BLOCKING_STATUSES or any(status.startswith(prefix) for prefix in PENDING_PREFIXES)


def _load_accepted_exceptions(path: Path) -> set[str]:
    if not path.exists():
        return set()
    accepted: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            artifact = (row.get("artifact") or row.get("report") or "").strip()
            decision = (row.get("decision") or row.get("status") or "").strip().upper()
            approved_by = (row.get("approved_by") or "").strip()
            expires_at = (row.get("expires_at") or "").strip()
            if artifact and decision in {"ACCEPTED", "APPROVED"} and approved_by and expires_at:
                accepted.add(artifact)
    return accepted


if __name__ == "__main__":
    raise SystemExit(main())

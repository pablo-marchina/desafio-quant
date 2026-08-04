#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = PROJECT_ROOT / "data" / "free_external_tool_registry.csv"
DEFAULT_REPORT = PROJECT_ROOT / "final_case_evidence" / "free_external_tool_registry_report.json"

REQUIRED_FIELDS = {
    "tool",
    "provider",
    "category",
    "free_tier_available",
    "api_key_required",
    "signup_required",
    "rate_limit",
    "terms_url",
    "data_retention",
    "privacy_risk",
    "configured",
    "readiness_check",
    "decision",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate free external tool governance registry.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    failures: list[str] = []
    rows: list[dict[str, str]] = []
    if not args.registry.exists():
        failures.append(f"missing registry: {args.registry}")
    else:
        with args.registry.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing_fields = sorted(REQUIRED_FIELDS - set(reader.fieldnames or []))
            if missing_fields:
                failures.append(f"missing fields: {', '.join(missing_fields)}")
            rows = list(reader)
        for index, row in enumerate(rows, start=2):
            if row.get("api_key_required", "").lower() == "true" and not row.get("readiness_check"):
                failures.append(f"line {index}: API-key tool requires readiness_check")
            if not row.get("terms_url"):
                failures.append(f"line {index}: missing terms_url")
            if row.get("configured", "").lower() == "true" and row.get("decision") == "FUTURE_RESEARCH_BY_CONSTRAINT":
                failures.append(f"line {index}: configured tool cannot be future-only")
    payload = {
        "report_id": "free_external_tool_registry_report",
        "status": "PASS" if not failures else "FAIL",
        "generated_at": datetime.now(UTC).isoformat(),
        "registry": str(args.registry),
        "tool_count": len(rows),
        "failures": failures,
    }
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failures:
        print("FAIL: free external tool registry")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: free external tool registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def validate_benchmark_type_policy(evidence_dir: Path) -> list[str]:
    failures: list[str] = []
    catalog_types = _load_catalog_types(evidence_dir / "candidate_catalog.csv")
    report_path = evidence_dir / "output_value_benchmark_report.json"
    if not report_path.exists():
        return []
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    for decision in payload.get("decisions", []) or []:
        if not isinstance(decision, dict):
            continue
        candidate_id = str(decision.get("candidate_id", ""))
        benchmark_type = str(decision.get("benchmark_type") or catalog_types.get(candidate_id, "")).upper()
        if benchmark_type == "PROXY" and decision.get("promotion_allowed") is True:
            failures.append(f"{candidate_id}: proxy benchmark cannot allow runtime promotion")
    return failures


def _load_catalog_types(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row.get("candidate_id", ""): row.get("benchmark_type", "")
            for row in csv.DictReader(handle)
            if row.get("candidate_id")
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Block runtime promotion based on proxy benchmark evidence.")
    parser.add_argument("--evidence-dir", type=Path, default=Path("final_case_evidence"))
    args = parser.parse_args()

    failures = validate_benchmark_type_policy(args.evidence_dir)
    if failures:
        print("FAIL: benchmark type policy")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: benchmark type policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

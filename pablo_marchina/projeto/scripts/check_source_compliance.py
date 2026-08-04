#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check source compliance report.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--require-live", action="store_true")
    args = parser.parse_args()

    report_path = args.evidence_dir / "source_compliance_report.json"
    registry_path = args.evidence_dir / "data_rights_registry.csv"
    failures = []
    if not report_path.exists():
        failures.append(f"missing {report_path}")
    if not registry_path.exists():
        failures.append(f"missing {registry_path}")
    if report_path.exists() and args.require_live:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if payload.get("live") is not True:
            failures.append("source compliance report is not from live collection")

    if failures:
        print("FAIL: source compliance")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: source compliance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

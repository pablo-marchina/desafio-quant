#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Check final lineage coverage artifacts.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    required = [
        args.evidence_dir / "data_lineage_report.json",
        args.evidence_dir / "evidence_to_decision_coverage.json",
        args.evidence_dir / "decision_ledger.csv",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        print("FAIL: lineage artifacts missing")
        for path in missing:
            print(f"  {path}")
        return 1
    print("PASS: lineage coverage artifacts exist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

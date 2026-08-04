#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check candidate promotion closure artifacts.")
    parser.add_argument("--evidence-dir", type=Path, default=Path("final_case_evidence"))
    args = parser.parse_args()
    required = [
        args.evidence_dir / "candidate_catalog.csv",
        args.evidence_dir / "candidate_decision_matrix.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("FAIL: candidate promotion closure")
        for path in missing:
            print(f"  missing: {path}")
        return 1
    print("PASS: candidate promotion closure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

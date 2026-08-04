#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR
from src.governance.final_closure import validate_final_closure_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate canonical Epic 30 candidate governance artifacts.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    failures = validate_final_closure_artifacts(args.evidence_dir)
    if failures:
        print("FAIL: candidate governance final closure")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: candidate governance final closure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

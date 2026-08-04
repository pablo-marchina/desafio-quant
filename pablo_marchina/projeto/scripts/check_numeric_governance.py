#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Check final numeric governance evidence.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--skip-magic-scan", action="store_true")
    args = parser.parse_args()

    failures: list[str] = []
    calibration = args.evidence_dir / "calibration_registry.csv"
    if not calibration.exists():
        failures.append(f"missing {calibration}")

    if not args.skip_magic_scan:
        result = subprocess.run(
            [sys.executable, "scripts/scan_magic_values.py", "--check"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            failures.append("scan_magic_values.py --check failed")

    if failures:
        print("FAIL: numeric governance")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: numeric governance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, DEFAULT_ROADMAP_PATH, build_initial_evidence_pack


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate final benchmark-first evidence artifacts.")
    parser.add_argument("--roadmap", type=Path, default=DEFAULT_ROADMAP_PATH)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    outputs = build_initial_evidence_pack(args.roadmap, args.evidence_dir)
    print("Final evidence pack generated:")
    for name, path in sorted(outputs.items()):
        print(f"  {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR
from src.governance.final_closure import generate_final_closure_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the final candidate decision matrix and promotion ledger.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()

    outputs = generate_final_closure_artifacts(evidence_dir=args.evidence_dir)
    print(f"PASS: candidate decision matrix: {outputs['candidate_decision_matrix']}")
    print(f"PASS: runtime promotion ledger: {outputs['runtime_promotion_ledger']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

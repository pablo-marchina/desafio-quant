#!/usr/bin/env python3
"""CLI runner for scraping baseline calibration.

Usage:
    python scripts/calibrate_scraping_baseline.py                      # full report (blocked)
    python scripts/calibrate_scraping_baseline.py --real-collector     # with real collector
    python scripts/calibrate_scraping_baseline.py --check              # exit 0 only if production_allowed
    python scripts/calibrate_scraping_baseline.py --json               # JSON output
    python scripts/calibrate_scraping_baseline.py --real-collector --json --check  # all flags
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.evaluation.scraping_baseline import run_full_calibration


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}

    golden_path = Path(args[0]) if args else Path("data/eval/golden_scraping_baseline.json")
    real_collector = "--real-collector" in flags

    collector = None
    if real_collector:
        from src.scraping.collector import build_collector

        collector = build_collector()

    result = run_full_calibration(
        golden_path=golden_path,
        real_collector_available=real_collector,
        collector=collector,
    )

    if "--json" in flags:
        clean = {
            "calibration_status": result["calibration_status"],
            "production_allowed": result["production_allowed"],
            "golden_set_size": result["golden_set_size"],
            "collector_validation": result.get("collector_validation", {}),
            "recommendations": {k: v for k, v in result["recommendations"].items()},
            "marginal_gains": result["marginal_gains"],
        }
        print(json.dumps(clean, indent=2, default=str))
    else:
        print(result["report"])
        cv = result.get("collector_validation", {})
        if cv:
            print("\nCollector Validation:")
            print(f"  collector_available: {cv.get('collector_available')}")
            print(f"  real_startups_validated: {cv.get('real_startups_validated', 0)}")
            print(f"  category_precision: {cv.get('category_precision', 'N/A')}")
            print(f"  category_recall: {cv.get('category_recall', 'N/A')}")
            print(f"  category_f1: {cv.get('category_f1', 'N/A')}")

    if "--check" in flags:
        if result["production_allowed"] and result["calibration_status"] == "baseline_measured":
            sys.exit(0)
        print(
            f"\nBLOCKED: calibration_status={result['calibration_status']}, "
            f"production_allowed={result['production_allowed']}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

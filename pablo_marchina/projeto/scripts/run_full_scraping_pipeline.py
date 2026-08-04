#!/usr/bin/env python3
"""End-to-end scraping pipeline runner.

Sequences the major pipeline stages:
  1. NVIDIA source sync (via sync_nvidia_sources)
  2. Discovery runs  (via POST /discovery/run-source-scraper for each scraper-based source)
  3. Coverage report (via source_coverage_report)

Usage:
    python scripts/run_full_scraping_pipeline.py
    python scripts/run_full_scraping_pipeline.py --dry-run
    python scripts/run_full_scraping_pipeline.py --skip-nvidia --skip-discovery
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime


def _run_step(description: str, cmd: list[str], *, dry_run: bool = False) -> bool:
    now = datetime.now(UTC).strftime("%H:%M:%S")
    print(f"[{now}] {description}...")
    print(f"       > {' '.join(cmd)}")
    if dry_run:
        print("       DRY RUN — skipped")
        return True
    result = subprocess.run(cmd, capture_output=False)
    ok = result.returncode == 0
    prefix = "OK" if ok else "FAIL"
    print(f"  [{prefix}] exit code {result.returncode}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full scraping pipeline end-to-end.")
    parser.add_argument("--dry-run", action="store_true", help="Print steps without executing")
    parser.add_argument("--skip-nvidia", action="store_true", help="Skip NVIDIA source sync")
    parser.add_argument("--skip-discovery", action="store_true", help="Skip discovery source scraping")
    parser.add_argument("--skip-report", action="store_true", help="Skip coverage report")
    args = parser.parse_args()

    start = datetime.now(UTC)
    print("=" * 60)
    print(f"FULL SCRAPING PIPELINE — started at {start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    steps_passed = 0
    steps_failed = 0

    if not args.skip_nvidia:
        ok = _run_step(
            "NVIDIA source sync (staging only)",
            [sys.executable, "scripts/sync_nvidia_sources.py", "--staging-only", "--rate-limit-seconds", "2"],
            dry_run=args.dry_run,
        )
        if ok:
            steps_passed += 1
        else:
            steps_failed += 1

    if not args.skip_discovery:
        from src.discovery.source_registry import load_sources

        scraper_sources = [s for s in load_sources().values() if s.collection_method.value in ("static_html",)]
        for src in scraper_sources:
            ok = _run_step(
                f"Discovery scraper: {src.source_id}",
                [sys.executable, "-c",
                 f"from src.discovery.service import StartupDiscoveryService; "
                 f"from src.api.deps import get_db_session; "
                 f"svc = StartupDiscoveryService(next(get_db_session())); "
                 f"print(svc.run_source_scraper_discovery('{src.source_id}'))"],
                dry_run=args.dry_run,
            )
            if ok:
                steps_passed += 1
            else:
                steps_failed += 1

    if not args.skip_report:
        ok = _run_step(
            "Coverage report",
            [sys.executable, "scripts/source_coverage_report.py"],
            dry_run=args.dry_run,
        )
        if ok:
            steps_passed += 1
        else:
            steps_failed += 1

    elapsed = (datetime.now(UTC) - start).total_seconds()
    print()
    print("=" * 60)
    print(f"PIPELINE FINISHED — {steps_passed} passed, {steps_failed} failed, {elapsed:.1f}s")
    print("=" * 60)

    sys.exit(0 if steps_failed == 0 else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Scheduler that refreshes stale sources based on their freshness policy.

Checks each source's *stale_after_days* or *freshness_policy* against the
last collected timestamp in the corpus metadata, and triggers a re-fetch
for any source that is past its freshness window.

Usage:
    python scripts/scheduler_refresh.py
    python scripts/scheduler_refresh.py --dry-run
    python scripts/scheduler_refresh.py --source-id nim triton --promote
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CORPUS_DIR = _PROJECT_ROOT / "data" / "nvidia_corpus"
_ALLOWLIST_FILE = _CORPUS_DIR / "source_allowlist.yaml"
_SOURCES_FILE = _CORPUS_DIR / "sources.yaml"

# Map freshness_policy values to TTL in days
_FRESHNESS_TTL: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "static": 365,
    "never": 9999,
}


def _load_sources_metadata() -> dict[str, dict]:
    """Load sources.yaml metadata — last_checked_at, freshness_policy, etc."""
    if not _SOURCES_FILE.exists():
        return {}
    raw = yaml.safe_load(_SOURCES_FILE.read_text(encoding="utf-8"))
    return raw.get("sources", {})


def _stale_after_days(entry: dict) -> int:
    sad = entry.get("stale_after_days")
    if sad is not None:
        return int(sad)
    fp = entry.get("freshness_policy", "monthly")
    return _FRESHNESS_TTL.get(fp, 30)


def _is_stale(entry: dict) -> tuple[bool, str | None]:
    sid = entry.get("source_id", "?")
    meta = _load_sources_metadata().get(sid)

    stale_days = _stale_after_days(entry)
    if stale_days >= 9999:
        return False, "never stale"

    last_checked = None
    if meta:
        last_str = meta.get("last_checked_at") or meta.get("collected_at")
        if last_str:
            try:
                last_checked = datetime.fromisoformat(last_str)
            except (ValueError, TypeError):
                pass

    if last_checked is None:
        return True, "never collected"

    age = datetime.now(UTC) - last_checked
    if age >= timedelta(days=stale_days):
        return True, f"stale ({age.days}d > {stale_days}d)"
    return False, f"fresh ({age.days}d < {stale_days}d)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh stale corpus sources.")
    parser.add_argument("--dry-run", action="store_true", help="Only report stale sources, don't fetch")
    parser.add_argument("--source-id", nargs="+", default=None, help="Only check specific source IDs")
    parser.add_argument("--promote", action="store_true", help="Auto-promote refreshed sources to corpus")
    args = parser.parse_args()

    if not _ALLOWLIST_FILE.exists():
        print(f"ERROR: Allowlist not found: {_ALLOWLIST_FILE}", file=sys.stderr)
        sys.exit(1)

    raw = yaml.safe_load(_ALLOWLIST_FILE.read_text(encoding="utf-8"))
    all_entries: list[dict] = raw.get("sources", [])

    if args.source_id:
        all_entries = [e for e in all_entries if e.get("source_id") in args.source_id]

    stale: list[dict] = []
    fresh: list[dict] = []
    for entry in all_entries:
        if not entry.get("allowed", False):
            continue
        is_stale, reason = _is_stale(entry)
        if is_stale:
            stale.append(entry)
        else:
            fresh.append(entry)

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"Scheduler Refresh Report ({now})")
    print(f"  Total sources:  {len(all_entries)}")
    print(f"  Fresh:          {len(fresh)}")
    print(f"  Stale:          {len(stale)}")
    print()

    if stale:
        print("--- Stale Sources ---")
        for entry in stale:
            _, reason = _is_stale(entry)
            print(f"  {entry['source_id']:40s} {reason}")
        print()

        if args.dry_run:
            print("DRY RUN — no fetching performed")
            return

        from scripts.sync_nvidia_sources import run_sync, parse_args

        fetch_args = [
            "--source-id",
            *[e["source_id"] for e in stale],
            "--rate-limit-seconds",
            "2",
        ]
        if args.promote:
            fetch_args.append("--promote")
        else:
            fetch_args.append("--staging-only")

        ns = parse_args(fetch_args)
        report = run_sync(ns)

        print()
        print("Sync completed. Report:")
        print(f"  Downloaded: {report.sources_downloaded}")
        print(f"  Failed:     {len(report.sources_failed)}")
        for f in report.sources_failed:
            print(f"    - {f}")
    else:
        print("All sources are up to date.")


if __name__ == "__main__":
    main()

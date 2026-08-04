#!/usr/bin/env python3
"""Generate a coverage report of all configured sources across registries.

Usage:
    python scripts/source_coverage_report.py
    python scripts/source_coverage_report.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml


def _collect_nvidia_sources() -> dict:
    path = Path("data/nvidia_corpus/source_allowlist.yaml")
    if not path.exists():
        return {"error": "source_allowlist.yaml not found"}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = [s for s in raw.get("sources", []) if s.get("allowed", False)]
    return {
        "total": len(sources),
        "by_freshness": dict(Counter(s.get("freshness_policy", "unknown") for s in sources)),
        "by_gap": dict(Counter(g for s in sources for g in s.get("gap_types", []))),
        "sources": [{"source_id": s["source_id"], "title": s.get("title", ""), "url": s.get("url", "")} for s in sources],
    }


def _collect_scraping_sources() -> dict:
    from src.scraping.source_registry import load_source_registry

    registry = load_source_registry()
    sources = list(registry.values())
    return {
        "total": len(sources),
        "production_enabled": sum(1 for s in sources if s.production_enabled),
        "blocked": sum(1 for s in sources if not s.production_enabled),
        "by_category": dict(Counter(s.source_category for s in sources)),
        "by_collector_type": dict(Counter(s.collector_type for s in sources)),
        "sources": [
            {
                "source_id": s.source_id,
                "category": s.source_category,
                "collector_type": s.collector_type,
                "production_enabled": s.production_enabled,
                "blockers": s.production_blockers,
                "base_url": s.base_url,
            }
            for s in sources
        ],
    }


def _collect_discovery_sources() -> dict:
    from src.discovery.source_registry import load_sources

    sources = load_sources()
    return {
        "total": len(sources),
        "by_type": dict(Counter(s.source_type.value for s in sources.values())),
        "by_method": dict(Counter(s.collection_method.value for s in sources.values())),
        "sources": [
            {
                "source_id": s.source_id,
                "source_type": s.source_type.value,
                "collection_method": s.collection_method.value,
                "base_url": s.base_url,
            }
            for s in sources.values()
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate source coverage report.")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    nvidia = _collect_nvidia_sources()
    scraping = _collect_scraping_sources()
    discovery = _collect_discovery_sources()

    if args.json:
        report = {
            "nvidia_allowlist": nvidia,
            "scraping_registry": scraping,
            "discovery_sources": discovery,
        }
        json.dump(report, sys.stdout, indent=2, default=str)
        return

    total = nvidia.get("total", 0) + scraping["total"] + discovery["total"]
    overlap = len({s["source_id"] for s in nvidia.get("sources", [])} & {s["source_id"] for s in scraping["sources"]})
    print("=" * 60)
    print("SOURCE COVERAGE REPORT")
    print("=" * 60)
    print(f"  NVIDIA allowlist:       {nvidia.get('total', 'ERR'):>3d} sources")
    print(f"  Scraping registry:      {scraping['total']:>3d} sources")
    print(f"  Discovery sources:      {discovery['total']:>3d} sources")
    print(f"  Overlapping IDs:        {overlap:>3d}")
    print(f"  Grand total (unique):   {total - overlap:>3d}")
    print()
    print("--- Scraping Registry ---")
    print(f"  Production enabled:  {scraping['production_enabled']}")
    print(f"  Blocked:             {scraping['blocked']}")
    print(f"  By category:")
    for cat, cnt in sorted(scraping["by_category"].items()):
        print(f"    {cat:40s} {cnt:>3d}")
    print(f"  By collector type:")
    for ct, cnt in sorted(scraping["by_collector_type"].items()):
        print(f"    {ct:40s} {cnt:>3d}")
    print()
    print("--- NVIDIA Allowlist ---")
    print(f"  By freshness:")
    for f, cnt in sorted(nvidia.get("by_freshness", {}).items()):
        print(f"    {f:40s} {cnt:>3d}")
    print()
    print("--- Discovery Sources ---")
    print(f"  By type:")
    for t, cnt in sorted(discovery["by_type"].items()):
        print(f"    {t:40s} {cnt:>3d}")
    print("=" * 60)


if __name__ == "__main__":
    main()

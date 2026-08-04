#!/usr/bin/env python3
"""Automated radar — periodically rescrape and detect changes.

Usage:
    python scripts/radar_scheduler.py                    # daily run (all production sources)
    python scripts/radar_scheduler.py --source startup_x  # single source
    python scripts/radar_scheduler.py --dry-run           # print what would be done
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from datetime import UTC, datetime
from typing import Any

from src.scraping.cache import scrape_cache
from src.scraping.change_detector import ChangeDetector
from src.scraping.http_collector import HttpSourceCollector, list_governed_sources

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


def run_radar(
    collector: HttpSourceCollector | None = None,
    *,
    source_id: str | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Run radar: rescrape sources, detect changes, report significance.

    Returns:
        List of change reports, each a dict with keys:
            ``source_id``, ``url``, ``changed``, ``significance``,
            ``sections_changed`` (list), ``previous_hash``, ``current_hash``
    """
    collector = collector or HttpSourceCollector()
    detector = ChangeDetector()
    reports: list[dict[str, Any]] = []

    sources = list_governed_sources()
    if source_id:
        sources = [s for s in sources if s.source_id == source_id]

    logger.info("Radar: checking %d source(s)", len(sources))

    for source in sources:
        url = (source.base_url or "").strip()
        if not url:
            continue

        if dry_run:
            logger.info("[DRY RUN] Would rescrape %s (%s)", source.source_id, url)
            continue

        fr = collector.collect_one(source)

        with scrape_cache() as cache:
            history = cache.get_hash_history(url, max_entries=2)
            current_hash = fr.content_hash or ""

            if current_hash:
                cache.record_hash(url, current_hash)

            changed = False
            significance = "unknown"
            sections_changed: list[dict[str, Any]] = []

            if len(history) >= 1:
                old_text = fr.raw_text if fr.status in ("fetched", "cached") else ""
                new_text = fr.raw_text if fr.status in ("fetched", "cached") else ""
                report = detector.detect(
                    old_hash=history[0],
                    new_hash=current_hash,
                    old_text=old_text if old_text else "",
                    new_text=new_text if new_text else "",
                )
                changed = report.changed
                significance = report.significance.value if report.significance else "unknown"
                sections_changed = [
                    {
                        "section": s.section_type,
                        "type": "added" if s.old_text == "" else "removed",
                    }
                    for s in (report.sections_changed or [])
                ]
            else:
                changed = False
                significance = "first_collection"

            report_entry = {
                "source_id": source.source_id,
                "url": url,
                "changed": changed,
                "significance": significance,
                "sections_changed": sections_changed,
                "previous_hash": history[0] if history else None,
                "current_hash": current_hash,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            reports.append(report_entry)

            if changed:
                level = significance.upper()
                logger.info(
                    "CHANGE [%s] %s — %s (%d section(s))",
                    level, source.source_id, url, len(sections_changed),
                )

    return reports


def persist_alerts(reports: list[dict[str, Any]]) -> None:
    """Persist HIGH/CRITICAL change alerts to a JSON file for downstream consumption."""
    alerts = [
        r for r in reports
        if r.get("changed") and r.get("significance") in ("high", "critical")
    ]
    if not alerts:
        return
    alerts_path = Path(__file__).resolve().parent.parent / ".radar_alerts.json"
    existing: list[dict[str, Any]] = []
    if alerts_path.exists():
        try:
            existing = json.loads(alerts_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.extend(alerts)
    # Keep last 1000 alerts
    alerts_path.write_text(
        json.dumps(existing[-1000:], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Persisted %d alert(s) to %s", len(alerts), alerts_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Radar — content change detection scheduler")
    parser.add_argument("--source", type=str, default=None, help="Scrape a single source ID")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done")
    parser.add_argument("--alert", action="store_true", help="Persist HIGH/CRITICAL changes to .radar_alerts.json")
    args = parser.parse_args()

    reports = run_radar(source_id=args.source, dry_run=args.dry_run)

    if args.dry_run:
        logger.info("Dry run complete. Would check %d source(s).", len(reports))
        return

    changed = [r for r in reports if r.get("changed")]
    high = [r for r in changed if r.get("significance") == "high"]
    logger.info(
        "Radar complete: %d sources checked, %d changed (%d high significance)",
        len(reports), len(changed), len(high),
    )

    if args.alert:
        persist_alerts(reports)


if __name__ == "__main__":
    main()

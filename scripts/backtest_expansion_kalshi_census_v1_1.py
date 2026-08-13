#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backtest_expansion_kalshi_census_v1 import (
    BASE,
    FAMILY_PATTERNS,
    get_json,
    host_from_url,
    match_families,
    paginate,
    year_from_market,
)

# Operational-only amendment: exact v1 scientific dictionary/classifier is imported.
# No family/query/field semantics are modified. Only independent per-Series I/O is concurrent.
VERSION = "KALSHI-CENSUS-v1.1"
BASE_SCRIPT_GIT_BLOB = "95c1ecf4cc8fd40c1de505165c7b6a7f9e4d8406"
OUTDIR = Path(os.environ.get("ARGOS_EXPANSION_OUTDIR", "artifacts/backtest_expansion_kalshi_v1_1"))
MAX_WORKERS = int(os.environ.get("ARGOS_KALSHI_WORKERS", "8"))


def fetch_series_markets(s: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
    ticker = str(s.get("ticker") or "")
    if not ticker:
        return s, [], "missing series ticker"
    try:
        hist = paginate("/historical/markets", "markets", {"series_ticker": ticker}, limit=1000)
        recent = paginate("/markets", "markets", {"series_ticker": ticker, "status": "settled"}, limit=1000)
        by_ticker: dict[str, dict[str, Any]] = {}
        for m in hist + recent:
            mt = str(m.get("ticker") or "")
            if mt:
                by_ticker[mt] = m
        return s, list(by_ticker.values()), None
    except Exception as exc:
        return s, [], str(exc)


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    cutoff = get_json("/historical/cutoff")
    series = paginate("/series", "series", {"include_volume": "true"}, limit=1000)

    category_counts = Counter(str(s.get("category") or "UNKNOWN") for s in series)
    candidate_series: list[dict[str, Any]] = []
    family_series_counts = Counter()
    source_hosts = Counter()

    for s in series:
        fams = match_families(s)
        if not fams:
            continue
        x = dict(s)
        x["matched_families"] = fams
        candidate_series.append(x)
        for fam in fams:
            family_series_counts[fam] += 1
        for src in s.get("settlement_sources") or []:
            source_hosts[host_from_url(src.get("url"))] += 1

    results: list[tuple[dict[str, Any], list[dict[str, Any]], str | None]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(fetch_series_markets, s) for s in sorted(candidate_series, key=lambda z: str(z.get("ticker") or ""))]
        for idx, fut in enumerate(as_completed(futures), start=1):
            results.append(fut.result())
            if idx % 25 == 0 or idx == len(futures):
                print(f"candidate series processed: {idx}/{len(futures)}", flush=True)

    all_market_rows: list[dict[str, Any]] = []
    unique_events: dict[str, dict[str, Any]] = {}
    family_event_sets: dict[str, set[str]] = defaultdict(set)
    family_market_counts = Counter()
    year_counts = Counter()
    series_failures: list[dict[str, str]] = []

    for s, markets, err in sorted(results, key=lambda x: str(x[0].get("ticker") or "")):
        ticker = str(s.get("ticker") or "")
        fams = list(s.get("matched_families") or [])
        if err is not None:
            series_failures.append({"series_ticker": ticker, "error": err})
            continue
        for m in markets:
            event_ticker = str(m.get("event_ticker") or "UNKNOWN")
            year = year_from_market(m)
            row = {
                "series_ticker": ticker,
                "series_title": s.get("title"),
                "series_category": s.get("category"),
                "matched_families": ";".join(fams),
                "event_ticker": event_ticker,
                "market_ticker": m.get("ticker"),
                "market_title": m.get("title"),
                "market_status": m.get("status"),
                "year": year,
                "volume_fp": m.get("volume_fp"),
                "open_time": m.get("open_time"),
                "close_time": m.get("close_time"),
                "settlement_ts": m.get("settlement_ts"),
            }
            all_market_rows.append(row)
            year_counts[year] += 1
            for fam in fams:
                family_market_counts[fam] += 1
                if event_ticker != "UNKNOWN":
                    family_event_sets[fam].add(event_ticker)
            if event_ticker != "UNKNOWN":
                unique_events.setdefault(event_ticker, {
                    "event_ticker": event_ticker,
                    "series_ticker": ticker,
                    "series_title": s.get("title"),
                    "matched_families": fams,
                })

    summary = {
        "artifact": "BACKTEST_EXPANSION_KALSHI_CENSUS",
        "version": VERSION,
        "operational_amendment_only": True,
        "base_scientific_script_git_blob": BASE_SCRIPT_GIT_BLOB,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "performance_blind": True,
        "linked_asset_returns_read": False,
        "pnl_read": False,
        "api_base": BASE,
        "historical_cutoff": cutoff,
        "workers": MAX_WORKERS,
        "series_total": len(series),
        "category_counts": dict(sorted(category_counts.items())),
        "candidate_series_total": len(candidate_series),
        "candidate_series_by_family_nonexclusive": dict(sorted(family_series_counts.items())),
        "candidate_markets_unique": len({str(r["market_ticker"]) for r in all_market_rows}),
        "candidate_events_unique": len(unique_events),
        "candidate_events_by_family_nonexclusive": {k: len(v) for k, v in sorted(family_event_sets.items())},
        "candidate_markets_by_family_nonexclusive": dict(sorted(family_market_counts.items())),
        "candidate_market_year_counts": dict(sorted(year_counts.items())),
        "settlement_source_hosts_candidate_series": dict(sorted(source_hosts.items())),
        "series_failures": series_failures,
        "family_dictionary": FAMILY_PATTERNS,
        "semantics": "Metadata census only. Candidate families are deterministic lexical discovery buckets inherited byte-for-byte from v1, not validated events, not PIT eligibility, and not backtest authorization.",
    }

    (OUTDIR / "kalshi_census_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    with (OUTDIR / "kalshi_candidate_series.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["ticker", "title", "category", "frequency", "matched_families", "volume_fp"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in sorted(candidate_series, key=lambda z: str(z.get("ticker") or "")):
            w.writerow({
                "ticker": s.get("ticker"),
                "title": s.get("title"),
                "category": s.get("category"),
                "frequency": s.get("frequency"),
                "matched_families": ";".join(s.get("matched_families") or []),
                "volume_fp": s.get("volume_fp"),
            })

    with (OUTDIR / "kalshi_candidate_markets.csv").open("w", newline="", encoding="utf-8") as f:
        fields = list(all_market_rows[0].keys()) if all_market_rows else ["series_ticker", "event_ticker", "market_ticker"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_market_rows)

    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()

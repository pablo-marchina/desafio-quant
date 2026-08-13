#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = "https://external-api.kalshi.com/trade-api/v2"
OUTDIR = Path(os.environ.get("ARGOS_EXPANSION_OUTDIR", "artifacts/backtest_expansion_kalshi_v1"))
TIMEOUT = 30
MAX_RETRIES = 4
MAX_PAGES = 500

# Frozen before the first census network run. Metadata only; no linked-asset returns/P&L.
FAMILY_PATTERNS: dict[str, tuple[str, ...]] = {
    "MACRO_INFLATION": (
        r"\bcpi\b", r"inflation", r"consumer price", r"\bpce\b", r"price index",
    ),
    "MACRO_LABOR": (
        r"payroll", r"unemployment", r"jobless", r"employment", r"jobs report", r"nonfarm",
    ),
    "MACRO_GROWTH_ACTIVITY": (
        r"\bgdp\b", r"retail sales", r"industrial production", r"consumer sentiment",
        r"\bism\b", r"manufacturing", r"housing starts", r"personal income",
    ),
    "MONETARY_POLICY_RATES": (
        r"\bfomc\b", r"federal reserve", r"fed funds", r"interest rate", r"rate cut",
        r"rate hike", r"treasury yield", r"10-year", r"2-year",
    ),
    "CORPORATE_EARNINGS": (
        r"earnings", r"\beps\b", r"revenue", r"quarterly sales", r"profit", r"guidance",
    ),
    "CORPORATE_MA_REG": (
        r"merger", r"acquisition", r"takeover", r"antitrust", r"\bftc\b", r"\bdoj\b",
        r"deal close", r"deal closing",
    ),
    "FDA_HEALTH_REG": (
        r"\bfda\b", r"pdufa", r"drug approval", r"advisory committee", r"complete response",
    ),
    "MARKET_ASSET_LEVEL": (
        r"s&p", r"s\&p", r"sp500", r"nasdaq", r"dow jones", r"stock price", r"\bvix\b",
        r"bitcoin", r"ethereum", r"gold", r"crude oil", r"oil price", r"treasury",
    ),
}


def get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ARGOS-backtest-expansion-census/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in {429, 500, 502, 503, 504}:
                raise
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"GET failed after retries: {url}: {last}")


def paginate(path: str, key: str, params: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    seen: set[str] = set()
    for _ in range(MAX_PAGES):
        q = dict(params)
        q["limit"] = limit
        if cursor:
            q["cursor"] = cursor
        data = get_json(path, q)
        batch = data.get(key) or []
        rows.extend(batch)
        cursor = data.get("cursor") or ""
        if not cursor:
            return rows
        if cursor in seen:
            raise RuntimeError(f"cursor loop on {path}")
        seen.add(cursor)
    raise RuntimeError(f"page safety bound exceeded on {path}")


def text_for_series(s: dict[str, Any]) -> str:
    tags = " ".join(str(x) for x in (s.get("tags") or []))
    return " ".join([str(s.get("title") or ""), str(s.get("category") or ""), tags]).casefold()


def match_families(s: dict[str, Any]) -> list[str]:
    text = text_for_series(s)
    return [fam for fam, patterns in FAMILY_PATTERNS.items() if any(re.search(p, text, flags=re.I) for p in patterns)]


def year_from_market(m: dict[str, Any]) -> str:
    for key in ("settlement_ts", "close_time", "expiration_time", "latest_expiration_time"):
        value = m.get(key)
        if not value:
            continue
        try:
            if isinstance(value, (int, float)):
                return str(datetime.fromtimestamp(value, tz=timezone.utc).year)
            return str(datetime.fromisoformat(str(value).replace("Z", "+00:00")).year)
        except Exception:
            pass
    return "UNKNOWN"


def host_from_url(url: str | None) -> str:
    if not url:
        return "UNKNOWN"
    try:
        return urllib.parse.urlparse(url).netloc or "UNKNOWN"
    except Exception:
        return "UNKNOWN"


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

    all_market_rows: list[dict[str, Any]] = []
    unique_events: dict[str, dict[str, Any]] = {}
    family_event_sets: dict[str, set[str]] = defaultdict(set)
    family_market_counts = Counter()
    year_counts = Counter()
    series_failures: list[dict[str, str]] = []

    for idx, s in enumerate(sorted(candidate_series, key=lambda z: str(z.get("ticker") or "")), start=1):
        ticker = str(s.get("ticker") or "")
        fams = list(s["matched_families"])
        if not ticker:
            continue
        try:
            hist = paginate("/historical/markets", "markets", {"series_ticker": ticker}, limit=1000)
            recent = paginate("/markets", "markets", {"series_ticker": ticker, "status": "settled"}, limit=1000)
        except Exception as exc:
            series_failures.append({"series_ticker": ticker, "error": str(exc)})
            continue

        by_ticker: dict[str, dict[str, Any]] = {}
        for m in hist + recent:
            mt = str(m.get("ticker") or "")
            if mt:
                by_ticker[mt] = m
        for m in by_ticker.values():
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
                family_event_sets[fam].add(event_ticker)
            if event_ticker != "UNKNOWN":
                unique_events.setdefault(event_ticker, {
                    "event_ticker": event_ticker,
                    "series_ticker": ticker,
                    "series_title": s.get("title"),
                    "matched_families": fams,
                })

        if idx % 20 == 0:
            print(f"candidate series processed: {idx}/{len(candidate_series)}")

    summary = {
        "artifact": "BACKTEST_EXPANSION_KALSHI_CENSUS",
        "version": "KALSHI-CENSUS-v1.0",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "performance_blind": True,
        "linked_asset_returns_read": False,
        "pnl_read": False,
        "api_base": BASE,
        "historical_cutoff": cutoff,
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
        "semantics": "Metadata census only. Candidate families are deterministic lexical discovery buckets, not validated events, not PIT eligibility, and not backtest authorization.",
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

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

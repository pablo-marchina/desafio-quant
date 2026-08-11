#!/usr/bin/env python3
"""Targeted performance-blind Gamma discovery census for EUAS-v1.1.

This is a complementary discovery route to the broad all-events census. It uses
pre-frozen title_search queries per event family, then post-filters with the
same EUAS_TEXT_CLASSIFIER_v1.0 classifier. Counts are LOWER BOUNDS: they may
establish that a minimum is exceeded, but a low count cannot prove a family is
absent or unsampleable.

No ARGOS outcome, linked-asset return, Brier/log loss, P&L or family performance
is read.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import wave1_event_universe_contract_census as base

QUERY_PROTOCOL_VERSION = "EUAS_TARGETED_DISCOVERY_v1.0"

# Frozen before targeted results are opened.
QUERY_MAP = {
    "EARNINGS_EPS": ["earnings", "EPS", "quarterly earnings"],
    "FDA_APPROVAL_ADVISORY": ["FDA", "PDUFA", "drug approval", "advisory committee"],
    "MA": ["merger", "acquisition", "acquire", "takeover", "deal close", "deal completion"],
    "ANTITRUST_REGULATORY": ["antitrust", "FTC", "DOJ", "regulatory approval", "regulatory clearance"],
    "LITIGATION_COURT": ["Supreme Court", "court ruling", "court decision", "lawsuit", "verdict", "injunction"],
    "MACRO_FED_CPI": ["FOMC", "Fed decision", "Fed rate", "CPI", "inflation", "GDP", "payrolls", "unemployment"],
}

TARGET_FAMILIES = [
    "EARNINGS_EPS",
    "FDA_APPROVAL_ADVISORY",
    "MA_DEAL_COMPLETION_REGULATORY_CLEARANCE",
    "MA_ANNOUNCEMENT_RUMOR",
    "ANTITRUST_REGULATORY",
    "LITIGATION_COURT",
    "MACRO_FED_CPI",
]


def fetch_query(query: str) -> list[dict]:
    events: list[dict] = []
    seen: set[str] = set()
    cursor = None
    for page in range(100):
        params: dict[str, object] = {
            "limit": 500,
            "closed": "true",
            "ascending": "true",
            "order": "createdAt",
            "title_search": query,
        }
        if cursor:
            params["after_cursor"] = cursor
        payload = base.fetch_json("/events/keyset", params)
        batch = payload.get("events", [])
        for event in batch:
            eid = str(event.get("id", ""))
            if eid and eid not in seen:
                seen.add(eid)
                events.append(event)
        cursor = payload.get("next_cursor")
        print(f"query={query!r} page={page+1} batch={len(batch)} total={len(events)} next={bool(cursor)}")
        if not batch or not cursor:
            break
    else:
        raise RuntimeError(f"Targeted query exceeded 100 pages: {query}")
    return events


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry-dir", default="registry")
    args = ap.parse_args()
    registry = Path(args.registry_dir)
    registry.mkdir(parents=True, exist_ok=True)

    query_records: list[dict] = []
    event_by_id: dict[str, dict] = {}
    queries_by_id: dict[str, set[str]] = defaultdict(set)
    for query_family, queries in QUERY_MAP.items():
        for query in queries:
            events = fetch_query(query)
            query_records.append({"query_family": query_family, "query": query, "returned_unique_events": len(events)})
            for event in events:
                eid = str(event.get("id", ""))
                if eid:
                    event_by_id.setdefault(eid, event)
                    queries_by_id[eid].add(query)

    rows: list[dict] = []
    by_family: dict[str, list[dict]] = defaultdict(list)
    for eid, event in event_by_id.items():
        start = base.parse_dt(event.get("startDate") or event.get("creationDate") or event.get("createdAt"))
        end = base.parse_dt(event.get("endDate") or event.get("closedTime"))
        lead_days = (end - start).total_seconds() / 86400 if start and end and end >= start else None
        volume = base.as_float(event.get("volume"))
        for family, reason in base.classify(event):
            if family not in TARGET_FAMILIES:
                continue
            row = {
                "family": family,
                "event_id": eid,
                "title": str(event.get("title", "")),
                "slug": str(event.get("slug", "")),
                "start_utc": start.isoformat().replace("+00:00", "Z") if start else "",
                "end_utc": end.isoformat().replace("+00:00", "Z") if end else "",
                "lead_days": "" if lead_days is None else f"{lead_days:.8f}",
                "volume": "" if volume is None else f"{volume:.8f}",
                "market_count": len(event.get("markets") or []),
                "queries_matched": "|".join(sorted(queries_by_id[eid])),
                "classifier_reason": reason,
                "manual_validation_status": "PENDING",
            }
            rows.append(row)
            by_family[family].append(row)

    fields = [
        "family", "event_id", "title", "slug", "start_utc", "end_utc", "lead_days", "volume",
        "market_count", "queries_matched", "classifier_reason", "manual_validation_status",
    ]
    rows.sort(key=lambda r: (r["family"], -(float(r["volume"]) if r["volume"] else 0.0), r["event_id"]))
    event_path = registry / "wave1_event_universe_targeted_census_events.csv.gz"
    base.write_gzip_csv(event_path, rows, fields)

    summary_rows: list[dict] = []
    for family in TARGET_FAMILIES:
        frows = by_family.get(family, [])
        vols = [float(r["volume"]) for r in frows if r["volume"]]
        leads = [float(r["lead_days"]) for r in frows if r["lead_days"]]
        summary_rows.append({
            "family": family,
            "candidate_event_lower_bound": len({r["event_id"] for r in frows}),
            "events_with_volume": len(vols),
            "volume_median": base.percentile(vols, 0.5),
            "volume_p25": base.percentile(vols, 0.25),
            "volume_p75": base.percentile(vols, 0.75),
            "volume_ge_1k_lower_bound": sum(v >= 1_000 for v in vols),
            "volume_ge_10k_lower_bound": sum(v >= 10_000 for v in vols),
            "volume_ge_100k_lower_bound": sum(v >= 100_000 for v in vols),
            "events_with_lead": len(leads),
            "lead_days_median": base.percentile(leads, 0.5),
            "lead_days_p25": base.percentile(leads, 0.25),
            "lead_days_p75": base.percentile(leads, 0.75),
            "manual_validation_required": True,
            "count_semantics": "LOWER_BOUND_DISCOVERY_ONLY",
        })
    summary_path = registry / "wave1_event_universe_targeted_census_summary.csv"
    base.write_csv(summary_path, summary_rows, list(summary_rows[0]))

    query_path = registry / "wave1_event_universe_targeted_query_audit.csv"
    base.write_csv(query_path, query_records, ["query_family", "query", "returned_unique_events"])

    meta = {
        "artifact": "WAVE1_EVENT_UNIVERSE_TARGETED_CENSUS",
        "version": QUERY_PROTOCOL_VERSION,
        "snapshot_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "official Polymarket Gamma API /events/keyset with frozen title_search queries",
        "performance_blind": True,
        "scientific_reopen": False,
        "classifier_version": base.CLASSIFIER_VERSION,
        "query_map": QUERY_MAP,
        "unique_events_returned_by_queries": len(event_by_id),
        "classified_rows": len(rows),
        "count_semantics": "LOWER_BOUND_DISCOVERY_ONLY; low counts cannot establish family absence/failure",
        "events_csv_gz_sha256": hashlib.sha256(event_path.read_bytes()).hexdigest(),
        "summary_csv_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "query_audit_sha256": hashlib.sha256(query_path.read_bytes()).hexdigest(),
        "limitations": [
            "title_search may miss relevant events whose family terms are absent from titles",
            "regex post-filter can create false positives/false negatives",
            "lifetime event volume is not PIT liquidity",
            "lead time does not prove the contract predated every material rumor/news item",
            "manual validation is required before using counts for EUAS gates"
        ]
    }
    meta_path = registry / "wave1_event_universe_targeted_census_summary.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

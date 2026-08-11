#!/usr/bin/env python3
"""Build the Wave-1 manual-validation queue from the targeted EUAS census.

This is a PERFORMANCE-BLIND derived-cleaning step. It does not validate a market
as belonging to a family. It only prevents cross-family propagation created by
the broad text classifier: a row is eligible for manual review only when at
least one frozen discovery query that returned the event belongs to the same
candidate family (M&A queries may feed either frozen M&A sub-family).

The frozen query map, EUAS dimensions/weights, and candidate families are not
changed. Manual validation is still required before any C/L/S gate can pass.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import wave1_event_universe_targeted_census as targeted

VERSION = "EUAS_VALIDATION_QUEUE_v1.0"

ALLOWED_BY_QUERY_FAMILY = {
    "EARNINGS_EPS": {"EARNINGS_EPS"},
    "FDA_APPROVAL_ADVISORY": {"FDA_APPROVAL_ADVISORY"},
    "MA": {"MA_DEAL_COMPLETION_REGULATORY_CLEARANCE", "MA_ANNOUNCEMENT_RUMOR"},
    "ANTITRUST_REGULATORY": {"ANTITRUST_REGULATORY"},
    "LITIGATION_COURT": {"LITIGATION_COURT"},
    "MACRO_FED_CPI": {"MACRO_FED_CPI"},
}


def query_family_lookup() -> dict[str, str]:
    out: dict[str, str] = {}
    for query_family, queries in targeted.QUERY_MAP.items():
        for query in queries:
            if query in out and out[query] != query_family:
                raise RuntimeError(f"Frozen query appears in multiple families: {query}")
            out[query] = query_family
    return out


def read_gzip_csv(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry-dir", default="registry")
    args = ap.parse_args()

    registry = Path(args.registry_dir)
    source = registry / "wave1_event_universe_targeted_census_events.csv.gz"
    if not source.exists():
        raise FileNotFoundError(source)

    rows = read_gzip_csv(source)
    lookup = query_family_lookup()
    kept: list[dict[str, str]] = []
    rejected_cross_family: list[dict[str, str]] = []

    for row in rows:
        matched_queries = [q for q in row.get("queries_matched", "").split("|") if q]
        query_families = sorted({lookup[q] for q in matched_queries if q in lookup})
        allowed = set()
        for qf in query_families:
            allowed.update(ALLOWED_BY_QUERY_FAMILY[qf])

        derived = dict(row)
        derived["query_families"] = "|".join(query_families)
        derived["query_consistent"] = str(row.get("family") in allowed)
        derived["manual_validation_status"] = "PENDING_MANUAL_REVIEW"
        derived["manual_validation_reason"] = ""
        derived["independent_event_key"] = ""
        derived["linked_asset_mapping_status"] = "PENDING"

        if row.get("family") in allowed:
            kept.append(derived)
        else:
            rejected_cross_family.append(derived)

    kept.sort(key=lambda r: (r["family"], -(float(r["volume"]) if r.get("volume") else 0.0), r["event_id"]))
    fields = list(kept[0].keys()) if kept else []
    queue_path = registry / "wave1_event_universe_manual_validation_queue.csv"
    write_csv(queue_path, kept, fields)

    raw_counts = Counter(r["family"] for r in rows)
    kept_counts = Counter(r["family"] for r in kept)
    rejected_counts = Counter(r["family"] for r in rejected_cross_family)
    summary = {
        "artifact": "WAVE1_EVENT_UNIVERSE_MANUAL_VALIDATION_QUEUE",
        "version": VERSION,
        "snapshot_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "performance_blind": True,
        "scientific_reopen": False,
        "query_protocol_unchanged": True,
        "euas_protocol_unchanged": True,
        "method": "query-family consistency filter before manual semantic review",
        "raw_rows": len(rows),
        "queue_rows": len(kept),
        "cross_family_rows_removed": len(rejected_cross_family),
        "raw_counts_by_family": dict(sorted(raw_counts.items())),
        "queue_counts_by_family": dict(sorted(kept_counts.items())),
        "cross_family_removed_by_family": dict(sorted(rejected_counts.items())),
        "manual_validation_required": True,
        "gate_boundary": "Queue counts remain discovery evidence only and cannot satisfy EUAS C/L/S gates.",
        "limitations": [
            "Title-search queries can still return semantically irrelevant events within their own query family (for example DOJ criminal cases in an antitrust query).",
            "M&A query terms can return non-corporate uses of acquire/takeover and require manual review.",
            "Supreme Court/lawsuit queries can return elections, appointments or non-financial cases and require manual review.",
            "Independent-event deduplication and linked-asset mapping are manual-review fields, not inferred here."
        ],
        "queue_csv_sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest(),
    }
    summary_path = registry / "wave1_event_universe_manual_validation_queue_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
QUEUE = REG / "w4c_r1_earnings_ir_queue_v1.csv.gz"
SUMMARY = REG / "w4c_r1_earnings_issuer_profile_summary_v1.json"
DETAIL = REG / "w4c_r1_earnings_issuer_profile_v1.json"

STOP_PREFIX = {"will","the","a","an","does","do","did","is","are","can","could","would","should","what","when","who","which"}
MARKERS = {"earnings","eps","revenue","sales","report","reports","reported","q1","q2","q3","q4","quarter","quarterly","fiscal","fy","beat","beats","miss","misses","above","below","over","under"}
GENERIC = {"inc","corp","corporation","company","co","ltd","limited","plc","holdings","group","class","common","stock"}


def read_gz(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def candidate(subject: str) -> tuple[str, str]:
    toks = [t for t in re.split(r"[^a-z0-9]+", (subject or "").lower()) if t]
    while toks and toks[0] in STOP_PREFIX:
        toks.pop(0)
    cut = next((i for i,t in enumerate(toks) if t in MARKERS), len(toks))
    head = toks[:cut]
    while head and head[-1] in GENERIC:
        head.pop()
    if not head:
        return "", "NO_STABLE_PREFIX"
    if len(head) > 5:
        return "_".join(head[:5]), "LONG_PREFIX_TRUNCATED"
    return "_".join(head), "PREFIX_BEFORE_EARNINGS_MARKER"


def main() -> None:
    rows = read_gz(QUEUE)
    assert len(rows) == 1355
    ids = sorted((r.get("exact_group_id") or "").strip() for r in rows)
    assert len(set(ids)) == 1355
    assert hashlib.sha256(("\n".join(ids)+"\n").encode()).hexdigest() == "c9fd3a13e87ea720e961fa087098130fd20da74c96aa02419aaeebef1e64b05c"

    groups = defaultdict(list)
    modes = Counter()
    blank = 0
    for r in rows:
        key, mode = candidate(r.get("pretruth_subject_key") or "")
        modes[mode] += 1
        if not key:
            blank += 1
            key = "__UNRESOLVED_PREFIX__"
        groups[key].append(r)

    detail_rows = []
    for key, rs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        subjects = sorted({(r.get("pretruth_subject_key") or "").strip() for r in rs})
        dates = sorted((r.get("pretruth_event_reference_date") or "").strip() for r in rs if (r.get("pretruth_event_reference_date") or "").strip())
        detail_rows.append({
            "candidate_issuer_key": key,
            "group_count": len(rs),
            "unique_subject_keys": len(subjects),
            "date_min": dates[0] if dates else "",
            "date_max": dates[-1] if dates else "",
            "sample_subject_keys": subjects[:5],
            "verification_authority": "NONE_DESCRIPTIVE_ONLY"
        })

    DETAIL.write_text(json.dumps({
        "artifact":"W4C_R1_EARNINGS_ISSUER_PROFILE",
        "version":"W4C-R1-EIR-IP-v1.0",
        "science_reopened":False,
        "rows":detail_rows
    }, indent=2, sort_keys=True)+"\n", encoding="utf-8")

    summary = {
        "artifact":"W4C_R1_EARNINGS_ISSUER_PROFILE_SUMMARY",
        "version":"W4C-R1-EIR-IP-SUM-v1.0",
        "status":"DESCRIPTIVE_WORK_ALLOCATION_ONLY",
        "science_reopened":False,
        "queue_groups":1355,
        "candidate_issuer_clusters":len(groups),
        "unresolved_prefix_rows":blank,
        "extraction_mode_counts":dict(sorted(modes.items())),
        "largest_cluster_sizes":[x["group_count"] for x in detail_rows[:20]],
        "top_candidate_issuer_keys":[{"key":x["candidate_issuer_key"],"groups":x["group_count"]} for x in detail_rows[:50]],
        "new_external_source_reads":False,
        "issuer_ir_lookup_performed":False,
        "prediction_market_performance_read":False,
        "linked_asset_realized_returns_read":False,
        "n_final_backtestable_authorized":False,
        "outcome_reveal_authorized":False,
        "gate_decision":"PASS_W4C_R1_EARNINGS_ISSUER_PROFILE_MATERIALIZED_DESCRIPTIVE_ONLY"
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
SRC = REG / "w4c_r1_official_truth_extension_unresolved_v1.csv.gz"
PROTO = REG / "w4c_r1_earnings_ir_fallback_protocol_v1.json"
OUT = REG / "w4c_r1_earnings_ir_queue_v1.csv.gz"
SUMMARY = REG / "w4c_r1_earnings_ir_queue_summary_v1.json"


def read_gz(path: Path) -> tuple[list[dict], list[str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_gz(path: Path, rows: list[dict], fields: list[str]) -> None:
    sio = io.StringIO(newline="")
    writer = csv.DictWriter(sio, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows([{k: r.get(k, "") for k in fields} for r in rows])
    raw = sio.getvalue().encode("utf-8")
    with path.open("wb") as fh:
        with gzip.GzipFile(filename=path.stem, mode="wb", fileobj=fh, mtime=0) as gz:
            gz.write(raw)


def main() -> None:
    proto = json.loads(PROTO.read_text(encoding="utf-8"))
    assert proto["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_PROTOCOL_FROZEN_PRE_SOURCE_LOOKUP"
    assert proto["eligible_universe"]["expected_groups"] == 1355
    assert proto["eligible_universe"]["required_family"] == "EARNINGS_EPS"

    rows, fields = read_gz(SRC)
    selected = []
    for row in rows:
        family = (row.get("resolved_family") or "").strip()
        state = (row.get("r1_verification_state") or row.get("verification_state") or "").strip()
        if family == "EARNINGS_EPS":
            assert state in {"UNRESOLVED_R1_OFFICIAL_TRUTH", "UNRESOLVED_OFFICIAL_TRUTH", ""}
            selected.append(row)

    selected.sort(key=lambda r: (r.get("exact_group_id") or ""))
    ids = [(r.get("exact_group_id") or "").strip() for r in selected]
    assert len(selected) == 1355
    assert len(set(ids)) == 1355
    assert all(ids)
    digest = hashlib.sha256(("\n".join(ids) + "\n").encode("utf-8")).hexdigest()

    years = Counter((r.get("pretruth_event_reference_date") or "")[:4] for r in selected)
    venues = Counter((r.get("venues") or "UNKNOWN").strip() or "UNKNOWN" for r in selected)
    subjects = [(r.get("pretruth_subject_key") or "").strip() for r in selected]

    write_gz(OUT, selected, fields)
    summary = {
        "artifact": "W4C_R1_EARNINGS_IR_QUEUE_SUMMARY",
        "version": "W4C-R1-EIR-Q-v1.0",
        "status": "FROZEN_DESCRIPTIVE_QUEUE_ONLY",
        "science_reopened": False,
        "source_path": str(SRC.relative_to(ROOT)),
        "source_git_blob_sha_expected": "82be733e844e7b2e99ad3c174370fe3fa214b807",
        "family": "EARNINGS_EPS",
        "groups": len(selected),
        "unique_exact_group_ids": len(set(ids)),
        "sorted_group_ids_sha256": digest,
        "serialization": "UTF-8 exact_group_id lexicographically sorted, LF joined, terminal LF",
        "unique_pretruth_subject_keys": len(set(subjects)),
        "year_counts": dict(sorted(years.items())),
        "venue_counts": dict(sorted(venues.items())),
        "new_external_source_reads": False,
        "issuer_ir_lookup_performed": False,
        "sec_lookup_performed": False,
        "prediction_market_performance_read": False,
        "linked_asset_realized_returns_read": False,
        "n_final_backtestable_authorized": False,
        "outcome_reveal_authorized": False,
        "gate_decision": "PASS_W4C_R1_EARNINGS_IR_QUEUE_MATERIALIZED_PRE_SOURCE_LOOKUP"
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

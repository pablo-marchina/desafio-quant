#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
SAMPLE = REG / "w4c_r1_earnings_ir_probe_sample_v1.json"
PROFILE = REG / "w4c_r1_earnings_ticker_profile_v1.json"
QUEUE = REG / "w4c_r1_earnings_ir_queue_v1.csv.gz"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    sample = load_json(SAMPLE)
    profile = load_json(PROFILE)
    sample_ids = {r["exact_group_id"] for r in sample["rows"]}
    profile_map = {
        r["exact_group_id"]: r.get("ticker_candidate", "")
        for r in profile["rows"]
        if r.get("mode") == "UNIQUE_PRE_GAAP_TICKER_CANDIDATE" and r.get("ticker_candidate")
    }
    missing = sorted(sample_ids - profile_map.keys())
    print(json.dumps({"sample_size": len(sample_ids), "profile_hits": len(sample_ids & profile_map.keys()), "missing": missing}, indent=2))
    if not missing:
        return 0

    with gzip.open(QUEUE, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [row for row in reader if row.get("exact_group_id") in set(missing)]

    print(json.dumps({"queue_matches": len(rows), "queue_fields": reader.fieldnames, "rows": rows}, indent=2, sort_keys=True))
    if len(rows) != len(missing):
        raise SystemExit("FAIL_REPAIR_INPUT_QUEUE_COVERAGE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

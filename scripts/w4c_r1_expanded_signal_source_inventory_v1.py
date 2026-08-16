#!/usr/bin/env python3
"""Inventory candidate PIT signal sources for W4-C/R1 expanded economic backtest.

This script intentionally scans schemas and shallow metadata only. It does not read
settlement values, realized returns, price returns, or ARGOS PnL rows. It is a
pre-PnL discovery tool to find where the frozen point-in-time signal map can be
built from.
"""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = [ROOT / "registry", ROOT / "data"]
OUT = ROOT / "registry" / "w4c_r1_expanded_signal_source_inventory_v1.json"

SIGNAL_TERMS = [
    "pit", "prob", "probability", "m2", "logit", "prediction", "market", "signal",
    "observation", "timestamp", "asof", "cutoff", "pre_event", "pretruth", "event",
    "group", "exact_group", "delta", "move", "movement", "velocity", "flow", "hhi",
]
JOIN_TERMS = ["exact_group", "group_id", "event_id", "subject", "pretruth", "ticker", "date", "canonical"]
FORBIDDEN_VALUE_TERMS = [
    "pnl", "profit", "loss", "settlement", "settled", "outcome", "realized",
    "spy", "benchmark", "trade_tape", "economic_backtest", "backtest_quality",
]
FORBIDDEN_FILENAME_TERMS = [
    "trade_tape", "pnl", "settlement", "outcome", "realized",
]


def safe_open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="")
    return open(path, "r", encoding="utf-8", errors="replace", newline="")


def is_forbidden_filename(path: Path) -> bool:
    name = path.name.lower()
    return any(term in name for term in FORBIDDEN_FILENAME_TERMS)


def score_columns(columns: List[str]) -> Tuple[int, List[str], List[str], List[str]]:
    lower_cols = [c.lower() for c in columns]
    signal_cols = [c for c, lc in zip(columns, lower_cols) if any(t in lc for t in SIGNAL_TERMS)]
    join_cols = [c for c, lc in zip(columns, lower_cols) if any(t in lc for t in JOIN_TERMS)]
    forbidden_cols = [c for c, lc in zip(columns, lower_cols) if any(t in lc for t in FORBIDDEN_VALUE_TERMS)]
    score = len(signal_cols) * 3 + len(join_cols) * 2 - len(forbidden_cols) * 4
    return score, signal_cols, join_cols, forbidden_cols


def inspect_csv(path: Path) -> Dict[str, object]:
    with safe_open_text(path) as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            header = []
    score, signal_cols, join_cols, forbidden_cols = score_columns(header)
    status = "CANDIDATE_SCHEMA_ONLY" if score > 0 and signal_cols and join_cols else "LOW_RELEVANCE_SCHEMA"
    if is_forbidden_filename(path):
        status = "EXCLUDED_FORBIDDEN_FILENAME_PRE_PNL"
    return {
        "path": str(path.relative_to(ROOT)),
        "kind": "csv_schema",
        "status": status,
        "column_count": len(header),
        "score": score,
        "signal_like_columns": signal_cols[:80],
        "join_like_columns": join_cols[:80],
        "forbidden_like_columns": forbidden_cols[:80],
        "all_columns_sample": header[:120],
    }


def inspect_json(path: Path) -> Dict[str, object]:
    keys: List[str] = []
    try:
        with safe_open_text(path) as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            keys = list(obj.keys())
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            keys = list(obj[0].keys())
    except Exception as e:
        return {
            "path": str(path.relative_to(ROOT)),
            "kind": "json_schema",
            "status": "UNREADABLE_SCHEMA",
            "error": str(e)[:200],
        }
    score, signal_cols, join_cols, forbidden_cols = score_columns(keys)
    status = "CANDIDATE_SCHEMA_ONLY" if score > 0 and (signal_cols or join_cols) else "LOW_RELEVANCE_SCHEMA"
    if is_forbidden_filename(path):
        status = "EXCLUDED_FORBIDDEN_FILENAME_PRE_PNL"
    return {
        "path": str(path.relative_to(ROOT)),
        "kind": "json_schema",
        "status": status,
        "key_count": len(keys),
        "score": score,
        "signal_like_keys": signal_cols[:80],
        "join_like_keys": join_cols[:80],
        "forbidden_like_keys": forbidden_cols[:80],
        "all_keys_sample": keys[:120],
    }


def main() -> None:
    items: List[Dict[str, object]] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            name = path.name.lower()
            if name.endswith(".csv") or name.endswith(".csv.gz"):
                items.append(inspect_csv(path))
            elif name.endswith(".json"):
                items.append(inspect_json(path))

    candidates = [x for x in items if x.get("status") == "CANDIDATE_SCHEMA_ONLY"]
    candidates_sorted = sorted(candidates, key=lambda x: int(x.get("score", 0)), reverse=True)
    status_counts = Counter(str(x.get("status")) for x in items)

    out = {
        "artifact": "W4C_R1_EXPANDED_SIGNAL_SOURCE_INVENTORY",
        "version": "W4C-R1-EXPANDED-SIGNAL-SOURCE-INVENTORY-v1.1",
        "date": "2026-08-16",
        "status": "MATERIALIZED_SCHEMA_ONLY_NO_OUTCOME_RETURN_SETTLEMENT_VALUES",
        "gate_decision": "PASS_SIGNAL_SOURCE_SCHEMA_INVENTORY_MATERIALIZED_PRE_PNL_WITH_DATA_DIR",
        "scope": "registry + data schema/header scan for frozen PIT signal-map candidates",
        "files_scanned": len(items),
        "status_counts": dict(status_counts),
        "candidate_count": len(candidates_sorted),
        "top_candidates": candidates_sorted[:80],
        "scientific_firewall": {
            "outcome_reveal_authorized": False,
            "earnings_numeric_outcomes_read": False,
            "prediction_market_settlement_read": False,
            "realized_returns_read": False,
            "security_price_return_read": False,
            "benchmark_return_read": False,
            "argos_pnl_read": False,
            "economic_backtest_execution": False,
        },
        "next_gate": "Select frozen PIT signal source(s) from top_candidates and build exact_group_id signal map without settlement/returns/PnL."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({
        "status": out["status"],
        "files_scanned": out["files_scanned"],
        "candidate_count": out["candidate_count"],
        "top_paths": [c["path"] for c in candidates_sorted[:15]],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

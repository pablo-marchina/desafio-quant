#!/usr/bin/env python3
"""Build frozen PIT signal map for W4-C/R1 expanded economic backtest.

Source: data/art028_h2_feature_matrix.csv.gz
Join: exact expanded eligibility rows by ticker + event_date to feature_matrix ticker + company_event_date.

This script reads PIT signal features only. It does not read settlement, earnings outcomes,
realized returns, security prices, benchmark returns, or ARGOS PnL.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
DATA = ROOT / "data"
ELIGIBILITY = REG / "w4c_r1_expanded_economic_backtest_eligibility_manifest_v1.csv.gz"
FEATURES = DATA / "art028_h2_feature_matrix.csv.gz"
SIGNAL_MAP = REG / "w4c_r1_expanded_economic_backtest_signal_map_v1.csv"
SUMMARY = REG / "w4c_r1_expanded_economic_backtest_signal_map_summary_v1.json"

SIGNAL_COLUMNS = [
    "p_cutoff",
    "delta_1h",
    "delta_6h",
    "delta_24h",
    "velocity_6h_per_hour",
    "conditional_z_move_6h",
    "signed_notional_imbalance_24h",
    "wallet_hhi_notional_24h",
    "same_direction_transition_share_lifecycle",
    "jump_score_6h",
    "matrix_profile_discord_6h",
]


def read_csv_any(path: Path) -> List[Dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_ticker(x: str) -> str:
    return (x or "").strip().upper().replace("-", ".")


def norm_date(x: str) -> str:
    return (x or "").strip()[:10]


def main() -> None:
    missing = [str(p.relative_to(ROOT)) for p in [ELIGIBILITY, FEATURES] if not p.exists()]
    if missing:
        raise SystemExit(f"FAIL_MISSING_REQUIRED_FILES {missing}")

    elig_rows = read_csv_any(ELIGIBILITY)
    feat_rows = read_csv_any(FEATURES)

    feature_index: Dict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)
    for r in feat_rows:
        key = (norm_ticker(r.get("ticker", "")), norm_date(r.get("company_event_date", "")))
        if key[0] and key[1]:
            feature_index[key].append(r)

    out_rows: List[Dict[str, str]] = []
    reason_counts = Counter()
    matched_keys = Counter()

    for e in elig_rows:
        gid = e.get("exact_group_id", "").strip()
        ticker = norm_ticker(e.get("ticker", ""))
        event_date = norm_date(e.get("event_date", ""))
        key = (ticker, event_date)
        if not gid:
            reason_counts["NO_EXACT_GROUP_ID"] += 1
            continue
        if not ticker:
            reason_counts["NO_TICKER_ON_ELIGIBILITY"] += 1
            continue
        if not event_date:
            reason_counts["NO_EVENT_DATE_ON_ELIGIBILITY"] += 1
            continue
        candidates = feature_index.get(key, [])
        if not candidates:
            reason_counts["NO_ART028_FEATURE_ROW_FOR_TICKER_DATE"] += 1
            continue
        if len(candidates) > 1:
            reason_counts["AMBIGUOUS_ART028_FEATURE_ROWS_FOR_TICKER_DATE"] += 1
            continue
        f = candidates[0]
        if not f.get("safe_cutoff_utc") or not f.get("p_cutoff"):
            reason_counts["FEATURE_ROW_MISSING_SAFE_CUTOFF_OR_P_CUTOFF"] += 1
            continue
        matched_keys[key] += 1
        row = {
            "exact_group_id": gid,
            "ticker": ticker,
            "event_date": event_date,
            "pit_timestamp": f.get("safe_cutoff_utc", ""),
            "pit_probability": f.get("p_cutoff", ""),
            "m2_probability": f.get("p_cutoff", ""),
            "market_id": f.get("market_id", ""),
            "event_key": f.get("event_key", ""),
            "source_file": "data/art028_h2_feature_matrix.csv.gz",
            "join_key": "ticker+event_date/company_event_date",
            "signal_map_version": "W4C-R1-EXPANDED-SIGNAL-MAP-v1.0",
        }
        for col in SIGNAL_COLUMNS:
            row[col] = f.get(col, "")
        out_rows.append(row)
        reason_counts["PASS_SIGNAL_MAP_JOIN"] += 1

    fieldnames = [
        "exact_group_id", "ticker", "event_date", "pit_timestamp", "pit_probability", "m2_probability",
        "market_id", "event_key", "source_file", "join_key", "signal_map_version",
    ] + SIGNAL_COLUMNS
    with SIGNAL_MAP.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in out_rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})

    summary = {
        "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_SIGNAL_MAP_SUMMARY",
        "version": "W4C-R1-EXPANDED-SIGNAL-MAP-v1.0",
        "date": "2026-08-16",
        "status": "MATERIALIZED_PIT_SIGNAL_MAP_FROM_ART028_FEATURE_MATRIX_FAIL_CLOSED",
        "gate_decision": "PASS_SIGNAL_MAP_MATERIALIZED_NO_OUTCOME_RETURN_SETTLEMENT_PNL_READS",
        "source": {
            "eligibility_manifest": str(ELIGIBILITY.relative_to(ROOT)),
            "feature_matrix": str(FEATURES.relative_to(ROOT)),
            "feature_matrix_sha256": sha256_file(FEATURES),
        },
        "counts": {
            "eligibility_rows": len(elig_rows),
            "feature_rows": len(feat_rows),
            "unique_feature_ticker_date_keys": len(feature_index),
            "signal_map_rows": len(out_rows),
            "unique_signal_ticker_date_keys": len(matched_keys),
        },
        "reason_counts": dict(reason_counts),
        "outputs": {
            "signal_map": str(SIGNAL_MAP.relative_to(ROOT)),
            "signal_map_sha256": sha256_file(SIGNAL_MAP),
        },
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
        "next_gate": "Re-run pre-PnL eligibility with this signal_map present; then decide whether signal coverage is enough for price/return execution or whether additional PIT signal collection is required."
    }
    with SUMMARY.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    print(json.dumps({
        "status": summary["status"],
        "signal_map_rows": len(out_rows),
        "reason_counts": dict(reason_counts),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

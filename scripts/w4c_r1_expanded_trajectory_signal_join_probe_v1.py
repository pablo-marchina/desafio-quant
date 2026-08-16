#!/usr/bin/env python3
"""Probe whether IC04 probability trajectories can expand the W4-C/R1 PIT signal map.

Reads only prediction-market trajectory metadata/probabilities and join keys. Does not read
settlement, earnings outcomes, realized equity returns, benchmark returns, or ARGOS PnL.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
DATA = ROOT / "data"
ELIGIBILITY = REG / "w4c_r1_expanded_economic_backtest_eligibility_manifest_v1.csv.gz"
TRAJECTORY = DATA / "ic04_yes_probability_trajectory.csv.gz"
COMBINED = REG / "w2c_pit_v2_1_combined_events.csv"
OUT = REG / "w4c_r1_expanded_trajectory_signal_join_probe_v1.json"

TICKER_COLS = ["ticker", "linked_asset", "asset", "symbol"]
DATE_COLS = ["company_event_date", "event_date", "semantic_end_utc", "public_revelation_utc", "safe_cutoff_utc"]
TIME_COLS = ["ts", "timestamp", "timestamp_utc", "observed_at", "time", "utc", "datetime"]
PROB_COLS = ["yes_probability", "probability", "p", "price", "value", "yes_price"]
MARKET_COLS = ["market_id", "condition_id", "pm_condition_id", "token_id", "pm_token_id", "event_id"]


def read_csv_any(path: Path) -> List[Dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def norm_ticker(x: str) -> str:
    return (x or "").strip().upper().replace("-", ".")


def norm_date(x: str) -> str:
    return (x or "").strip()[:10]


def pick(row: Dict[str, str], cols: Iterable[str]) -> str:
    lower = {k.lower(): k for k in row.keys()}
    for c in cols:
        k = lower.get(c.lower())
        if k and str(row.get(k, "")).strip():
            return str(row[k]).strip()
    return ""


def contains_cols(header: List[str], needles: Iterable[str]) -> List[str]:
    out = []
    ns = [n.lower() for n in needles]
    for h in header:
        hl = h.lower()
        if any(n in hl for n in ns):
            out.append(h)
    return out


def ticker_date_key(row: Dict[str, str]) -> Tuple[str, str]:
    return norm_ticker(pick(row, TICKER_COLS)), norm_date(pick(row, DATE_COLS))


def condition_tokens(value: str) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in re.split(r"[|,;\s]+", value) if v.strip()]


def main() -> None:
    missing = [str(p.relative_to(ROOT)) for p in [ELIGIBILITY, TRAJECTORY, COMBINED] if not p.exists()]
    if missing:
        raise SystemExit(f"FAIL_MISSING_REQUIRED_FILES {missing}")

    elig = read_csv_any(ELIGIBILITY)
    combined = read_csv_any(COMBINED)

    # Stream trajectory: keep schema/counts/key counts, not full raw values.
    with gzip.open(TRAJECTORY, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        traj_header = reader.fieldnames or []
        traj_rows = 0
        traj_market_values = Counter()
        traj_market_cols = contains_cols(traj_header, MARKET_COLS)
        traj_time_cols = contains_cols(traj_header, TIME_COLS)
        traj_prob_cols = contains_cols(traj_header, PROB_COLS)
        traj_ticker_cols = contains_cols(traj_header, TICKER_COLS)
        traj_date_cols = contains_cols(traj_header, DATE_COLS)
        first_nonempty_examples = {}
        for row in reader:
            traj_rows += 1
            if traj_rows <= 20000:
                for c in traj_market_cols:
                    v = row.get(c, "").strip()
                    if v:
                        traj_market_values[v] += 1
                for c in traj_header:
                    if c not in first_nonempty_examples and row.get(c, "").strip():
                        # Store redacted/truncated metadata sample only.
                        first_nonempty_examples[c] = row[c].strip()[:80]

    elig_ticker_date = Counter((norm_ticker(r.get("ticker", "")), norm_date(r.get("event_date", ""))) for r in elig if r.get("ticker") and r.get("event_date"))
    combined_ticker_date = Counter(ticker_date_key(r) for r in combined if ticker_date_key(r)[0] and ticker_date_key(r)[1])

    # Build combined condition/token to ticker-date map.
    cond_to_ticker_date = defaultdict(set)
    for r in combined:
        key = ticker_date_key(r)
        if not key[0] or not key[1]:
            continue
        for c in ["pm_condition_ids", "pm_token_ids", "condition_id", "token_id", "event_id"]:
            for tok in condition_tokens(r.get(c, "")):
                cond_to_ticker_date[tok].add(key)

    trajectory_condition_matches = 0
    trajectory_condition_ambiguous = 0
    trajectory_ticker_date_matches = 0
    matched_ticker_dates = set()
    for mv in traj_market_values.keys():
        keys = cond_to_ticker_date.get(mv, set())
        if len(keys) == 1:
            key = next(iter(keys))
            if key in elig_ticker_date:
                trajectory_condition_matches += 1
                matched_ticker_dates.add(key)
        elif len(keys) > 1:
            trajectory_condition_ambiguous += 1

    # Direct ticker/date matching only if trajectory has such columns; count not possible without second full pass storing per-row keys.
    direct_possible = bool(traj_ticker_cols and traj_date_cols)

    out = {
        "artifact": "W4C_R1_EXPANDED_TRAJECTORY_SIGNAL_JOIN_PROBE",
        "version": "W4C-R1-EXPANDED-TRAJECTORY-SIGNAL-JOIN-PROBE-v1.0",
        "date": "2026-08-16",
        "status": "MATERIALIZED_PRE_PNL_TRAJECTORY_JOIN_PROBE",
        "gate_decision": "PASS_TRAJECTORY_JOIN_PROBE_NO_OUTCOME_RETURN_SETTLEMENT_PNL_READS",
        "inputs": {
            "eligibility_manifest": str(ELIGIBILITY.relative_to(ROOT)),
            "trajectory": str(TRAJECTORY.relative_to(ROOT)),
            "combined_events": str(COMBINED.relative_to(ROOT))
        },
        "schemas": {
            "trajectory_columns": traj_header,
            "trajectory_market_like_columns": traj_market_cols,
            "trajectory_time_like_columns": traj_time_cols,
            "trajectory_probability_like_columns": traj_prob_cols,
            "trajectory_ticker_like_columns": traj_ticker_cols,
            "trajectory_date_like_columns": traj_date_cols,
            "combined_columns": list(combined[0].keys()) if combined else [],
            "eligibility_columns": list(elig[0].keys()) if elig else []
        },
        "counts": {
            "eligibility_rows": len(elig),
            "eligibility_unique_ticker_dates": len(elig_ticker_date),
            "combined_rows": len(combined),
            "combined_unique_ticker_dates": len(combined_ticker_date),
            "trajectory_rows": traj_rows,
            "trajectory_unique_market_values_sampled_first_20000": len(traj_market_values),
            "trajectory_condition_values_matching_unique_combined_ticker_date": trajectory_condition_matches,
            "trajectory_condition_values_matching_ambiguous_combined_ticker_date": trajectory_condition_ambiguous,
            "trajectory_unique_eligibility_ticker_dates_matched_by_condition": len(matched_ticker_dates),
            "direct_ticker_date_join_possible_from_trajectory_schema": direct_possible
        },
        "first_nonempty_examples_truncated": first_nonempty_examples,
        "scientific_firewall": {
            "outcome_reveal_authorized": False,
            "earnings_numeric_outcomes_read": False,
            "prediction_market_settlement_read": False,
            "realized_returns_read": False,
            "security_price_return_read": False,
            "benchmark_return_read": False,
            "argos_pnl_read": False,
            "economic_backtest_execution": False
        },
        "next_gate": "If trajectory condition/token keys match enough eligibility ticker-dates, build an expanded PIT signal map using the latest pre-cutoff probability per exact_group_id. Otherwise report signal-coverage limitation and avoid running a small-N PnL as expanded."
    }
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"status": out["status"], "counts": out["counts"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

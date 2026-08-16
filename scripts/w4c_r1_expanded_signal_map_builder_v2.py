#!/usr/bin/env python3
"""Build expanded PIT signal map v2 from IC04 YES probability trajectories.

Join: eligibility exact_group_id by ticker + event_date to trajectory ticker + company_event_date.
Signal: latest YES-token price observed at or before safe_cutoff_utc.

No settlement, earnings outcomes, realized equity returns, benchmark returns, or ARGOS PnL are read.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
DATA = ROOT / "data"
ELIGIBILITY = REG / "w4c_r1_expanded_economic_backtest_eligibility_manifest_v1.csv.gz"
TRAJECTORY = DATA / "ic04_yes_probability_trajectory.csv.gz"
SIGNAL_MAP = REG / "w4c_r1_expanded_economic_backtest_signal_map_v2.csv"
SUMMARY = REG / "w4c_r1_expanded_economic_backtest_signal_map_summary_v2.json"


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


def parse_utc(x: str) -> Optional[datetime]:
    if not x:
        return None
    s = x.strip()
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def to_float(x: str) -> Optional[float]:
    try:
        return float(str(x).strip())
    except Exception:
        return None


def main() -> None:
    missing = [str(p.relative_to(ROOT)) for p in [ELIGIBILITY, TRAJECTORY] if not p.exists()]
    if missing:
        raise SystemExit(f"FAIL_MISSING_REQUIRED_FILES {missing}")

    elig = read_csv_any(ELIGIBILITY)
    elig_by_key: Dict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)
    for e in elig:
        ticker = norm_ticker(e.get("ticker", ""))
        event_date = norm_date(e.get("event_date", ""))
        if ticker and event_date:
            elig_by_key[(ticker, event_date)].append(e)

    # Latest pre-cutoff YES price by ticker/date, fail-closed on ambiguous market IDs.
    latest_by_key: Dict[Tuple[str, str], Dict[str, str]] = {}
    market_ids_by_key: Dict[Tuple[str, str], set] = defaultdict(set)
    trajectory_rows = 0
    candidate_rows = 0
    skipped_after_cutoff = 0
    skipped_non_yes = 0
    skipped_bad_price_or_time = 0

    with gzip.open(TRAJECTORY, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            trajectory_rows += 1
            if str(r.get("token_label", "")).strip().upper() != "YES":
                skipped_non_yes += 1
                continue
            ticker = norm_ticker(r.get("ticker", ""))
            event_date = norm_date(r.get("company_event_date", ""))
            key = (ticker, event_date)
            if key not in elig_by_key:
                continue
            cutoff = parse_utc(r.get("safe_cutoff_utc", ""))
            ts = parse_utc(r.get("timestamp_utc", ""))
            price = to_float(r.get("price", ""))
            if cutoff is None or ts is None or price is None:
                skipped_bad_price_or_time += 1
                continue
            if ts > cutoff:
                skipped_after_cutoff += 1
                continue
            candidate_rows += 1
            market_ids_by_key[key].add(str(r.get("market_id", "")).strip())
            prev = latest_by_key.get(key)
            if prev is None or parse_utc(prev["pit_timestamp"]) < ts:
                latest_by_key[key] = {
                    "ticker": ticker,
                    "event_date": event_date,
                    "pit_timestamp": ts.isoformat().replace("+00:00", "Z"),
                    "safe_cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
                    "pit_probability": str(price),
                    "m2_probability": str(price),
                    "market_id": str(r.get("market_id", "")).strip(),
                    "event_key": str(r.get("event_key", "")).strip(),
                    "token_id": str(r.get("token_id", "")).strip(),
                    "source_file": "data/ic04_yes_probability_trajectory.csv.gz",
                    "join_key": "ticker+event_date/company_event_date;latest_yes_price_at_or_before_safe_cutoff",
                    "signal_map_version": "W4C-R1-EXPANDED-SIGNAL-MAP-v2.0",
                }

    out_rows: List[Dict[str, str]] = []
    reason_counts = Counter()
    ambiguous_keys = set()
    for key, mids in market_ids_by_key.items():
        mids_clean = {m for m in mids if m}
        if len(mids_clean) > 1:
            ambiguous_keys.add(key)

    for e in elig:
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
        if key in ambiguous_keys:
            reason_counts["AMBIGUOUS_MULTIPLE_MARKET_IDS_FOR_TICKER_DATE"] += 1
            continue
        sig = latest_by_key.get(key)
        if not sig:
            reason_counts["NO_PRE_CUTOFF_TRAJECTORY_SIGNAL_FOR_TICKER_DATE"] += 1
            continue
        row = {"exact_group_id": gid}
        row.update(sig)
        out_rows.append(row)
        reason_counts["PASS_SIGNAL_MAP_JOIN"] += 1

    fieldnames = [
        "exact_group_id", "ticker", "event_date", "pit_timestamp", "safe_cutoff_utc", "pit_probability",
        "m2_probability", "market_id", "event_key", "token_id", "source_file", "join_key", "signal_map_version",
    ]
    with SIGNAL_MAP.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in out_rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})

    summary = {
        "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_SIGNAL_MAP_SUMMARY",
        "version": "W4C-R1-EXPANDED-SIGNAL-MAP-v2.0",
        "date": "2026-08-16",
        "status": "MATERIALIZED_EXPANDED_PIT_SIGNAL_MAP_FROM_TRAJECTORY_FAIL_CLOSED",
        "gate_decision": "PASS_EXPANDED_SIGNAL_MAP_V2_MATERIALIZED_NO_OUTCOME_RETURN_SETTLEMENT_PNL_READS",
        "source": {
            "eligibility_manifest": str(ELIGIBILITY.relative_to(ROOT)),
            "trajectory": str(TRAJECTORY.relative_to(ROOT)),
            "trajectory_sha256": sha256_file(TRAJECTORY),
        },
        "counts": {
            "eligibility_rows": len(elig),
            "eligibility_unique_ticker_dates": len(elig_by_key),
            "trajectory_rows": trajectory_rows,
            "trajectory_candidate_pre_cutoff_yes_rows": candidate_rows,
            "latest_signal_ticker_dates": len(latest_by_key),
            "ambiguous_ticker_date_keys": len(ambiguous_keys),
            "signal_map_rows": len(out_rows),
            "skipped_non_yes_rows": skipped_non_yes,
            "skipped_after_cutoff_rows": skipped_after_cutoff,
            "skipped_bad_price_or_time_rows": skipped_bad_price_or_time,
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
        "next_gate": "Use this signal map as the frozen PIT signal source in eligibility; then decide whether price/return execution is justified by N_final_backtestable_candidate_pre_price."
    }
    with SUMMARY.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"status": summary["status"], "counts": summary["counts"], "reason_counts": dict(reason_counts)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

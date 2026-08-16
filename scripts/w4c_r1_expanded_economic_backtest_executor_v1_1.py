#!/usr/bin/env python3
"""W4-C/R1 expanded economic backtest executor v1.1.

Adds a deterministic overlay from the frozen EARNINGS_EPS queue to recover
pretruth dates/subjects before any outcome, settlement, return or PnL read.
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import sys
sys.path.append(str(Path(__file__).resolve().parent))
import w4c_r1_expanded_economic_backtest_executor_v1 as base  # noqa: E402

QUEUE = base.REG / "w4c_r1_earnings_ir_queue_v1.csv.gz"


def pick_contains(row: Dict[str, str], must_any: Iterable[str]) -> str:
    needles = [x.lower() for x in must_any]
    for k, v in row.items():
        lk = k.lower()
        if any(n in lk for n in needles) and str(v).strip():
            return str(v).strip()
    return ""


def parse_date_any(row: Dict[str, str]) -> Tuple[str, str, str]:
    raw = base.pick(row, base.DATE_FIELDS)
    src = "exact_date_field" if raw else ""
    if not raw:
        raw = pick_contains(row, ["reference_date", "event_reference", "event_date", "pretruth_event", "date"])
        src = "fuzzy_date_field" if raw else ""
    parsed = base.parse_date(raw)
    return parsed, raw, src


def pick_subject_any(row: Dict[str, str]) -> Tuple[str, str]:
    val = base.pick(row, base.SUBJECT_FIELDS)
    if val:
        return val, "exact_subject_field"
    val = pick_contains(row, ["subject", "title", "question", "market"])
    return val, "fuzzy_subject_field" if val else ""


def pick_group_any(row: Dict[str, str], idx: int) -> Tuple[str, str]:
    val = base.pick(row, base.GROUP_FIELDS)
    if val:
        return val, "exact_group_field"
    val = pick_contains(row, ["exact_group", "group_id"])
    if val:
        return val, "fuzzy_group_field"
    return f"ROW_{idx:05d}", "row_number_fallback"


def pick_family_any(row: Dict[str, str]) -> Tuple[str, str]:
    val = base.pick(row, base.FAMILY_FIELDS)
    if val:
        return val, "exact_family_field"
    val = pick_contains(row, ["family"])
    if val:
        return val, "fuzzy_family_field"
    return "EARNINGS_EPS", "default_from_protocol"


def overlay_resolution_queue(res_row: Dict[str, str], queue_row: Dict[str, str]) -> Dict[str, str]:
    # Resolution is authoritative for discovered fields; queue is authoritative for pretruth date/subject context.
    merged = dict(queue_row)
    merged.update({k: v for k, v in res_row.items() if str(v).strip()})
    return merged


def validate_v1_1() -> dict:
    v = base.validate()
    if not QUEUE.exists():
        raise SystemExit("FAIL_MISSING_QUEUE_FILE")
    q = base.read_csv_any(QUEUE)
    r = base.read_csv_any(base.RESOLUTION)
    if len(q) != 1355:
        raise SystemExit(f"FAIL_QUEUE_ROW_COUNT rows={len(q)}")
    v.update({
        "status": "PASS_VALIDATE_ONLY_V1_1_QUEUE_OVERLAY",
        "queue_rows": len(q),
        "resolution_rows": len(r),
        "queue_columns_sample": list(q[0].keys())[:40] if q else [],
        "resolution_columns_sample": list(r[0].keys())[:40] if r else [],
        "economic_reads_performed": False,
    })
    return v


def materialize_eligibility_v1_1() -> dict:
    validation = validate_v1_1()
    res_rows = base.read_csv_any(base.RESOLUTION)
    queue_rows = base.read_csv_any(QUEUE)
    signal_map = base.load_signal_map()
    out_rows: List[Dict[str, object]] = []
    reason_counts = Counter()
    ticker_counts = Counter()
    date_values: List[str] = []
    seen = Counter()

    for i, res in enumerate(res_rows, start=1):
        q = queue_rows[i - 1] if i - 1 < len(queue_rows) else {}
        row = overlay_resolution_queue(res, q)
        gid, gid_source = pick_group_any(row, i)
        seen[gid] += 1
        family, family_source = pick_family_any(row)
        event_date, raw_date, date_source = parse_date_any(row)
        subject, subject_source = pick_subject_any(row)
        ticker, ticker_source = base.extract_ticker(row, subject)
        pit_ready, pit_value, pit_timestamp = base.detect_pit_signal(row)

        if gid in signal_map:
            sm = signal_map[gid]
            pit_value = pit_value or base.pick(sm, base.PIT_FIELDS)
            pit_timestamp = pit_timestamp or base.pick(sm, base.PIT_TIME_FIELDS)
            pit_ready = bool(pit_value and pit_timestamp)

        reasons: List[str] = []
        if family and family != "EARNINGS_EPS":
            reasons.append("FAMILY_NOT_EARNINGS_EPS")
        if not event_date:
            reasons.append("NO_DETERMINISTIC_EVENT_DATE")
        if not ticker:
            reasons.append("NO_DETERMINISTIC_TICKER")
        if seen[gid] > 1:
            reasons.append("DUPLICATE_OR_AMBIGUOUS_JOIN_KEY")
        if not pit_ready:
            reasons.append("NO_PIT_SIGNAL_BEFORE_CUTOFF")

        if reasons:
            stage = "INELIGIBLE_PRE_PNL"
            primary_reason = reasons[0]
        else:
            stage = "ELIGIBLE_PRE_PRICE_AND_PNL"
            primary_reason = "PASS_PRE_PRICE_ELIGIBILITY"
            date_values.append(event_date)
            ticker_counts[ticker] += 1

        for rr in reasons or ["PASS_PRE_PRICE_ELIGIBILITY"]:
            reason_counts[rr] += 1

        out_rows.append({
            "exact_group_id": gid,
            "row_number": i,
            "group_id_source": gid_source,
            "family": family,
            "family_source": family_source,
            "event_date": event_date,
            "raw_event_date": raw_date,
            "date_source": date_source,
            "ticker": ticker,
            "ticker_source": ticker_source,
            "subject_source": subject_source,
            "pit_signal_ready": str(bool(pit_ready)).lower(),
            "pit_signal_value_present": str(bool(pit_value)).lower(),
            "pit_timestamp_present": str(bool(pit_timestamp)).lower(),
            "eligibility_stage": stage,
            "primary_failure_reason": primary_reason,
            "all_failure_reasons": ";".join(reasons),
        })

    fieldnames = [
        "exact_group_id", "row_number", "group_id_source", "family", "family_source", "event_date",
        "raw_event_date", "date_source", "ticker", "ticker_source", "subject_source",
        "pit_signal_ready", "pit_signal_value_present", "pit_timestamp_present", "eligibility_stage",
        "primary_failure_reason", "all_failure_reasons",
    ]
    base.write_csv_gz(base.ELIGIBILITY_CSV, out_rows, fieldnames)
    eligible = [r for r in out_rows if r["eligibility_stage"] == "ELIGIBLE_PRE_PRICE_AND_PNL"]
    ticker_candidate = [r for r in out_rows if r["ticker"]]
    dated = [r for r in out_rows if r["event_date"]]
    dated_all = [str(r["event_date"]) for r in dated]

    summary = {
        "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_ELIGIBILITY_SUMMARY",
        "version": "W4C-R1-EXPANDED-ECON-BACKTEST-ELIGIBILITY-v1.1",
        "date": "2026-08-16",
        "status": "MATERIALIZED_PRE_PNL_ELIGIBILITY_WITH_QUEUE_OVERLAY_FAIL_CLOSED",
        "gate_decision": "PASS_ELIGIBILITY_MATERIALIZED_QUEUE_OVERLAY_NO_OUTCOME_RETURN_SETTLEMENT_READS",
        "validation": validation,
        "base_rows": len(out_rows),
        "queue_rows": len(queue_rows),
        "resolution_rows": len(res_rows),
        "ticker_candidate_rows": len(ticker_candidate),
        "dated_rows": len(dated),
        "date_min_all_dated": min(dated_all) if dated_all else None,
        "date_max_all_dated": max(dated_all) if dated_all else None,
        "signal_map_present": base.SIGNAL_MAP.exists(),
        "signal_map_rows": len(signal_map),
        "n_final_backtestable_candidate_pre_price": len(eligible),
        "date_min_eligible": min(date_values) if date_values else None,
        "date_max_eligible": max(date_values) if date_values else None,
        "unique_tickers_eligible": len(ticker_counts),
        "top_tickers_eligible": ticker_counts.most_common(25),
        "failure_reason_counts": dict(reason_counts),
        "outputs": {
            "eligibility_manifest": str(base.ELIGIBILITY_CSV.relative_to(base.ROOT)),
            "eligibility_manifest_sha256": base.sha256_file(base.ELIGIBILITY_CSV),
        },
        "scientific_firewall": {
            "outcome_reveal_authorized": False,
            "event_truth_verification_used": False,
            "earnings_numeric_outcomes_read": False,
            "prediction_market_settlement_read": False,
            "realized_returns_read": False,
            "argos_pnl_read": False,
            "backtest_execution_authorized": False,
        },
        "next_gate": "Materialize a frozen PIT signal map keyed by exact_group_id before any return/PnL execution; do not invent thresholds or use settlements/returns to choose signals.",
    }
    base.write_json(base.ELIGIBILITY_SUMMARY, summary)
    return summary


def main() -> None:
    if os.getenv("W4C_R1_EXPANDED_ECON_BACKTEST_VALIDATE_ONLY") == "YES":
        print(json.dumps(validate_v1_1(), indent=2, sort_keys=True))
        return
    if os.getenv("W4C_R1_EXPANDED_ECON_BACKTEST_MATERIALIZE_ELIGIBILITY") == "YES_FROZEN":
        print(json.dumps(materialize_eligibility_v1_1(), indent=2, sort_keys=True))
        return
    if os.getenv("W4C_R1_EXPANDED_ECON_BACKTEST_EXECUTE") == "YES_FROZEN_EXPANDED_ECON":
        print(json.dumps(base.execute_economic_backtest(), indent=2, sort_keys=True))
        return
    raise SystemExit("Set VALIDATE_ONLY, MATERIALIZE_ELIGIBILITY, or EXECUTE mode")


if __name__ == "__main__":
    main()

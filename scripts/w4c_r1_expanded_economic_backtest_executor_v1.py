#!/usr/bin/env python3
"""W4-C/R1 expanded economic backtest executor v1.

Frozen behavior:
- validate protocol + full expansion freeze without outcome/return/settlement reads;
- materialize deterministic eligibility from the frozen full 1,355 EARNINGS_EPS expansion;
- execute economic backtest only under a separate execution authorization and only if
  a frozen signal map exists. The script fails closed rather than inventing thresholds.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"

PROTOCOL = REG / "w4c_r1_expanded_economic_backtest_protocol_freeze_v1.json"
FULL_FREEZE = REG / "w4c_r1_earnings_ir_official_domain_full_expansion_result_freeze_v1.json"
RESOLUTION = REG / "w4c_r1_earnings_ir_official_domain_full_resolution_manifest_v1.csv.gz"
NAVIGATION = REG / "w4c_r1_earnings_ir_official_domain_full_navigation_manifest_v1.csv.gz"
BODY = REG / "w4c_r1_earnings_ir_official_domain_full_body_manifest_v1.csv.gz"
SUMMARY = REG / "w4c_r1_earnings_ir_official_domain_full_expansion_summary_v1.json"
EXEC_MANIFEST = REG / "w4c_r1_earnings_ir_official_domain_full_execution_manifest_v1.json"

SIGNAL_MAP = REG / "w4c_r1_expanded_economic_backtest_signal_map_v1.csv"
EXEC_AUTH = REG / "w4c_r1_expanded_economic_backtest_execute_authorization_v1.json"

ELIGIBILITY_CSV = REG / "w4c_r1_expanded_economic_backtest_eligibility_manifest_v1.csv.gz"
ELIGIBILITY_SUMMARY = REG / "w4c_r1_expanded_economic_backtest_eligibility_summary_v1.json"
RESULT_GUARD = REG / "w4c_r1_expanded_economic_backtest_execution_guard_v1.json"

GROUP_FIELDS = ["exact_group_id", "group_id", "id", "event_id"]
FAMILY_FIELDS = ["resolved_family", "family", "event_family"]
DATE_FIELDS = ["pretruth_event_reference_date", "event_reference_date", "event_date", "date", "reference_date"]
SUBJECT_FIELDS = ["pretruth_subject_key", "subject_key", "title", "event_title", "market_title", "question"]
TICKER_FIELDS = [
    "ticker",
    "ticker_symbol",
    "resolved_ticker",
    "candidate_ticker",
    "wikidata_ticker",
    "issuer_ticker",
    "primary_ticker",
    "symbol",
]
PIT_FIELDS = [
    "pit_probability",
    "m2_probability",
    "m2_prob",
    "probability_pit",
    "pre_event_probability",
    "market_probability",
]
PIT_TIME_FIELDS = ["pit_timestamp", "observation_utc", "signal_timestamp", "timestamp_utc", "asof_utc"]
COMMON_NON_TICKERS = {
    "gaap", "nongaap", "up", "down", "or", "and", "the", "inc", "corp", "holdings", "group",
    "company", "technologies", "technology", "financial", "earnings", "estimate", "cash", "times",
}


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def read_csv_any(path: Path) -> List[Dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv_gz(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pick(row: Dict[str, str], fields: Iterable[str]) -> str:
    lower = {k.lower(): k for k in row.keys()}
    for f in fields:
        k = lower.get(f.lower())
        if k and str(row.get(k, "")).strip():
            return str(row[k]).strip()
    return ""


def parse_date(value: str) -> str:
    if not value:
        return ""
    m = re.search(r"(20\d{2}|19\d{2})[-/](\d{1,2})[-/](\d{1,2})", value)
    if not m:
        return ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return ""


def clean_ticker(value: str) -> str:
    if not value:
        return ""
    value = value.strip().upper().replace("$", "")
    m = re.search(r"\b[A-Z][A-Z0-9.\-]{0,5}\b", value)
    if not m:
        return ""
    t = m.group(0).replace("-", ".")
    if t.lower() in COMMON_NON_TICKERS:
        return ""
    return t


def ticker_from_subject(subject: str) -> Tuple[str, str]:
    if not subject:
        return "", ""
    tokens = [t for t in re.split(r"[^A-Za-z0-9]+", subject.lower()) if t]
    for marker in ("gaap", "nongaap"):
        if marker in tokens:
            i = tokens.index(marker)
            if i > 0:
                t = clean_ticker(tokens[i - 1])
                if t:
                    return t, f"subject_token_before_{marker}"
    if "up" in tokens and "down" in tokens:
        # common market pattern: company ticker up or down / up_or_down ticker
        for i, tok in enumerate(tokens):
            if tok == "down" and i + 1 < len(tokens):
                t = clean_ticker(tokens[i + 1])
                if t:
                    return t, "subject_token_after_down"
    for tok in tokens:
        if 1 <= len(tok) <= 5 and tok not in COMMON_NON_TICKERS and not any(ch.isdigit() for ch in tok):
            # conservative fallback: only after explicit fields failed; label as heuristic.
            if tok not in {"will", "beat", "miss", "eps", "qtr", "year", "next"}:
                return clean_ticker(tok), "subject_first_short_token_heuristic"
    return "", ""


def extract_ticker(row: Dict[str, str], subject: str) -> Tuple[str, str]:
    direct = pick(row, TICKER_FIELDS)
    t = clean_ticker(direct)
    if t:
        return t, "explicit_ticker_field"
    return ticker_from_subject(subject)


def detect_pit_signal(row: Dict[str, str]) -> Tuple[bool, str, str]:
    val = pick(row, PIT_FIELDS)
    ts = pick(row, PIT_TIME_FIELDS)
    if val and ts:
        return True, val, ts
    if val:
        return False, val, ""
    return False, "", ""


def load_signal_map() -> Dict[str, Dict[str, str]]:
    if not SIGNAL_MAP.exists():
        return {}
    rows = read_csv_any(SIGNAL_MAP)
    out = {}
    for r in rows:
        gid = pick(r, GROUP_FIELDS)
        if gid:
            out[gid] = r
    return out


def validate() -> dict:
    required = [PROTOCOL, FULL_FREEZE, RESOLUTION, NAVIGATION, BODY, SUMMARY, EXEC_MANIFEST]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"FAIL_MISSING_REQUIRED_FILES {missing}")
    protocol = read_json(PROTOCOL)
    full_freeze = read_json(FULL_FREEZE)
    full_summary = read_json(SUMMARY)
    exec_manifest = read_json(EXEC_MANIFEST)
    if protocol.get("scientific_firewall_at_protocol_freeze", {}).get("backtest_execution_authorized") is not False:
        raise SystemExit("FAIL_PROTOCOL_FIREWALL_BACKTEST_EXECUTION_NOT_FALSE")
    if full_freeze.get("status") != "FROZEN_AUTHORITATIVE":
        raise SystemExit("FAIL_FULL_EXPANSION_NOT_AUTHORITATIVE")
    if full_summary.get("input_queue_groups") != 1355:
        raise SystemExit("FAIL_UNEXPECTED_FULL_UNIVERSE_SIZE")
    if any(exec_manifest.get("scientific_firewall", {}).get(k) for k in [
        "argos_pnl_read", "earnings_numeric_outcomes_read", "prediction_market_settlement_read", "realized_returns_read"
    ]):
        raise SystemExit("FAIL_FULL_EXPANSION_FIREWALL_VIOLATION")
    rows = read_csv_any(RESOLUTION)
    if len(rows) != 1355:
        raise SystemExit(f"FAIL_RESOLUTION_ROW_COUNT rows={len(rows)}")
    return {
        "status": "PASS_VALIDATE_ONLY",
        "rows": len(rows),
        "protocol_version": protocol.get("version"),
        "full_freeze_gate": full_freeze.get("gate_decision"),
        "external_requests_performed_in_full_expansion": exec_manifest.get("external_requests_performed"),
        "economic_reads_performed": False,
    }


def materialize_eligibility() -> dict:
    validation = validate()
    rows = read_csv_any(RESOLUTION)
    signal_map = load_signal_map()
    out_rows: List[Dict[str, object]] = []
    reason_counts = Counter()
    ticker_counts = Counter()
    date_values: List[str] = []
    seen = Counter()

    for i, row in enumerate(rows, start=1):
        gid = pick(row, GROUP_FIELDS) or f"ROW_{i:05d}"
        seen[gid] += 1
        family = pick(row, FAMILY_FIELDS) or "EARNINGS_EPS"
        raw_date = pick(row, DATE_FIELDS)
        event_date = parse_date(raw_date)
        subject = pick(row, SUBJECT_FIELDS)
        ticker, ticker_source = extract_ticker(row, subject)
        pit_ready, pit_value, pit_timestamp = detect_pit_signal(row)

        if gid in signal_map:
            sm = signal_map[gid]
            pit_value = pit_value or pick(sm, PIT_FIELDS)
            pit_timestamp = pit_timestamp or pick(sm, PIT_TIME_FIELDS)
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

        for r in reasons or ["PASS_PRE_PRICE_ELIGIBILITY"]:
            reason_counts[r] += 1

        out_rows.append({
            "exact_group_id": gid,
            "row_number": i,
            "family": family,
            "event_date": event_date,
            "raw_event_date": raw_date,
            "ticker": ticker,
            "ticker_source": ticker_source,
            "pit_signal_ready": str(bool(pit_ready)).lower(),
            "pit_signal_value_present": str(bool(pit_value)).lower(),
            "pit_timestamp_present": str(bool(pit_timestamp)).lower(),
            "eligibility_stage": stage,
            "primary_failure_reason": primary_reason,
            "all_failure_reasons": ";".join(reasons),
        })

    fieldnames = [
        "exact_group_id", "row_number", "family", "event_date", "raw_event_date", "ticker", "ticker_source",
        "pit_signal_ready", "pit_signal_value_present", "pit_timestamp_present", "eligibility_stage",
        "primary_failure_reason", "all_failure_reasons",
    ]
    write_csv_gz(ELIGIBILITY_CSV, out_rows, fieldnames)

    eligible = [r for r in out_rows if r["eligibility_stage"] == "ELIGIBLE_PRE_PRICE_AND_PNL"]
    ticker_candidate = [r for r in out_rows if r["ticker"]]
    dated = [r for r in out_rows if r["event_date"]]
    summary = {
        "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_ELIGIBILITY_SUMMARY",
        "version": "W4C-R1-EXPANDED-ECON-BACKTEST-ELIGIBILITY-v1.0",
        "date": "2026-08-16",
        "status": "MATERIALIZED_PRE_PNL_ELIGIBILITY_FAIL_CLOSED",
        "gate_decision": "PASS_ELIGIBILITY_MATERIALIZED_NO_OUTCOME_RETURN_SETTLEMENT_READS",
        "validation": validation,
        "base_rows": len(out_rows),
        "ticker_candidate_rows": len(ticker_candidate),
        "dated_rows": len(dated),
        "signal_map_present": SIGNAL_MAP.exists(),
        "signal_map_rows": len(signal_map),
        "n_final_backtestable_candidate_pre_price": len(eligible),
        "date_min_eligible": min(date_values) if date_values else None,
        "date_max_eligible": max(date_values) if date_values else None,
        "unique_tickers_eligible": len(ticker_counts),
        "top_tickers_eligible": ticker_counts.most_common(25),
        "failure_reason_counts": dict(reason_counts),
        "outputs": {
            "eligibility_manifest": str(ELIGIBILITY_CSV.relative_to(ROOT)),
            "eligibility_manifest_sha256": sha256_file(ELIGIBILITY_CSV),
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
        "next_gate": "If n_final_backtestable_candidate_pre_price is nonzero, freeze/authorize price and benchmark execution. If zero, first materialize a frozen PIT signal map rather than inventing a rule.",
    }
    write_json(ELIGIBILITY_SUMMARY, summary)
    return summary


def execute_economic_backtest() -> dict:
    if not EXEC_AUTH.exists():
        guard = {
            "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_EXECUTION_GUARD",
            "status": "FAIL_CLOSED_NO_EXECUTION_AUTHORIZATION",
            "reason": "registry/w4c_r1_expanded_economic_backtest_execute_authorization_v1.json is required before reading returns or computing PnL",
            "economic_reads_performed": False,
        }
        write_json(RESULT_GUARD, guard)
        return guard
    auth = read_json(EXEC_AUTH)
    if auth.get("backtest_execution_authorized") is not True:
        guard = {
            "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_EXECUTION_GUARD",
            "status": "FAIL_CLOSED_BACKTEST_NOT_AUTHORIZED",
            "economic_reads_performed": False,
        }
        write_json(RESULT_GUARD, guard)
        return guard
    if not SIGNAL_MAP.exists():
        guard = {
            "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_EXECUTION_GUARD",
            "status": "FAIL_CLOSED_NO_FROZEN_SIGNAL_MAP",
            "reason": "A frozen PIT signal map is required before any return or PnL calculation; thresholds/directions are not invented by this executor.",
            "economic_reads_performed": False,
        }
        write_json(RESULT_GUARD, guard)
        return guard
    guard = {
        "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_EXECUTION_GUARD",
        "status": "EXECUTION_NOT_IMPLEMENTED_BEYOND_PRE_PNL_GUARD_IN_V1",
        "reason": "v1 freezes validation and eligibility behavior. Price-return execution requires a follow-up executor version bound to the frozen signal map schema.",
        "economic_reads_performed": False,
    }
    write_json(RESULT_GUARD, guard)
    return guard


def main() -> None:
    if os.getenv("W4C_R1_EXPANDED_ECON_BACKTEST_VALIDATE_ONLY") == "YES":
        result = validate()
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if os.getenv("W4C_R1_EXPANDED_ECON_BACKTEST_MATERIALIZE_ELIGIBILITY") == "YES_FROZEN":
        result = materialize_eligibility()
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if os.getenv("W4C_R1_EXPANDED_ECON_BACKTEST_EXECUTE") == "YES_FROZEN_EXPANDED_ECON":
        result = execute_economic_backtest()
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    raise SystemExit("Set one mode: VALIDATE_ONLY=YES, MATERIALIZE_ELIGIBILITY=YES_FROZEN, or EXECUTE=YES_FROZEN_EXPANDED_ECON")


if __name__ == "__main__":
    main()

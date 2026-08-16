#!/usr/bin/env python3
"""W4-C/R1 expanded PIT signal coverage executor v1.

Goal: expand point-in-time prediction-market signal coverage beyond the current
109-row signal map before any security price, return, benchmark, settlement,
earnings outcome, or ARGOS PnL read.

Allowed reads:
- existing frozen repo artifacts;
- public Polymarket Gamma search/catalog fields needed for market identity and
  CLOB token IDs;
- public Polymarket CLOB historical YES prices only at or before the deterministic
  safe cutoff.

Forbidden reads:
- prediction-market settlement/outcome fields;
- earnings numeric outcomes;
- equity/security prices or returns;
- benchmark returns;
- ARGOS PnL or previous trade tape economics.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"

PROTOCOL = REG / "w4c_r1_expanded_pit_signal_coverage_protocol_v1.json"
COVERAGE_FREEZE = REG / "w4c_r1_expanded_economic_backtest_signal_coverage_freeze_v1.json"
ELIGIBILITY_V1 = REG / "w4c_r1_expanded_economic_backtest_eligibility_manifest_v1.csv.gz"
SIGNAL_MAP_V2 = REG / "w4c_r1_expanded_economic_backtest_signal_map_v2.csv"

OUT_TRACE = REG / "w4c_r1_expanded_pit_external_coverage_trace_v1.csv.gz"
OUT_MAP = REG / "w4c_r1_expanded_economic_backtest_signal_map_v3.csv"
OUT_SUMMARY = REG / "w4c_r1_expanded_pit_external_coverage_summary_v1.json"
OUT_ELIGIBILITY = REG / "w4c_r1_expanded_economic_backtest_eligibility_manifest_v2.csv.gz"
OUT_ELIGIBILITY_SUMMARY = REG / "w4c_r1_expanded_economic_backtest_eligibility_summary_v2.json"
OUT_AUTH_CANDIDATE = REG / "w4c_r1_expanded_price_return_authorization_candidate_v1.json"

GAMMA_SEARCH = "https://gamma-api.polymarket.com/public-search"
CLOB_HISTORY = "https://clob.polymarket.com/prices-history"
UA = "desafio-quant-w4c-r1-expanded-pit-coverage-v1/1.0"
EXECUTE_ENV = "W4C_R1_EXPANDED_PIT_EXTERNAL_COVERAGE_EXECUTE"
EXECUTE_TOKEN = "YES_FROZEN_PRE_PNL_EXTERNAL_PIT_COVERAGE"
VALIDATE_ENV = "W4C_R1_EXPANDED_PIT_EXTERNAL_COVERAGE_VALIDATE_ONLY"

MIN_COVERAGE_FOR_PNL = int(os.getenv("W4C_R1_MIN_SIGNAL_ROWS_FOR_PNL", "300"))
MAX_TICKERS = int(os.getenv("W4C_R1_MAX_EXTERNAL_TICKERS", "900"))
REQUEST_SLEEP_SECONDS = float(os.getenv("W4C_R1_EXTERNAL_REQUEST_SLEEP", "0.04"))
HISTORY_LOOKBACK_DAYS = int(os.getenv("W4C_R1_HISTORY_LOOKBACK_DAYS", "21"))
HISTORY_FIDELITY_MINUTES = int(os.getenv("W4C_R1_HISTORY_FIDELITY_MINUTES", "60"))


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


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def write_csv_gz(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
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


def parse_date(value: str) -> str:
    if not value:
        return ""
    m = re.search(r"(20\d{2}|19\d{2})[-/](\d{1,2})[-/](\d{1,2})", str(value))
    if not m:
        return ""
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return ""


def cutoff_for_event_date(event_date: str) -> datetime:
    d = datetime.strptime(event_date, "%Y-%m-%d").date()
    return datetime.combine(d - timedelta(days=1), dtime(20, 0), tzinfo=timezone.utc)


def http_json(url: str, params: Optional[dict] = None, attempts: int = 3, timeout: int = 25) -> Tuple[Optional[Any], str, int]:
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "identity"}
    last_error = ""
    last_status = 0
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                last_status = int(resp.status)
                data = resp.read(10_000_000)
                if last_status == 200:
                    return json.loads(data.decode("utf-8")), "", last_status
                last_error = f"HTTP_{last_status}"
        except urllib.error.HTTPError as exc:
            last_status = int(exc.code)
            last_error = f"HTTP_{exc.code}"
        except Exception as exc:
            last_error = type(exc).__name__
        if attempt < attempts:
            time.sleep(0.25 * attempt)
    return None, last_error, last_status


def parse_json_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return [x.strip() for x in s.split(",") if x.strip()]
    return []


def date_candidates_from_text(text: str) -> set[str]:
    out: set[str] = set()
    for m in re.finditer(r"(?<!\d)(\d{1,2})-(\d{1,2})-(20\d{2})(?!\d)", text):
        try:
            out.add(date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat())
        except ValueError:
            pass
    for m in re.finditer(r"(20\d{2})-(\d{1,2})-(\d{1,2})", text):
        try:
            out.add(date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat())
        except ValueError:
            pass
    return out


def iter_market_dicts(obj: Any, parent_text: str = "") -> Iterable[Dict[str, Any]]:
    if isinstance(obj, list):
        for x in obj:
            yield from iter_market_dicts(x, parent_text)
        return
    if not isinstance(obj, dict):
        return
    here_text = " ".join(str(obj.get(k, "")) for k in ["question", "title", "subtitle", "slug"] if obj.get(k))
    combined_text = (parent_text + " " + here_text).strip()
    if obj.get("clobTokenIds") or obj.get("clobTokenId") or obj.get("tokens"):
        d = dict(obj)
        d["_combined_text"] = combined_text
        yield d
    for key in ["markets", "events", "items", "results", "data"]:
        if key in obj:
            yield from iter_market_dicts(obj[key], combined_text)


def ticker_matches(ticker: str, text: str, slug: str) -> bool:
    t = ticker.upper()
    tlow = ticker.lower()
    upper_text = text.upper()
    slug_low = slug.lower()
    if f"({t})" in upper_text:
        return True
    if slug_low.startswith(f"{tlow}-quarterly") or slug_low.startswith(f"{tlow}-earnings"):
        return True
    if len(t) >= 3 and re.search(rf"\b{re.escape(t)}\b", upper_text) and tlow in slug_low:
        return True
    return False


def market_matches(row: Dict[str, str], market: Dict[str, Any]) -> Tuple[bool, str]:
    ticker = row["ticker"].upper()
    event_date = row["event_date"]
    text = str(market.get("_combined_text") or "")
    slug = str(market.get("slug") or "")
    low = (text + " " + slug).lower()
    if "earnings" not in low and "eps" not in low:
        return False, "NO_EARNINGS_TEXT_MATCH"
    if not ticker_matches(ticker, text, slug):
        return False, "NO_TICKER_MATCH"
    candidate_dates = set()
    candidate_dates |= date_candidates_from_text(text)
    candidate_dates |= date_candidates_from_text(slug)
    for k in ["endDate", "endDateIso", "umaEndDate", "closeDate", "closedTime"]:
        if market.get(k):
            parsed = parse_date(str(market.get(k)))
            if parsed:
                candidate_dates.add(parsed)
    if event_date not in candidate_dates:
        return False, "NO_EXACT_EVENT_DATE_MATCH"
    return True, "PASS_MARKET_IDENTITY_MATCH"


def yes_token_id(market: Dict[str, Any]) -> str:
    if market.get("clobTokenId"):
        return str(market.get("clobTokenId"))
    token_ids = parse_json_list(market.get("clobTokenIds"))
    outcomes = [str(x).strip().lower() for x in parse_json_list(market.get("outcomes"))]
    if token_ids and outcomes:
        for i, outcome in enumerate(outcomes):
            if outcome == "yes" and i < len(token_ids):
                return str(token_ids[i])
    if token_ids:
        return str(token_ids[0])
    tokens = market.get("tokens")
    if isinstance(tokens, list):
        for tok in tokens:
            if isinstance(tok, dict) and str(tok.get("outcome", "")).strip().lower() == "yes":
                return str(tok.get("token_id") or tok.get("tokenId") or "")
    return ""


def history_latest_pre_cutoff(token_id: str, cutoff: datetime) -> Tuple[str, str, str]:
    start = int((cutoff - timedelta(days=HISTORY_LOOKBACK_DAYS)).timestamp())
    end = int(cutoff.timestamp())
    payload, err, status = http_json(
        CLOB_HISTORY,
        params={"market": token_id, "startTs": start, "endTs": end, "fidelity": HISTORY_FIDELITY_MINUTES},
        attempts=3,
        timeout=30,
    )
    if err or not isinstance(payload, dict):
        return "", "", err or f"HTTP_{status}"
    hist = payload.get("history") or []
    if not isinstance(hist, list) or not hist:
        return "", "", "NO_HISTORY_POINTS"
    best_t = -1
    best_p: Optional[float] = None
    for pt in hist:
        if not isinstance(pt, dict):
            continue
        t_raw = pt.get("t") or pt.get("timestamp") or pt.get("time")
        p_raw = pt.get("p") or pt.get("price")
        try:
            ts = int(float(t_raw))
            p = float(p_raw)
        except Exception:
            continue
        if ts <= end and 0.0 <= p <= 1.0 and ts > best_t:
            best_t = ts
            best_p = p
    if best_p is None:
        return "", "", "NO_VALID_PRE_CUTOFF_POINT"
    ts_iso = datetime.fromtimestamp(best_t, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return f"{best_p:.6f}", ts_iso, "PASS_PRE_CUTOFF_HISTORY"


def validate() -> dict:
    required = [PROTOCOL, COVERAGE_FREEZE, ELIGIBILITY_V1]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"FAIL_MISSING_REQUIRED_FILES {missing}")
    protocol = read_json(PROTOCOL)
    freeze = read_json(COVERAGE_FREEZE)
    if protocol.get("gate_decision") != "PASS_W4C_R1_EXPANDED_PIT_SIGNAL_COVERAGE_PROTOCOL_FROZEN_NO_OUTCOME_RETURN_SETTLEMENT_READS":
        raise SystemExit("FAIL_PROTOCOL_NOT_FROZEN")
    if freeze.get("gate_decision") != "PASS_SIGNAL_COVERAGE_DIAGNOSIS_FROZEN_NO_EXPANDED_PNL_AUTHORIZATION":
        raise SystemExit("FAIL_COVERAGE_FREEZE_NOT_BOUND")
    if protocol.get("scientific_firewall", {}).get("economic_backtest_execution") is not False:
        raise SystemExit("FAIL_PROTOCOL_FIREWALL")
    rows = read_csv_any(ELIGIBILITY_V1)
    return {
        "status": "PASS_EXTERNAL_PIT_COVERAGE_VALIDATE_ONLY",
        "eligibility_rows": len(rows),
        "existing_signal_map_v2_present": SIGNAL_MAP_V2.exists(),
        "economic_backtest_execution": False,
        "security_price_return_read": False,
    }


def load_existing_signal_rows() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if SIGNAL_MAP_V2.exists():
        for r in read_csv_any(SIGNAL_MAP_V2):
            gid = str(r.get("exact_group_id") or "").strip()
            if not gid:
                continue
            out[gid] = dict(r)
            out[gid]["signal_source"] = r.get("signal_source") or "existing_signal_map_v2"
    return out


def search_markets_for_ticker(ticker: str) -> Tuple[List[Dict[str, Any]], str]:
    q = f"{ticker} quarterly earnings"
    payload, err, status = http_json(
        GAMMA_SEARCH,
        params={
            "q": q,
            "limit_per_type": 20,
            "keep_closed_markets": 1,
            "events_status": "all",
            "cache": "true",
        },
        attempts=3,
        timeout=25,
    )
    if err or payload is None:
        return [], err or f"HTTP_{status}"
    return list(iter_market_dicts(payload)), ""


def materialize_external_coverage() -> dict:
    validation = validate()
    eligibility = read_csv_any(ELIGIBILITY_V1)
    existing = load_existing_signal_rows()
    covered_gid = set(existing)

    missing = [r for r in eligibility if r.get("ticker") and r.get("event_date") and r.get("exact_group_id") not in covered_gid]
    by_ticker: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for r in missing:
        by_ticker[str(r["ticker"]).upper()].append(r)

    external_rows: Dict[str, Dict[str, Any]] = {}
    trace_rows: List[Dict[str, Any]] = []
    counts = Counter()
    tickers = sorted(by_ticker)[:MAX_TICKERS]

    for ti, ticker in enumerate(tickers, start=1):
        markets, search_error = search_markets_for_ticker(ticker)
        counts["gamma_search_requests"] += 1
        if search_error:
            for row in by_ticker[ticker]:
                trace_rows.append({
                    "exact_group_id": row["exact_group_id"], "ticker": ticker, "event_date": row["event_date"],
                    "stage": "GAMMA_SEARCH_FAILED", "reason": search_error,
                })
            continue
        dates_for_ticker = by_ticker[ticker]
        for row in dates_for_ticker:
            gid = row["exact_group_id"]
            cutoff = cutoff_for_event_date(row["event_date"])
            matched_any = False
            best: Optional[Dict[str, Any]] = None
            for market in markets:
                ok, reason = market_matches(row, market)
                if not ok:
                    continue
                matched_any = True
                token_id = yes_token_id(market)
                if not token_id:
                    trace_rows.append({"exact_group_id": gid, "ticker": ticker, "event_date": row["event_date"], "stage": "MARKET_MATCHED_NO_TOKEN", "reason": "NO_YES_TOKEN_ID"})
                    continue
                prob, ts_iso, hist_reason = history_latest_pre_cutoff(token_id, cutoff)
                counts["clob_history_requests"] += 1
                if hist_reason != "PASS_PRE_CUTOFF_HISTORY":
                    trace_rows.append({
                        "exact_group_id": gid, "ticker": ticker, "event_date": row["event_date"], "stage": "CLOB_HISTORY_NO_SIGNAL",
                        "reason": hist_reason, "token_id": token_id, "market_slug": market.get("slug", ""),
                    })
                    continue
                candidate = {
                    "exact_group_id": gid,
                    "ticker": ticker,
                    "event_date": row["event_date"],
                    "safe_cutoff_utc": cutoff.isoformat().replace("+00:00", "Z"),
                    "pit_probability": prob,
                    "pit_timestamp_utc": ts_iso,
                    "signal_source": "polymarket_gamma_clob_external_pre_cutoff_v1",
                    "market_id": str(market.get("id") or market.get("conditionId") or ""),
                    "market_slug": str(market.get("slug") or ""),
                    "yes_token_id": token_id,
                    "join_rule": "gamma_public_search_identity_plus_clob_pre_cutoff_history",
                }
                if best is None or candidate["pit_timestamp_utc"] > best["pit_timestamp_utc"]:
                    best = candidate
            if best is not None:
                external_rows[gid] = best
                trace_rows.append({
                    "exact_group_id": gid, "ticker": ticker, "event_date": row["event_date"],
                    "stage": "PASS_EXTERNAL_PIT_SIGNAL", "reason": "PASS_EXTERNAL_SIGNAL_MAP_JOIN",
                    "token_id": best["yes_token_id"], "market_slug": best["market_slug"], "pit_timestamp_utc": best["pit_timestamp_utc"],
                })
            elif not matched_any:
                trace_rows.append({"exact_group_id": gid, "ticker": ticker, "event_date": row["event_date"], "stage": "NO_MARKET_IDENTITY_MATCH", "reason": "NO_GAMMA_MARKET_MATCH_FOR_TICKER_DATE"})
        if REQUEST_SLEEP_SECONDS:
            time.sleep(REQUEST_SLEEP_SECONDS)

    combined = dict(existing)
    combined.update(external_rows)
    combined_fields = [
        "exact_group_id", "ticker", "event_date", "safe_cutoff_utc", "pit_probability", "pit_timestamp_utc",
        "signal_source", "market_id", "market_slug", "yes_token_id", "join_rule",
    ]
    combined_rows = []
    for gid, row in sorted(combined.items()):
        normalized = {k: row.get(k, "") for k in combined_fields}
        normalized["exact_group_id"] = gid
        # compatibility with older maps
        normalized["pit_probability"] = normalized["pit_probability"] or row.get("p_cutoff", "") or row.get("probability", "")
        normalized["pit_timestamp_utc"] = normalized["pit_timestamp_utc"] or row.get("timestamp_utc", "") or row.get("signal_timestamp", "")
        combined_rows.append(normalized)

    trace_fields = ["exact_group_id", "ticker", "event_date", "stage", "reason", "token_id", "market_slug", "pit_timestamp_utc"]
    write_csv(OUT_MAP, combined_rows, combined_fields)
    write_csv_gz(OUT_TRACE, trace_rows, trace_fields)

    eligibility_v2_rows: List[Dict[str, Any]] = []
    reason_counts = Counter()
    for r in eligibility:
        gid = r.get("exact_group_id", "")
        has_signal = gid in combined
        if not r.get("ticker"):
            primary = "NO_DETERMINISTIC_TICKER"
            stage = "INELIGIBLE_PRE_PNL"
        elif not r.get("event_date"):
            primary = "NO_DETERMINISTIC_EVENT_DATE"
            stage = "INELIGIBLE_PRE_PNL"
        elif not has_signal:
            primary = "NO_PIT_SIGNAL_BEFORE_CUTOFF"
            stage = "INELIGIBLE_PRE_PNL"
        else:
            primary = "PASS_PRE_PRICE_ELIGIBILITY"
            stage = "ELIGIBLE_PRE_PRICE_AND_PNL"
        reason_counts[primary] += 1
        nr = dict(r)
        nr.update({
            "pit_signal_ready": str(has_signal).lower(),
            "pit_signal_value_present": str(has_signal).lower(),
            "pit_timestamp_present": str(has_signal).lower(),
            "eligibility_stage": stage,
            "primary_failure_reason": primary,
            "all_failure_reasons": "" if primary == "PASS_PRE_PRICE_ELIGIBILITY" else primary,
        })
        eligibility_v2_rows.append(nr)

    elig_fields = list(eligibility_v2_rows[0].keys()) if eligibility_v2_rows else []
    write_csv_gz(OUT_ELIGIBILITY, eligibility_v2_rows, elig_fields)
    n_eligible = reason_counts["PASS_PRE_PRICE_ELIGIBILITY"]
    authorized = n_eligible >= MIN_COVERAGE_FOR_PNL

    summary = {
        "artifact": "W4C_R1_EXPANDED_PIT_EXTERNAL_COVERAGE_SUMMARY",
        "version": "W4C-R1-EXPANDED-PIT-EXTERNAL-COVERAGE-v1.0",
        "date": "2026-08-16",
        "status": "MATERIALIZED_EXTERNAL_PRE_PNL_SIGNAL_COVERAGE",
        "gate_decision": "PASS_EXTERNAL_PIT_SIGNAL_COVERAGE_MATERIALIZED_NO_OUTCOME_RETURN_SETTLEMENT_PNL_READS",
        "validation": validation,
        "counts": {
            "eligibility_rows": len(eligibility),
            "existing_signal_rows_v2": len(existing),
            "external_new_signal_rows": len(external_rows),
            "combined_signal_rows_v3": len(combined_rows),
            "missing_rows_considered": len(missing),
            "unique_missing_tickers_total": len(by_ticker),
            "unique_missing_tickers_queried": len(tickers),
            "n_final_backtestable_candidate_pre_price_v2": n_eligible,
            "min_coverage_for_pnl": MIN_COVERAGE_FOR_PNL,
            **dict(counts),
        },
        "eligibility_reason_counts_v2": dict(reason_counts),
        "decision": {
            "price_return_authorization_candidate": authorized,
            "reason": "coverage_threshold_satisfied" if authorized else "coverage_below_threshold_do_not_run_pnl_yet",
        },
        "outputs": {
            "signal_map_v3": str(OUT_MAP.relative_to(ROOT)),
            "signal_map_v3_sha256": sha256_file(OUT_MAP),
            "trace": str(OUT_TRACE.relative_to(ROOT)),
            "trace_sha256": sha256_file(OUT_TRACE),
            "eligibility_manifest_v2": str(OUT_ELIGIBILITY.relative_to(ROOT)),
            "eligibility_manifest_v2_sha256": sha256_file(OUT_ELIGIBILITY),
            "eligibility_summary_v2": str(OUT_ELIGIBILITY_SUMMARY.relative_to(ROOT)),
        },
        "scientific_firewall": {
            "outcome_reveal_authorized": False,
            "prediction_market_settlement_read": False,
            "earnings_numeric_outcomes_read": False,
            "realized_returns_read": False,
            "security_price_return_read": False,
            "benchmark_return_read": False,
            "argos_pnl_read": False,
            "economic_backtest_execution": False,
        },
        "next_gate": "authorize_price_return_backtest_if_candidate_true_else_report_signal_coverage_limit",
    }
    eligibility_summary = {
        "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_ELIGIBILITY_SUMMARY",
        "version": "W4C-R1-EXPANDED-ECON-BACKTEST-ELIGIBILITY-v2.0",
        "date": "2026-08-16",
        "status": "MATERIALIZED_PRE_PNL_ELIGIBILITY_WITH_SIGNAL_MAP_V3_FAIL_CLOSED",
        "gate_decision": "PASS_ELIGIBILITY_V2_MATERIALIZED_NO_OUTCOME_RETURN_SETTLEMENT_READS",
        "base_rows": len(eligibility_v2_rows),
        "signal_map_rows": len(combined_rows),
        "n_final_backtestable_candidate_pre_price": n_eligible,
        "failure_reason_counts": dict(reason_counts),
        "coverage_threshold_for_price_return_authorization": MIN_COVERAGE_FOR_PNL,
        "price_return_authorization_candidate": authorized,
        "outputs": summary["outputs"],
        "scientific_firewall": summary["scientific_firewall"],
    }
    write_json(OUT_SUMMARY, summary)
    write_json(OUT_ELIGIBILITY_SUMMARY, eligibility_summary)

    if authorized:
        auth = {
            "artifact": "W4C_R1_EXPANDED_PRICE_RETURN_AUTHORIZATION_CANDIDATE",
            "version": "W4C-R1-EXPANDED-PRICE-RETURN-AUTH-CANDIDATE-v1.0",
            "date": "2026-08-16",
            "status": "CANDIDATE_READY_FOR_HUMAN_OR_NEXT_GATE_AUTHORIZATION",
            "basis": {
                "coverage_summary": str(OUT_SUMMARY.relative_to(ROOT)),
                "eligibility_summary_v2": str(OUT_ELIGIBILITY_SUMMARY.relative_to(ROOT)),
                "n_final_backtestable_candidate_pre_price": n_eligible,
                "minimum_required": MIN_COVERAGE_FOR_PNL,
            },
            "not_yet_executed": {
                "security_price_return_read": True,
                "benchmark_return_read": True,
                "argos_pnl_read": True,
                "economic_backtest_execution": True,
            },
            "scientific_firewall_before_next_gate": summary["scientific_firewall"],
        }
        write_json(OUT_AUTH_CANDIDATE, auth)
    return summary


def main() -> None:
    if os.getenv(VALIDATE_ENV) == "YES":
        print(json.dumps(validate(), indent=2, sort_keys=True))
        return
    if os.getenv(EXECUTE_ENV) != EXECUTE_TOKEN:
        raise SystemExit("FAIL_MISSING_EXTERNAL_PIT_COVERAGE_EXECUTION_AUTHORIZATION")
    summary = materialize_external_coverage()
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

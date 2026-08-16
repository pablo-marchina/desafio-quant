#!/usr/bin/env python3
"""W4-C/R1 expanded PIT internal join executor v1.

Final pre-PnL coverage recovery attempt using already materialized repository
artifacts. This script does NOT read security prices/returns, benchmark returns,
earnings numeric outcomes, prediction-market settlements, or ARGOS PnL.

It may read internal market/catalog artifacts to recover market/token identity and
may query public CLOB price history only at or before deterministic safe cutoffs
for newly recovered token IDs.
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
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"

AUTH = REG / "w4c_r1_expanded_pit_internal_join_authorization_v1.json"
ELIGIBILITY_V2 = REG / "w4c_r1_expanded_economic_backtest_eligibility_manifest_v2.csv.gz"
ELIGIBILITY_V1 = REG / "w4c_r1_expanded_economic_backtest_eligibility_manifest_v1.csv.gz"
SIGNAL_MAP_V3 = REG / "w4c_r1_expanded_economic_backtest_signal_map_v3.csv"
SIGNAL_MAP_V2 = REG / "w4c_r1_expanded_economic_backtest_signal_map_v2.csv"

INTERNAL_SOURCES = [
    REG / "w4b_polymarket_recensus_venue_events_v1.csv.gz",
    REG / "w4b_polymarket_w2_overlap_v1.csv.gz",
    REG / "w2c_pit_v2_1_primary_source_queue.csv",
    REG / "w2c_pit_v2_1_primary_asset_events.csv.gz",
]

OUT_TRACE = REG / "w4c_r1_expanded_pit_internal_join_trace_v1.csv.gz"
OUT_MAP = REG / "w4c_r1_expanded_economic_backtest_signal_map_v4.csv"
OUT_SUMMARY = REG / "w4c_r1_expanded_pit_internal_join_summary_v1.json"
OUT_ELIGIBILITY = REG / "w4c_r1_expanded_economic_backtest_eligibility_manifest_v3.csv.gz"
OUT_ELIGIBILITY_SUMMARY = REG / "w4c_r1_expanded_economic_backtest_eligibility_summary_v3.json"
OUT_AUTH_CANDIDATE = REG / "w4c_r1_expanded_price_return_authorization_candidate_v2.json"
OUT_CLOSEOUT = REG / "w4c_r1_expanded_pit_signal_coverage_closeout_v1.json"

CLOB_HISTORY = "https://clob.polymarket.com/prices-history"
UA = "desafio-quant-w4c-r1-expanded-pit-internal-join-v1/1.0"
VALIDATE_ENV = "W4C_R1_EXPANDED_PIT_INTERNAL_JOIN_VALIDATE_ONLY"
EXECUTE_ENV = "W4C_R1_EXPANDED_PIT_INTERNAL_JOIN_EXECUTE"
EXECUTE_TOKEN = "YES_FROZEN_PRE_PNL_INTERNAL_PIT_JOIN"

MIN_COVERAGE_FOR_PNL = int(os.getenv("W4C_R1_MIN_SIGNAL_ROWS_FOR_PNL", "300"))
MAX_NEW_TOKENS = int(os.getenv("W4C_R1_MAX_INTERNAL_NEW_TOKENS", "1200"))
HISTORY_LOOKBACK_DAYS = int(os.getenv("W4C_R1_HISTORY_LOOKBACK_DAYS", "21"))
HISTORY_FIDELITY_MINUTES = int(os.getenv("W4C_R1_HISTORY_FIDELITY_MINUTES", "60"))
REQUEST_SLEEP_SECONDS = float(os.getenv("W4C_R1_INTERNAL_REQUEST_SLEEP", "0.03"))

DATE_FIELD_HINTS = [
    "event_date", "company_event_date", "target_date", "close_date", "closed_time", "end_date", "enddate",
    "endDate", "endDateIso", "umaEndDate", "resolution_date", "resolved_date", "cutoff_date",
]
TICKER_FIELD_HINTS = [
    "ticker", "symbol", "asset_ticker", "company_ticker", "primary_ticker", "underlying_ticker",
    "stock_ticker", "equity_ticker",
]
TEXT_FIELD_HINTS = [
    "exact_group_id", "group_id", "question", "title", "name", "subtitle", "slug", "market_slug",
    "event_slug", "description", "market_title", "event_title", "condition_slug",
]
TOKEN_FIELD_HINTS = [
    "yes_token_id", "clob_token_id", "clobTokenId", "token_id", "tokenId", "yes_clob_token_id",
    "primary_asset_token_id", "market_token_id", "clobTokenIds", "clob_token_ids", "tokens",
]
IDENTIFIER_FIELD_HINTS = [
    "market_id", "condition_id", "conditionId", "clob_market_id", "market_slug", "slug", "event_id",
]
FORBIDDEN_VALUE_FIELDS = [
    "settlement", "settled", "resolution", "resolved", "winner", "winning", "result", "pnl", "return",
    "profit", "loss", "actual_eps", "reported_eps", "surprise",
]


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def iter_csv_any(path: Path) -> Iterator[Dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            yield {str(k): ("" if v is None else str(v)) for k, v in row.items()}


def read_csv_any(path: Path) -> List[Dict[str, str]]:
    return list(iter_csv_any(path))


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def write_csv_gz(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_json_maybe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def parse_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    parsed = parse_json_maybe(value)
    if isinstance(parsed, list):
        return parsed
    s = str(value).strip()
    if not s:
        return []
    if "," in s:
        return [x.strip().strip('"\'') for x in s.split(",") if x.strip()]
    return [s]


def parse_date_any(value: str) -> Set[str]:
    out: Set[str] = set()
    if not value:
        return out
    text = str(value)
    # ISO dates first.
    for m in re.finditer(r"(?<!\d)(20\d{2}|19\d{2})[-/](\d{1,2})[-/](\d{1,2})(?!\d)", text):
        try:
            out.add(date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat())
        except ValueError:
            pass
    # Common US-style dates in Polymarket slugs/questions.
    for m in re.finditer(r"(?<!\d)(\d{1,2})[-/](\d{1,2})[-/](20\d{2}|19\d{2})(?!\d)", text):
        try:
            out.add(date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat())
        except ValueError:
            pass
    return out


def cutoff_for_event_date(event_date: str) -> datetime:
    d = datetime.strptime(event_date, "%Y-%m-%d").date()
    return datetime.combine(d - timedelta(days=1), dtime(20, 0), tzinfo=timezone.utc)


def http_json(url: str, params: Optional[dict] = None, attempts: int = 3, timeout: int = 30) -> Tuple[Optional[Any], str, int]:
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


def latest_pre_cutoff_history(token_id: str, cutoff: datetime) -> Tuple[str, str, str]:
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
            price = float(p_raw)
        except Exception:
            continue
        if ts <= end and 0.0 <= price <= 1.0 and ts > best_t:
            best_t = ts
            best_p = price
    if best_p is None:
        return "", "", "NO_VALID_PRE_CUTOFF_POINT"
    return f"{best_p:.6f}", datetime.fromtimestamp(best_t, tz=timezone.utc).isoformat().replace("+00:00", "Z"), "PASS_PRE_CUTOFF_HISTORY"


def selected_text(row: Dict[str, str]) -> str:
    parts: List[str] = []
    lower_keys = {k.lower(): k for k in row}
    for hint in TEXT_FIELD_HINTS:
        k = lower_keys.get(hint.lower())
        if k and row.get(k):
            parts.append(row[k])
    return " ".join(parts)[:5000]


def safe_direct_tickers(row: Dict[str, str], ticker_set: Set[str]) -> Set[str]:
    out: Set[str] = set()
    lower_keys = {k.lower(): k for k in row}
    for hint in TICKER_FIELD_HINTS:
        k = lower_keys.get(hint.lower())
        if not k:
            continue
        value = re.sub(r"[^A-Za-z0-9.\-]", "", row.get(k, "")).upper()
        if value in ticker_set:
            out.add(value)
    return out


def text_tickers(text: str, ticker_set: Set[str]) -> Set[str]:
    if not text:
        return set()
    out: Set[str] = set()
    upper = text.upper()
    for token in set(re.findall(r"\b[A-Z]{1,5}\b", upper)):
        if token in ticker_set:
            out.add(token)
    # Slugs often hold lower-case ticker without uppercase boundaries.
    low = text.lower()
    for ticker in ticker_set:
        if len(ticker) >= 3 and re.search(rf"(^|[^a-z0-9]){re.escape(ticker.lower())}([^a-z0-9]|$)", low):
            out.add(ticker)
    return out


def row_dates(row: Dict[str, str], text: str) -> Set[str]:
    out: Set[str] = set()
    lower_keys = {k.lower(): k for k in row}
    for hint in DATE_FIELD_HINTS:
        k = lower_keys.get(hint.lower())
        if k and row.get(k):
            out |= parse_date_any(row[k])
    if not out:
        out |= parse_date_any(text)
    return out


def token_candidates(row: Dict[str, str]) -> List[Tuple[str, str]]:
    """Return (token_id, extraction_rule). Uses outcome labels only for token orientation, never settlement."""
    out: List[Tuple[str, str]] = []
    lower_keys = {k.lower(): k for k in row}

    # Token records with explicit Yes outcome.
    outcome_col = lower_keys.get("outcome") or lower_keys.get("token_outcome") or lower_keys.get("asset_outcome")
    token_col = lower_keys.get("token_id") or lower_keys.get("tokenid") or lower_keys.get("clob_token_id") or lower_keys.get("clobtokenid")
    if outcome_col and token_col and row.get(token_col) and row.get(outcome_col, "").strip().lower() == "yes":
        out.append((row[token_col].strip(), f"explicit_yes_{token_col}"))

    for hint in TOKEN_FIELD_HINTS:
        k = lower_keys.get(hint.lower())
        if not k or not row.get(k):
            continue
        parsed = parse_json_maybe(row[k])
        if isinstance(parsed, list) and k.lower() in {"tokens"}:
            for tok in parsed:
                if isinstance(tok, dict) and str(tok.get("outcome", "")).strip().lower() == "yes":
                    tid = str(tok.get("token_id") or tok.get("tokenId") or tok.get("id") or "").strip()
                    if tid:
                        out.append((tid, f"tokens_json_yes_{k}"))
        elif k.lower() in {"clobtokenids", "clob_token_ids"}:
            token_ids = [str(x).strip() for x in parse_list(row[k]) if str(x).strip()]
            outcomes: List[str] = []
            for ok in ["outcomes", "outcome_names", "token_outcomes"]:
                source = lower_keys.get(ok)
                if source:
                    outcomes = [str(x).strip().lower() for x in parse_list(row[source])]
                    break
            if token_ids and outcomes:
                for i, outcome in enumerate(outcomes):
                    if outcome == "yes" and i < len(token_ids):
                        out.append((token_ids[i], f"clob_token_ids_yes_index_{k}"))
            elif token_ids:
                out.append((token_ids[0], f"clob_token_ids_first_{k}"))
        else:
            for item in parse_list(row[k]):
                tid = str(item).strip().strip('"\'')
                if tid and len(tid) >= 10:
                    out.append((tid, f"token_field_{k}"))

    # Deduplicate while preserving order.
    seen: Set[str] = set()
    dedup: List[Tuple[str, str]] = []
    for tid, rule in out:
        if tid not in seen:
            seen.add(tid)
            dedup.append((tid, rule))
    return dedup


def identifier_values(row: Dict[str, str]) -> Dict[str, str]:
    lower_keys = {k.lower(): k for k in row}
    out: Dict[str, str] = {}
    for hint in IDENTIFIER_FIELD_HINTS:
        k = lower_keys.get(hint.lower())
        if k and row.get(k):
            out[hint] = row[k]
    return out


def load_existing_signal_rows() -> Dict[str, Dict[str, Any]]:
    src = SIGNAL_MAP_V3 if SIGNAL_MAP_V3.exists() else SIGNAL_MAP_V2
    out: Dict[str, Dict[str, Any]] = {}
    if not src.exists():
        return out
    for r in read_csv_any(src):
        gid = str(r.get("exact_group_id") or "").strip()
        if not gid:
            continue
        row = dict(r)
        row["signal_source"] = row.get("signal_source") or src.name
        out[gid] = row
    return out


def load_eligibility() -> List[Dict[str, str]]:
    return read_csv_any(ELIGIBILITY_V2 if ELIGIBILITY_V2.exists() else ELIGIBILITY_V1)


def validate() -> dict:
    missing = [str(p.relative_to(ROOT)) for p in [AUTH, ELIGIBILITY_V1] if not p.exists()]
    if missing:
        raise SystemExit(f"FAIL_MISSING_REQUIRED_FILES {missing}")
    auth = read_json(AUTH)
    if auth.get("gate_decision") != "PASS_W4C_R1_EXPANDED_PIT_INTERNAL_JOIN_AUTHORIZED_NO_OUTCOME_RETURN_SETTLEMENT_PNL_READS":
        raise SystemExit("FAIL_INTERNAL_JOIN_AUTH_NOT_FROZEN")
    source_presence = {str(p.relative_to(ROOT)): p.exists() for p in INTERNAL_SOURCES}
    if not any(source_presence.values()):
        raise SystemExit("FAIL_NO_INTERNAL_JOIN_SOURCES_PRESENT")
    rows = load_eligibility()
    return {
        "status": "PASS_INTERNAL_PIT_JOIN_VALIDATE_ONLY",
        "eligibility_rows": len(rows),
        "existing_signal_map_present": SIGNAL_MAP_V3.exists() or SIGNAL_MAP_V2.exists(),
        "internal_source_presence": source_presence,
        "economic_backtest_execution": False,
        "security_price_return_read": False,
    }


def build_internal_candidates(eligibility: List[Dict[str, str]], existing: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], dict]:
    missing_by_key: Dict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)
    ticker_set: Set[str] = set()
    for row in eligibility:
        gid = row.get("exact_group_id", "")
        ticker = str(row.get("ticker", "")).upper().strip()
        event_date = row.get("event_date", "").strip()
        if not ticker or not event_date or gid in existing:
            continue
        ticker_set.add(ticker)
        missing_by_key[(ticker, event_date)].append(row)

    candidates_by_gid: Dict[str, Dict[str, Any]] = {}
    trace: List[Dict[str, Any]] = []
    counts = Counter()
    source_stats: Dict[str, dict] = {}

    for source in INTERNAL_SOURCES:
        source_key = str(source.relative_to(ROOT))
        stats = Counter()
        if not source.exists():
            stats["missing_source_file"] += 1
            source_stats[source_key] = dict(stats)
            continue
        for row in iter_csv_any(source):
            stats["rows_scanned"] += 1
            tokens = token_candidates(row)
            if not tokens:
                stats["rows_without_token_candidate"] += 1
                continue
            text = selected_text(row)
            tickers = safe_direct_tickers(row, ticker_set)
            if not tickers:
                tickers = text_tickers(text, ticker_set)
            if not tickers:
                stats["rows_without_relevant_ticker"] += 1
                continue
            dates = row_dates(row, text)
            if not dates:
                stats["rows_without_date"] += 1
                continue
            ids = identifier_values(row)
            for ticker in tickers:
                for event_date in dates:
                    key = (ticker, event_date)
                    if key not in missing_by_key:
                        continue
                    for base in missing_by_key[key]:
                        gid = base["exact_group_id"]
                        # Keep the first deterministic candidate per exact_group_id and token, but prefer explicit direct ticker fields.
                        token_id, rule = tokens[0]
                        previous = candidates_by_gid.get(gid)
                        candidate = {
                            "exact_group_id": gid,
                            "ticker": ticker,
                            "event_date": event_date,
                            "safe_cutoff_utc": cutoff_for_event_date(event_date).isoformat().replace("+00:00", "Z"),
                            "token_id": token_id,
                            "token_extraction_rule": rule,
                            "internal_source": source_key,
                            "internal_identifier_fields": json.dumps(ids, sort_keys=True),
                            "join_rule": "internal_artifact_ticker_event_date_token_identity_join_v1",
                        }
                        if previous is None:
                            candidates_by_gid[gid] = candidate
                            stats["new_gid_candidates"] += 1
                        else:
                            stats["duplicate_gid_candidates_ignored"] += 1
                        trace.append({
                            "exact_group_id": gid,
                            "ticker": ticker,
                            "event_date": event_date,
                            "stage": "INTERNAL_TOKEN_CANDIDATE",
                            "reason": "PASS_INTERNAL_TICKER_DATE_TOKEN_JOIN",
                            "token_id": token_id,
                            "source": source_key,
                            "rule": rule,
                        })
            stats["rows_with_relevant_ticker_date_token_scan"] += 1
        source_stats[source_key] = dict(stats)
        counts.update({f"{source.name}:{k}": v for k, v in stats.items()})
    return candidates_by_gid, trace, {"missing_key_count": len(missing_by_key), "missing_gid_count": sum(len(v) for v in missing_by_key.values()), "source_stats": source_stats, "flat_counts": dict(counts)}


def materialize_internal_join() -> dict:
    validation = validate()
    eligibility = load_eligibility()
    existing = load_existing_signal_rows()
    candidates, trace, join_stats = build_internal_candidates(eligibility, existing)

    new_signal_rows: Dict[str, Dict[str, Any]] = {}
    history_counts = Counter()
    for idx, (gid, cand) in enumerate(sorted(candidates.items()), start=1):
        if len(new_signal_rows) >= MAX_NEW_TOKENS:
            trace.append({**cand, "stage": "SKIP_MAX_NEW_TOKEN_LIMIT", "reason": "MAX_NEW_TOKENS_REACHED", "source": cand.get("internal_source", "")})
            continue
        cutoff = cutoff_for_event_date(cand["event_date"])
        prob, ts_iso, reason = latest_pre_cutoff_history(cand["token_id"], cutoff)
        history_counts["clob_history_requests"] += 1
        if reason != "PASS_PRE_CUTOFF_HISTORY":
            history_counts[reason] += 1
            trace.append({
                "exact_group_id": gid,
                "ticker": cand["ticker"],
                "event_date": cand["event_date"],
                "stage": "INTERNAL_TOKEN_NO_PRE_CUTOFF_HISTORY",
                "reason": reason,
                "token_id": cand["token_id"],
                "source": cand.get("internal_source", ""),
                "rule": cand.get("token_extraction_rule", ""),
            })
            continue
        new_signal_rows[gid] = {
            "exact_group_id": gid,
            "ticker": cand["ticker"],
            "event_date": cand["event_date"],
            "safe_cutoff_utc": cand["safe_cutoff_utc"],
            "pit_probability": prob,
            "pit_timestamp_utc": ts_iso,
            "signal_source": "internal_artifact_token_join_plus_clob_pre_cutoff_history_v1",
            "market_id": cand.get("internal_identifier_fields", ""),
            "market_slug": "",
            "yes_token_id": cand["token_id"],
            "join_rule": cand["join_rule"],
            "internal_source": cand.get("internal_source", ""),
        }
        trace.append({
            "exact_group_id": gid,
            "ticker": cand["ticker"],
            "event_date": cand["event_date"],
            "stage": "PASS_INTERNAL_PIT_SIGNAL",
            "reason": "PASS_INTERNAL_JOIN_AND_PRE_CUTOFF_HISTORY",
            "token_id": cand["token_id"],
            "source": cand.get("internal_source", ""),
            "rule": cand.get("token_extraction_rule", ""),
            "pit_timestamp_utc": ts_iso,
        })
        if REQUEST_SLEEP_SECONDS:
            time.sleep(REQUEST_SLEEP_SECONDS)

    combined = dict(existing)
    combined.update(new_signal_rows)
    map_fields = [
        "exact_group_id", "ticker", "event_date", "safe_cutoff_utc", "pit_probability", "pit_timestamp_utc",
        "signal_source", "market_id", "market_slug", "yes_token_id", "join_rule", "internal_source",
    ]
    map_rows: List[Dict[str, Any]] = []
    for gid, row in sorted(combined.items()):
        nr = {k: row.get(k, "") for k in map_fields}
        nr["exact_group_id"] = gid
        nr["pit_probability"] = nr["pit_probability"] or row.get("p_cutoff", "") or row.get("probability", "")
        nr["pit_timestamp_utc"] = nr["pit_timestamp_utc"] or row.get("timestamp_utc", "") or row.get("signal_timestamp", "")
        map_rows.append(nr)

    reason_counts = Counter()
    eligibility_v3: List[Dict[str, Any]] = []
    for row in eligibility:
        gid = row.get("exact_group_id", "")
        has_signal = gid in combined
        if not row.get("ticker"):
            reason = "NO_DETERMINISTIC_TICKER"
            stage = "INELIGIBLE_PRE_PNL"
        elif not row.get("event_date"):
            reason = "NO_DETERMINISTIC_EVENT_DATE"
            stage = "INELIGIBLE_PRE_PNL"
        elif not has_signal:
            reason = "NO_PIT_SIGNAL_BEFORE_CUTOFF"
            stage = "INELIGIBLE_PRE_PNL"
        else:
            reason = "PASS_PRE_PRICE_ELIGIBILITY"
            stage = "ELIGIBLE_PRE_PRICE_AND_PNL"
        reason_counts[reason] += 1
        nr = dict(row)
        nr.update({
            "pit_signal_ready": str(has_signal).lower(),
            "pit_signal_value_present": str(has_signal).lower(),
            "pit_timestamp_present": str(has_signal).lower(),
            "eligibility_stage": stage,
            "primary_failure_reason": reason,
            "all_failure_reasons": "" if reason == "PASS_PRE_PRICE_ELIGIBILITY" else reason,
        })
        eligibility_v3.append(nr)

    trace_fields = ["exact_group_id", "ticker", "event_date", "stage", "reason", "token_id", "source", "rule", "pit_timestamp_utc"]
    elig_fields = list(eligibility_v3[0].keys()) if eligibility_v3 else []
    write_csv(OUT_MAP, map_rows, map_fields)
    write_csv_gz(OUT_TRACE, trace, trace_fields)
    write_csv_gz(OUT_ELIGIBILITY, eligibility_v3, elig_fields)

    n_eligible = reason_counts["PASS_PRE_PRICE_ELIGIBILITY"]
    authorized = n_eligible >= MIN_COVERAGE_FOR_PNL
    firewall = {
        "outcome_reveal_authorized": False,
        "prediction_market_settlement_read": False,
        "earnings_numeric_outcomes_read": False,
        "realized_returns_read": False,
        "security_price_return_read": False,
        "benchmark_return_read": False,
        "argos_pnl_read": False,
        "economic_backtest_execution": False,
    }
    outputs = {
        "signal_map_v4": str(OUT_MAP.relative_to(ROOT)),
        "signal_map_v4_sha256": sha256_file(OUT_MAP),
        "internal_join_trace": str(OUT_TRACE.relative_to(ROOT)),
        "internal_join_trace_sha256": sha256_file(OUT_TRACE),
        "eligibility_manifest_v3": str(OUT_ELIGIBILITY.relative_to(ROOT)),
        "eligibility_manifest_v3_sha256": sha256_file(OUT_ELIGIBILITY),
        "eligibility_summary_v3": str(OUT_ELIGIBILITY_SUMMARY.relative_to(ROOT)),
    }
    summary = {
        "artifact": "W4C_R1_EXPANDED_PIT_INTERNAL_JOIN_SUMMARY",
        "version": "W4C-R1-EXPANDED-PIT-INTERNAL-JOIN-v1.0",
        "date": "2026-08-16",
        "status": "MATERIALIZED_INTERNAL_PRE_PNL_SIGNAL_COVERAGE",
        "gate_decision": "PASS_INTERNAL_PIT_SIGNAL_JOIN_MATERIALIZED_NO_OUTCOME_RETURN_SETTLEMENT_PNL_READS",
        "validation": validation,
        "counts": {
            "eligibility_rows": len(eligibility),
            "existing_signal_rows_v3": len(existing),
            "internal_token_candidates_by_gid": len(candidates),
            "internal_new_signal_rows": len(new_signal_rows),
            "combined_signal_rows_v4": len(map_rows),
            "n_final_backtestable_candidate_pre_price_v3": n_eligible,
            "min_coverage_for_pnl": MIN_COVERAGE_FOR_PNL,
            **dict(history_counts),
        },
        "join_stats": join_stats,
        "eligibility_reason_counts_v3": dict(reason_counts),
        "decision": {
            "price_return_authorization_candidate": authorized,
            "reason": "coverage_threshold_satisfied" if authorized else "coverage_below_threshold_freeze_final_pit_coverage_closeout",
        },
        "outputs": outputs,
        "scientific_firewall": firewall,
        "next_gate": "authorize_price_return_backtest_if_candidate_true_else_use_closeout_in_report_page_4",
    }
    eligibility_summary = {
        "artifact": "W4C_R1_EXPANDED_ECONOMIC_BACKTEST_ELIGIBILITY_SUMMARY",
        "version": "W4C-R1-EXPANDED-ECON-BACKTEST-ELIGIBILITY-v3.0",
        "date": "2026-08-16",
        "status": "MATERIALIZED_PRE_PNL_ELIGIBILITY_WITH_SIGNAL_MAP_V4_FAIL_CLOSED",
        "gate_decision": "PASS_ELIGIBILITY_V3_MATERIALIZED_NO_OUTCOME_RETURN_SETTLEMENT_READS",
        "base_rows": len(eligibility_v3),
        "signal_map_rows": len(map_rows),
        "n_final_backtestable_candidate_pre_price": n_eligible,
        "failure_reason_counts": dict(reason_counts),
        "coverage_threshold_for_price_return_authorization": MIN_COVERAGE_FOR_PNL,
        "price_return_authorization_candidate": authorized,
        "outputs": outputs,
        "scientific_firewall": firewall,
    }
    write_json(OUT_SUMMARY, summary)
    write_json(OUT_ELIGIBILITY_SUMMARY, eligibility_summary)

    if authorized:
        write_json(OUT_AUTH_CANDIDATE, {
            "artifact": "W4C_R1_EXPANDED_PRICE_RETURN_AUTHORIZATION_CANDIDATE",
            "version": "W4C-R1-EXPANDED-PRICE-RETURN-AUTH-CANDIDATE-v2.0",
            "date": "2026-08-16",
            "status": "CANDIDATE_READY_FOR_PRICE_RETURN_BACKTEST_GATE",
            "basis": {
                "internal_join_summary": str(OUT_SUMMARY.relative_to(ROOT)),
                "eligibility_summary_v3": str(OUT_ELIGIBILITY_SUMMARY.relative_to(ROOT)),
                "n_final_backtestable_candidate_pre_price": n_eligible,
                "minimum_required": MIN_COVERAGE_FOR_PNL,
            },
            "not_yet_executed": {
                "security_price_return_read": True,
                "benchmark_return_read": True,
                "argos_pnl_read": True,
                "economic_backtest_execution": True,
            },
            "scientific_firewall_before_next_gate": firewall,
        })
    else:
        write_json(OUT_CLOSEOUT, {
            "artifact": "W4C_R1_EXPANDED_PIT_SIGNAL_COVERAGE_CLOSEOUT",
            "version": "W4C-R1-EXPANDED-PIT-SIGNAL-COVERAGE-CLOSEOUT-v1.0",
            "date": "2026-08-16",
            "status": "FROZEN_FINAL_SIGNAL_COVERAGE_LIMITATION_PRE_PNL",
            "gate_decision": "FAIL_EXPANDED_PRICE_RETURN_BACKTEST_AUTHORIZATION_COVERAGE_BELOW_THRESHOLD",
            "basis": {
                "official_domain_expanded_universe_rows": len(eligibility),
                "signal_map_v4_rows": len(map_rows),
                "n_final_backtestable_candidate_pre_price": n_eligible,
                "minimum_required_for_expanded_pnl": MIN_COVERAGE_FOR_PNL,
                "internal_new_signal_rows": len(new_signal_rows),
                "internal_token_candidates_by_gid": len(candidates),
                "summary": str(OUT_SUMMARY.relative_to(ROOT)),
                "eligibility_summary_v3": str(OUT_ELIGIBILITY_SUMMARY.relative_to(ROOT)),
            },
            "report_page_4_policy": "Use official-domain expansion 1355 plus PIT coverage limitation and last complete economic backtest, not an expanded PnL claim.",
            "scientific_firewall": firewall,
        })
    return summary


def main() -> None:
    if os.getenv(VALIDATE_ENV) == "YES":
        print(json.dumps(validate(), indent=2, sort_keys=True))
        return
    if os.getenv(EXECUTE_ENV) != EXECUTE_TOKEN:
        raise SystemExit("FAIL_MISSING_INTERNAL_PIT_JOIN_EXECUTION_AUTHORIZATION")
    print(json.dumps(materialize_internal_join(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

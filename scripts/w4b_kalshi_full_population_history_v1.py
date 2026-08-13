#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import json
import time
from bisect import bisect_right
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
BASE = "https://external-api.kalshi.com/trade-api/v2"
UA = "ARGOS-W4B-full-history/1.0"
PROTO = json.loads((REG / "w4b_kalshi_full_population_history_protocol_v1.json").read_text())
SEMANTIC = REG / "w4b_kalshi_semantic_events_v1_1.csv.gz"
HORIZONS = [(int(x["hours_before_t0"]), int(x["max_staleness_hours"])) for x in PROTO["horizon_ladder"]]


def parse_ts(s: str) -> int:
    return int(datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp())


def request_json(url: str, retries: int = 7):
    last = None
    for i in range(retries):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode()), 200, None
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode(errors="replace")[:500]
            except Exception:
                pass
            last = {"status": e.code, "error": body or str(e)}
            if e.code == 404:
                return None, 404, last
            if 400 <= e.code < 500 and e.code != 429:
                return None, e.code, last
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            last = {"status": None, "error": str(e)}
        if i + 1 < retries:
            time.sleep(min(16.0, 1.0 * (2 ** i)))
    return None, (last or {}).get("status"), last or {"status": None, "error": "unknown"}


def fetch_candles(series_ticker: str, ticker: str, start_ts: int, end_ts: int) -> dict:
    q = urlencode({"start_ts": start_ts, "end_ts": end_ts, "period_interval": 60})
    hurl = f"{BASE}/historical/markets/{ticker}/candlesticks?{q}"
    obj, status, err = request_json(hurl)
    route = "historical"
    if status == 404:
        lurl = f"{BASE}/series/{series_ticker}/markets/{ticker}/candlesticks?{q}"
        obj, status, err = request_json(lurl)
        route = "live"
    if status != 200 or obj is None:
        return {
            "market_ticker": ticker,
            "route_used": route,
            "http_resolution_status": "API_UNRESOLVED",
            "api_status": status if status is not None else "",
            "api_error": (err or {}).get("error", ""),
            "candlestick_count": 0,
            "first_end_period_ts": "",
            "last_end_period_ts": "",
            "timestamps": [],
        }
    raw = obj.get("candlesticks", [])
    ts = sorted({int(x["end_period_ts"]) for x in raw if x.get("end_period_ts") is not None and start_ts <= int(x["end_period_ts"]) <= end_ts})
    return {
        "market_ticker": ticker,
        "route_used": route,
        "http_resolution_status": "RESOLVED_200_EMPTY" if not ts else "RESOLVED_200_DATA",
        "api_status": 200,
        "api_error": "",
        "candlestick_count": len(ts),
        "first_end_period_ts": ts[0] if ts else "",
        "last_end_period_ts": ts[-1] if ts else "",
        "timestamps": ts,
    }


def horizon_metrics(ts: list[int], t0: int) -> tuple[dict[str, bool], dict[str, str]]:
    valid = {}
    stale = {}
    for hours, max_stale_h in HORIZONS:
        key = f"t_minus_{hours}h"
        target = t0 - hours * 3600
        idx = bisect_right(ts, target) - 1
        if idx < 0:
            valid[key] = False
            stale[key] = ""
            continue
        staleness = target - ts[idx]
        valid[key] = 0 <= staleness <= max_stale_h * 3600
        stale[key] = str(staleness)
    return valid, stale


def event_class(any_valid: dict[str, bool]) -> str:
    n = sum(bool(v) for v in any_valid.values())
    h240 = any_valid["t_minus_240h"]
    h1 = any_valid["t_minus_1h"]
    if n == len(HORIZONS):
        return "FULL_LADDER"
    if h240 and h1 and n >= 8:
        return "CORE_T10_TO_T1H"
    if n == 0:
        return "NO_HISTORY"
    if not h240:
        return "NO_T10D"
    if not h1:
        return "NO_NEAR_T0"
    return "PARTIAL"


def main():
    accepted = []
    with gzip.open(SEMANTIC, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("semantic_status", "").startswith("ACCEPT") and r.get("canonicalization_status") == "PASS":
                accepted.append(r)

    groups: dict[str, dict] = {}
    ticker_to_cid = {}
    collision = []
    for r in accepted:
        cid = r["canonical_event_id"]
        g = groups.setdefault(cid, {"rows": [], "tickers": {}, "t0_candidates": []})
        g["rows"].append(r)
        if r.get("latest_close_time"):
            try:
                g["t0_candidates"].append(parse_ts(r["latest_close_time"]))
            except Exception:
                pass
        for ticker in filter(None, r.get("market_tickers", "").split("|")):
            if ticker in ticker_to_cid and ticker_to_cid[ticker] != cid:
                collision.append({"ticker": ticker, "cid_a": ticker_to_cid[ticker], "cid_b": cid})
            ticker_to_cid[ticker] = cid
            g["tickers"].setdefault(ticker, r["series_ticker"])

    if len(groups) != int(PROTO["input"]["expected_accepted_unique_canonical_events"]):
        raise SystemExit(f"canonical_event_count_mismatch:{len(groups)}")
    if collision:
        raise SystemExit(f"market_ticker_cross_canonical_collision:{collision[:5]}")
    if any(not g["t0_candidates"] for g in groups.values()):
        raise SystemExit("missing_operational_t0_candidate")

    tasks = []
    for cid, g in sorted(groups.items()):
        t0 = min(g["t0_candidates"])
        start = t0 - 264 * 3600
        for ticker, series in sorted(g["tickers"].items()):
            tasks.append((cid, series, ticker, start, t0))

    print(json.dumps({"canonical_events": len(groups), "unique_market_tickers": len(tasks)}, sort_keys=True), flush=True)
    fetched = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        future_map = {
            ex.submit(fetch_candles, series, ticker, start, t0): (cid, series, ticker, start, t0)
            for cid, series, ticker, start, t0 in tasks
        }
        done = 0
        for fut in as_completed(future_map):
            cid, series, ticker, start, t0 = future_map[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"market_ticker": ticker, "route_used": "", "http_resolution_status": "API_UNRESOLVED", "api_status": "", "api_error": repr(e), "candlestick_count": 0, "first_end_period_ts": "", "last_end_period_ts": "", "timestamps": []}
            fetched[(cid, ticker)] = (series, start, t0, res)
            done += 1
            if done % 250 == 0:
                print(f"resolved_market_requests={done}/{len(tasks)}", flush=True)

    market_rows = []
    unresolved = []
    per_event_market_rows = defaultdict(list)
    market_fields = ["canonical_event_id","series_ticker","market_ticker","operational_t0_ts","route_used","http_resolution_status","api_status","candlestick_count","first_end_period_ts","last_end_period_ts"]
    for hours, _ in HORIZONS:
        market_fields += [f"t_minus_{hours}h_valid", f"t_minus_{hours}h_staleness_seconds"]

    for (cid, ticker), (series, start, t0, res) in sorted(fetched.items()):
        valid, stale = horizon_metrics(res["timestamps"], t0)
        row = {
            "canonical_event_id": cid,
            "series_ticker": series,
            "market_ticker": ticker,
            "operational_t0_ts": t0,
            "route_used": res["route_used"],
            "http_resolution_status": res["http_resolution_status"],
            "api_status": res["api_status"],
            "candlestick_count": res["candlestick_count"],
            "first_end_period_ts": res["first_end_period_ts"],
            "last_end_period_ts": res["last_end_period_ts"],
        }
        for hours, _ in HORIZONS:
            key = f"t_minus_{hours}h"
            row[f"{key}_valid"] = "YES" if valid[key] else "NO"
            row[f"{key}_staleness_seconds"] = stale[key]
        market_rows.append(row)
        per_event_market_rows[cid].append(row)
        if res["http_resolution_status"] == "API_UNRESOLVED":
            unresolved.append({"canonical_event_id": cid, "ticker": ticker, "status": res["api_status"], "error": res["api_error"]})

    event_fields = ["canonical_event_id","resolved_family","operational_t0_ts","alias_event_rows","unique_market_tickers","history_class","distributional_core_flag"]
    for hours, _ in HORIZONS:
        event_fields += [f"t_minus_{hours}h_any_valid", f"t_minus_{hours}h_market_fraction_valid"]
    event_rows = []
    class_counts = defaultdict(int)
    family_classes = defaultdict(lambda: defaultdict(int))
    for cid, g in sorted(groups.items()):
        rows = per_event_market_rows[cid]
        if not rows:
            raise SystemExit(f"no_market_rows:{cid}")
        any_valid = {}
        fracs = {}
        resolved_rows = [r for r in rows if r["http_resolution_status"] != "API_UNRESOLVED"]
        denom = len(resolved_rows)
        for hours, _ in HORIZONS:
            k = f"t_minus_{hours}h"
            count = sum(r[f"{k}_valid"] == "YES" for r in resolved_rows)
            any_valid[k] = count > 0
            fracs[k] = (count / denom) if denom else 0.0
        cls = event_class(any_valid)
        dist = fracs["t_minus_240h"] >= 0.5 and fracs["t_minus_1h"] >= 0.5 and sum(any_valid.values()) >= 8
        fams = sorted({r["resolved_family"] for r in g["rows"]})
        if len(fams) != 1:
            raise SystemExit(f"canonical_family_collision:{cid}:{fams}")
        fam = fams[0]
        row = {
            "canonical_event_id": cid,
            "resolved_family": fam,
            "operational_t0_ts": min(g["t0_candidates"]),
            "alias_event_rows": len(g["rows"]),
            "unique_market_tickers": len(rows),
            "history_class": cls,
            "distributional_core_flag": "YES" if dist else "NO",
        }
        for hours, _ in HORIZONS:
            k = f"t_minus_{hours}h"
            row[f"{k}_any_valid"] = "YES" if any_valid[k] else "NO"
            row[f"{k}_market_fraction_valid"] = f"{fracs[k]:.10f}"
        event_rows.append(row)
        class_counts[cls] += 1
        family_classes[fam][cls] += 1

    def write_gz(path, rows, fields):
        with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader(); w.writerows(rows)

    write_gz(REG / "w4b_kalshi_history_market_v1.csv.gz", market_rows, market_fields)
    write_gz(REG / "w4b_kalshi_history_event_v1.csv.gz", event_rows, event_fields)

    summary = {
        "artifact": "W4B_KALSHI_FULL_POPULATION_HISTORY_SUMMARY",
        "version": "W4B-KH-RESULT-v1.0",
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTO["version"],
        "performance_blind": True,
        "linked_asset_realized_returns_read": False,
        "kalshi_settlement_results_persisted": False,
        "canonical_events_expected": 387,
        "canonical_events_audited": len(event_rows),
        "unique_market_tickers_audited": len(market_rows),
        "api_unresolved_count": len(unresolved),
        "api_unresolved_examples": unresolved[:20],
        "history_class_counts": dict(sorted(class_counts.items())),
        "distributional_core_events": sum(r["distributional_core_flag"] == "YES" for r in event_rows),
        "family_history_class_counts": {f: dict(sorted(v.items())) for f, v in sorted(family_classes.items())},
        "horizon_event_counts": {
            f"t_minus_{h}h": sum(r[f"t_minus_{h}h_any_valid"] == "YES" for r in event_rows)
            for h, _ in HORIZONS
        },
        "technical_gate_decision": "PASS_FULL_POPULATION_HISTORY_MATERIALIZED" if len(event_rows) == 387 and not unresolved else "FAIL_HISTORY_MATERIALIZATION",
        "interpretation": "Venue-side pre-event candlestick availability relative to conservative operational Kalshi close-time T0. Not official event-time truth, not cross-venue unique N, not asset-mapped and not N_final_backtestable."
    }
    (REG / "w4b_kalshi_history_summary_v1.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: summary[k] for k in ["canonical_events_audited","unique_market_tickers_audited","api_unresolved_count","history_class_counts","distributional_core_events","horizon_event_counts","technical_gate_decision"]}, indent=2, sort_keys=True), flush=True)
    if summary["technical_gate_decision"].startswith("FAIL"):
        raise SystemExit(2)

if __name__ == "__main__":
    main()

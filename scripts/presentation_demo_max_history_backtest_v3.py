#!/usr/bin/env python3
"""Complete max-history retrospective backtest across the canonical venue universes.

This is a presentation/research extension only. It does not reopen, replace, or
reinterpret the frozen competition protocol. Candidate construction uses only
pre-existing performance-blind semantic/canonical artifacts. Price, settlement,
and PnL are read only after the candidate/event identity is fixed.

Outputs three economically distinct views:
  1) max-history per venue (each venue uses its own oldest observable history),
  2) common-overlap prediction-market slice,
  3) canonical-event-deduplicated prediction-market sensitivity.

Legacy funded equity accounting is reported separately because NAV/active wealth
is not commensurate with one-contract prediction-market PnL.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
OUT_SUMMARY = REG / "presentation_demo_max_history_backtest_summary_v3.json"
OUT_SCORECARD = REG / "presentation_demo_max_history_backtest_scorecard_v3.csv"
OUT_TRADES = REG / "presentation_demo_max_history_backtest_trades_v3.csv"
OUT_YEARLY = REG / "presentation_demo_max_history_backtest_yearly_v3.csv"
OUT_FUNNELS = REG / "presentation_demo_max_history_backtest_funnels_v3.csv"
OUT_ERRORS = REG / "presentation_demo_max_history_backtest_errors_v3.csv"
OUT_FORECASTEX = REG / "presentation_demo_max_history_forecastex_v3.json"

UA = "ARGOS-max-history-backtest/3.0"
TH_YES = float(os.getenv("ARGOS_MAX_HISTORY_THRESHOLD_YES", "0.65"))
TH_NO = float(os.getenv("ARGOS_MAX_HISTORY_THRESHOLD_NO", "0.35"))
PM_LOOKBACK_DAYS = int(os.getenv("ARGOS_MAX_HISTORY_PM_LOOKBACK_DAYS", "14"))
KALSHI_LOOKBACK_HOURS = int(os.getenv("ARGOS_MAX_HISTORY_KALSHI_LOOKBACK_HOURS", "264"))
HTTP_TIMEOUT = float(os.getenv("ARGOS_MAX_HISTORY_HTTP_TIMEOUT", "35"))
PM_DETAIL_WORKERS = int(os.getenv("ARGOS_MAX_HISTORY_PM_DETAIL_WORKERS", "12"))
KALSHI_WORKERS = int(os.getenv("ARGOS_MAX_HISTORY_KALSHI_WORKERS", "4"))

PM_CANON = REG / "w4b_polymarket_recensus_events_v1.csv.gz"
KALSHI_EVENTS = REG / "w4b_kalshi_history_event_v1_0_3.csv.gz"
KALSHI_MARKETS = REG / "w4b_kalshi_history_market_v1_0_3.csv.gz"
FORECASTEX_EVENTS = REG / "w4b_forecastex_events_v1.csv.gz"
FORECASTEX_CONTRACTS = REG / "w4b_forecastex_contracts_v1.csv.gz"
V2_BOOTSTRAP = ROOT / "scripts" / "presentation_demo_multi_route_backtest_suite_bootstrap_v2.py"

PM_GAMMA = "https://gamma-api.polymarket.com"
PM_CLOB = "https://clob.polymarket.com"
KALSHI_BASE = "https://external-api.kalshi.com/trade-api/v2"


def read_gz(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8", newline="", errors="replace") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def parse_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        try:
            return datetime.fromtimestamp(float(s), timezone.utc)
        except Exception:
            pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def ts(v: Any) -> int | None:
    d = parse_dt(v)
    return int(d.timestamp()) if d else None


def iso(v: Any) -> str:
    d = parse_dt(v)
    return d.isoformat() if d else ""


def fnum(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(str(v).strip())
        return x if math.isfinite(x) else None
    except Exception:
        return None


def json_array(v: Any) -> list[Any]:
    if isinstance(v, list):
        return v
    if v is None:
        return []
    try:
        x = json.loads(str(v))
        return x if isinstance(x, list) else []
    except Exception:
        return []


def request_json(url: str, *, method: str = "GET", body: dict | None = None, retries: int = 7) -> Any:
    data = None
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in {429, 500, 502, 503, 504}:
                raise
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            last = e
        if i + 1 < retries:
            time.sleep(min(12.0, 0.5 * (2**i)))
    if last:
        raise last
    raise RuntimeError("request_failed_without_exception")


def side_from_yes(p: float) -> str:
    if p >= TH_YES:
        return "BUY_YES"
    if p <= TH_NO:
        return "BUY_NO"
    return "ABSTAIN"


def make_trade(*, route_id: str, venue: str, canonical_id: str, market_id: str, ticker: str,
               question: str, category: str, entry_ts: int, entry_yes: float, entry_no: float,
               terminal_yes: float, terminal_no: float, history_points: int, history_window_days: float,
               price_source: str, data_tier: str = "", source_detail: str = "") -> dict[str, Any]:
    side = side_from_yes(entry_yes)
    if side == "BUY_YES":
        gross = terminal_yes - entry_yes
        stake = entry_yes
    elif side == "BUY_NO":
        gross = terminal_no - entry_no
        stake = entry_no
    else:
        gross = 0.0
        stake = 0.0
    net = gross
    return {
        "route_id": route_id,
        "venue": venue,
        "canonical_event_id": canonical_id,
        "market_id": market_id,
        "ticker": ticker,
        "question": question,
        "category": category,
        "entry_ts": entry_ts,
        "entry_datetime_utc": datetime.fromtimestamp(entry_ts, timezone.utc).isoformat(),
        "entry_date": datetime.fromtimestamp(entry_ts, timezone.utc).date().isoformat(),
        "entry_year": datetime.fromtimestamp(entry_ts, timezone.utc).year,
        "entry_yes_price": entry_yes,
        "entry_no_price": entry_no,
        "terminal_yes_price": terminal_yes,
        "terminal_no_price": terminal_no,
        "side": side,
        "gross_pnl_per_contract": gross,
        "net_pnl_per_contract": net,
        "return_on_stake": (net / stake) if side != "ABSTAIN" and stake > 0 else None,
        "hit": (net > 0) if side != "ABSTAIN" else None,
        "history_points": history_points,
        "history_window_days": history_window_days,
        "price_source": price_source,
        "data_tier": data_tier,
        "source_detail": source_detail,
    }


def summarize(route_id: str, venue: str, considered: int, history_returned: int, trades: list[dict[str, Any]],
              extra: dict[str, Any] | None = None) -> dict[str, Any]:
    executed = [t for t in trades if t.get("side") in {"BUY_YES", "BUY_NO"}]
    pnls = [float(t["net_pnl_per_contract"]) for t in executed]
    dates = [str(t.get("entry_date")) for t in trades if t.get("entry_date")]
    out = {
        "route_id": route_id,
        "venue": venue,
        "status": "MATERIALIZED_MAX_HISTORY_BACKTEST",
        "markets_considered": considered,
        "history_returned": history_returned,
        "trade_rows_total": len(trades),
        "executed_trades": len(executed),
        "abstained_neutral": len(trades) - len(executed),
        "buy_yes": sum(t["side"] == "BUY_YES" for t in executed),
        "buy_no": sum(t["side"] == "BUY_NO" for t in executed),
        "hit_rate": (sum(bool(t["hit"]) for t in executed) / len(executed)) if executed else None,
        "mean_net_pnl_per_contract": statistics.fmean(pnls) if pnls else None,
        "median_net_pnl_per_contract": statistics.median(pnls) if pnls else None,
        "total_net_pnl_per_1_contract_each": sum(pnls) if pnls else 0.0,
        "earliest_entry_date": min(dates) if dates else None,
        "latest_entry_date": max(dates) if dates else None,
        "canonical_events_executed": len({t.get("canonical_event_id") for t in executed if t.get("canonical_event_id")}),
    }
    if extra:
        out.update(extra)
    return out


# ------------------------------- Polymarket -------------------------------

def choose_pm_market(ev: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for m in ev.get("markets") or []:
        if not isinstance(m, dict):
            continue
        outs = [str(x).strip().lower() for x in json_array(m.get("outcomes"))]
        toks = [str(x) for x in json_array(m.get("clobTokenIds"))]
        prices = [fnum(x) for x in json_array(m.get("outcomePrices"))]
        if len(outs) != 2 or len(toks) != 2 or set(outs) != {"yes", "no"}:
            continue
        yi, ni = outs.index("yes"), outs.index("no")
        if len(prices) != 2 or prices[yi] is None or prices[ni] is None:
            continue
        ty, tn = float(prices[yi]), float(prices[ni])
        # A settled binary contract must terminate very near 0/1. This gate is
        # applied after deterministic market identity construction.
        if not ((ty >= 0.99 and tn <= 0.01) or (ty <= 0.01 and tn >= 0.99)):
            continue
        end_ts = ts(m.get("endDate") or ev.get("endDate"))
        if not end_ts:
            continue
        try:
            mid = int(str(m.get("id") or "0"))
        except Exception:
            mid = 10**30
        candidates.append((mid, str(m.get("slug") or ""), {
            "market_id": str(m.get("id") or ""),
            "question": str(m.get("question") or ev.get("title") or ""),
            "category": str(ev.get("category") or ""),
            "yes_token": toks[yi],
            "no_token": toks[ni],
            "terminal_yes": ty,
            "terminal_no": tn,
            "end_ts": end_ts,
        }))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]


def pm_resolve_canonical(r: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    gids = [x.strip() for x in re.split(r"[|,;]", r.get("gamma_event_ids", "")) if x.strip()]
    def sk(x: str):
        return (0, int(x)) if x.isdigit() else (1, x)
    errors = []
    for gid in sorted(set(gids), key=sk):
        try:
            ev = request_json(f"{PM_GAMMA}/events/{urllib.parse.quote(gid)}")
            m = choose_pm_market(ev)
            if m:
                m.update({
                    "canonical_event_id": r.get("canonical_event_id", ""),
                    "resolved_family": r.get("resolved_family", ""),
                    "gamma_event_id": gid,
                })
                return m, None
        except Exception as e:
            errors.append(f"{gid}:{type(e).__name__}:{e}")
    return None, "; ".join(errors[:3]) if errors else "no_settled_binary_market"


def pm_points(obj: Any) -> list[tuple[int, float]]:
    out = []
    if not isinstance(obj, list):
        return out
    for p in obj:
        if not isinstance(p, dict):
            continue
        try:
            tt = int(float(p.get("t")))
            px = float(p.get("p"))
            if 0 <= px <= 1:
                out.append((tt, px))
        except Exception:
            pass
    return sorted(set(out))


def pair_entry(yes_pts: list[tuple[int, float]], no_pts: list[tuple[int, float]], start: int, end: int) -> tuple[int, float, float] | None:
    y = [(t, p) for t, p in yes_pts if start <= t <= end]
    n = [(t, p) for t, p in no_pts if start <= t <= end]
    if not y or not n:
        return None
    # Actual Yes and No prices are required. Pick the earliest pair whose
    # timestamps are within 18h; no complement is synthesized.
    j = 0
    for ty, py in y:
        while j + 1 < len(n) and n[j + 1][0] <= ty:
            j += 1
        cand = [n[j]]
        if j + 1 < len(n):
            cand.append(n[j + 1])
        tn, pn = min(cand, key=lambda z: abs(z[0] - ty))
        if abs(tn - ty) <= 18 * 3600:
            return max(ty, tn), py, pn
    return None


def run_polymarket() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    canon = read_gz(PM_CANON)
    selected: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=PM_DETAIL_WORKERS) as ex:
        futs = {ex.submit(pm_resolve_canonical, r): r for r in canon}
        done = 0
        for fut in as_completed(futs):
            r = futs[fut]
            try:
                m, err = fut.result()
            except Exception as e:
                m, err = None, f"{type(e).__name__}:{e}"
            if m:
                selected.append(m)
            else:
                errors.append({"route_id": "PM_ALL_POLYMARKET_CONTRACT_PNL", "canonical_event_id": r.get("canonical_event_id"), "stage": "market_detail", "error": err or "unresolved"})
            done += 1
            if done % 250 == 0:
                print(f"pm_detail={done}/{len(canon)} selected={len(selected)}", flush=True)

    selected.sort(key=lambda m: (m["end_ts"], m["canonical_event_id"], m["market_id"]))
    trades: list[dict[str, Any]] = []
    history_returned = 0
    batch_errors = 0
    # 10 binary markets = 20 token IDs, the official batch endpoint limit.
    for i in range(0, len(selected), 10):
        chunk = selected[i:i+10]
        tokens = [tok for m in chunk for tok in (m["yes_token"], m["no_token"])]
        start = min(m["end_ts"] - PM_LOOKBACK_DAYS * 86400 for m in chunk)
        end = max(m["end_ts"] for m in chunk)
        try:
            obj = request_json(
                f"{PM_CLOB}/batch-prices-history",
                method="POST",
                body={"markets": tokens, "start_ts": start, "end_ts": end, "fidelity": 1440},
            )
            hmap = obj.get("history", {}) if isinstance(obj, dict) else {}
        except Exception as e:
            batch_errors += 1
            for m in chunk:
                errors.append({"route_id": "PM_ALL_POLYMARKET_CONTRACT_PNL", "canonical_event_id": m["canonical_event_id"], "stage": "batch_history", "error": f"{type(e).__name__}:{e}"})
            continue
        for m in chunk:
            yp = pm_points(hmap.get(m["yes_token"], []))
            np = pm_points(hmap.get(m["no_token"], []))
            st = m["end_ts"] - PM_LOOKBACK_DAYS * 86400
            ent = pair_entry(yp, np, st, m["end_ts"])
            if not ent:
                errors.append({"route_id": "PM_ALL_POLYMARKET_CONTRACT_PNL", "canonical_event_id": m["canonical_event_id"], "stage": "entry_pair", "error": f"yes_points={len(yp)};no_points={len(np)}"})
                continue
            history_returned += 1
            et, ey, en = ent
            trades.append(make_trade(
                route_id="PM_ALL_POLYMARKET_CONTRACT_PNL",
                venue="POLYMARKET",
                canonical_id=m["canonical_event_id"], market_id=m["market_id"], ticker=m["gamma_event_id"],
                question=m["question"], category=m["resolved_family"], entry_ts=et,
                entry_yes=ey, entry_no=en, terminal_yes=m["terminal_yes"], terminal_no=m["terminal_no"],
                history_points=min(len(yp), len(np)), history_window_days=PM_LOOKBACK_DAYS,
                price_source="polymarket_batch_prices_history_actual_yes_no_daily",
                source_detail=f"gamma_event={m['gamma_event_id']};yes_token={m['yes_token']};no_token={m['no_token']}",
            ))
        if (i // 10 + 1) % 25 == 0:
            print(f"pm_history_batches={i//10+1} trades={len(trades)}", flush=True)
        time.sleep(0.03)

    summary = summarize("PM_ALL_POLYMARKET_CONTRACT_PNL", "POLYMARKET", len(canon), history_returned, trades, {
        "canonical_universe": len(canon),
        "settled_binary_market_resolved": len(selected),
        "market_detail_unresolved": len(canon) - len(selected),
        "batch_history_errors": batch_errors,
        "entry_requires_actual_yes_and_no": True,
        "candidate_selection": "full W4-B canonical universe; deterministic lowest market id among settled binary Yes/No markets; no economic fields used for event selection",
    })
    funnels = [
        {"route_id": summary["route_id"], "stage": "canonical_events", "count": len(canon), "notes": "full W4-B Polymarket canonical universe"},
        {"route_id": summary["route_id"], "stage": "settled_binary_market_resolved", "count": len(selected), "notes": "deterministic market id; actual outcome token ids"},
        {"route_id": summary["route_id"], "stage": "actual_yes_no_history_returned", "count": history_returned, "notes": f"official batch-prices-history; {PM_LOOKBACK_DAYS}d pre-settlement window"},
        {"route_id": summary["route_id"], "stage": "trade_rows_materialized", "count": len(trades), "notes": "actual Yes/No entry prices"},
        {"route_id": summary["route_id"], "stage": "executed_threshold_trades", "count": summary["executed_trades"], "notes": f"YES>={TH_YES}; NO signal when YES<={TH_NO}"},
    ]
    return summary, trades, funnels, errors


# -------------------------------- Kalshi ---------------------------------

def candle_close(c: dict[str, Any]) -> float | None:
    def cv(obj: Any) -> float | None:
        if not isinstance(obj, dict):
            return None
        for k in ("close_dollars", "close"):
            x = fnum(obj.get(k))
            if x is not None:
                if k == "close" and x > 1:
                    x /= 100.0
                if 0 <= x <= 1:
                    return x
        return None
    px = cv(c.get("price"))
    if px is not None:
        return px
    b, a = cv(c.get("yes_bid")), cv(c.get("yes_ask"))
    if b is not None and a is not None:
        return (a + b) / 2
    return a if a is not None else b


def kalshi_terminal(m: dict[str, Any]) -> float | None:
    result = str(m.get("result") or "").strip().lower()
    if result == "yes":
        return 1.0
    if result == "no":
        return 0.0
    for k in ("settlement_value_dollars", "settlement_value", "settlement_price_dollars", "settlement_price"):
        x = fnum(m.get(k))
        if x is not None:
            if x > 1:
                x /= 100.0
            if 0 <= x <= 1:
                return x
    return None


def kalshi_detail(ticker: str, prefer_historical: bool) -> tuple[dict[str, Any] | None, str, str | None]:
    routes = ["historical", "live"] if prefer_historical else ["live", "historical"]
    errs = []
    qtick = urllib.parse.quote(ticker, safe="")
    for tier in routes:
        url = f"{KALSHI_BASE}/historical/markets/{qtick}" if tier == "historical" else f"{KALSHI_BASE}/markets/{qtick}"
        try:
            obj = request_json(url)
            m = obj.get("market", obj) if isinstance(obj, dict) else None
            if isinstance(m, dict):
                return m, tier, None
        except urllib.error.HTTPError as e:
            errs.append(f"{tier}:HTTP{e.code}")
            if e.code != 404:
                break
        except Exception as e:
            errs.append(f"{tier}:{type(e).__name__}:{e}")
    return None, routes[0], ";".join(errs)


def kalshi_history(ticker: str, series: str, tier: str, t0: int) -> tuple[list[tuple[int, float]], str | None]:
    start = t0 - KALSHI_LOOKBACK_HOURS * 3600
    q = urllib.parse.urlencode({"start_ts": start, "end_ts": t0, "period_interval": 60})
    qt = urllib.parse.quote(ticker, safe="")
    qs = urllib.parse.quote(series, safe="")
    if tier == "historical":
        url = f"{KALSHI_BASE}/historical/markets/{qt}/candlesticks?{q}"
    else:
        url = f"{KALSHI_BASE}/series/{qs}/markets/{qt}/candlesticks?{q}"
    try:
        obj = request_json(url)
        pts = []
        for c in obj.get("candlesticks", []) if isinstance(obj, dict) else []:
            try:
                tt = int(c.get("end_period_ts"))
            except Exception:
                continue
            px = candle_close(c)
            if px is not None and start <= tt <= t0:
                pts.append((tt, px))
        return sorted(set(pts)), None
    except Exception as e:
        return [], f"{type(e).__name__}:{e}"


def run_kalshi() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    events = read_gz(KALSHI_EVENTS)
    markets = read_gz(KALSHI_MARKETS)
    by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in markets:
        if r.get("http_resolution_status") == "RESOLVED_200_DATA":
            by_event[r.get("canonical_event_id", "")].append(r)
    event_map = {r.get("canonical_event_id", ""): r for r in events}
    candidates = []
    for cid, ev in sorted(event_map.items()):
        rows = sorted(by_event.get(cid, []), key=lambda r: (r.get("market_ticker", ""), r.get("series_ticker", "")))
        if not rows:
            candidates.append((cid, ev, []))
        else:
            # Up to 3 purely technical history-availability fallbacks. No price,
            # result or PnL is used to choose fallback order.
            candidates.append((cid, ev, rows[:3]))

    cutoff_obj = request_json(f"{KALSHI_BASE}/historical/cutoff")
    cutoff = ts(cutoff_obj.get("market_settled_ts")) if isinstance(cutoff_obj, dict) else None
    trades: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    history_returned = 0
    detail_resolved = 0
    live_provisional = 0

    def one(item):
        cid, ev, rows = item
        if not rows:
            return None, {"route_id": "PM_KALSHI_CONTRACT_PNL", "canonical_event_id": cid, "stage": "candidate", "error": "no_pre_audited_data_market"}
        t0 = int(ev.get("operational_t0_ts") or rows[0].get("operational_t0_ts") or 0)
        for r in rows:
            ticker = r.get("market_ticker", "")
            series = r.get("series_ticker", "")
            prefer_hist = bool(cutoff and t0 < cutoff)
            m, tier, derr = kalshi_detail(ticker, prefer_hist)
            if not m:
                continue
            terminal = kalshi_terminal(m)
            if terminal is None:
                continue
            # Live data is supported but excluded from the reproducible default score.
            if tier != "historical":
                return {"provisional": True, "canonical_event_id": cid, "ticker": ticker}, None
            hp, herr = kalshi_history(ticker, series, tier, t0)
            if not hp:
                continue
            et, ey = hp[0]
            en = 1.0 - ey
            tr = make_trade(
                route_id="PM_KALSHI_CONTRACT_PNL", venue="KALSHI", canonical_id=cid,
                market_id=ticker, ticker=ticker, question=str(m.get("title") or m.get("subtitle") or ticker),
                category=ev.get("resolved_family", ""), entry_ts=et, entry_yes=ey, entry_no=en,
                terminal_yes=terminal, terminal_no=1.0-terminal, history_points=len(hp),
                history_window_days=KALSHI_LOOKBACK_HOURS/24,
                price_source="kalshi_60m_yes_trade_close_implied_no",
                data_tier=tier,
                source_detail=f"series={series};operational_t0={t0};technical_fallback_rank={rows.index(r)+1}",
            )
            return {"trade": tr, "provisional": False}, None
        return None, {"route_id": "PM_KALSHI_CONTRACT_PNL", "canonical_event_id": cid, "stage": "detail_or_history", "error": "all_pre_audited_ticker_fallbacks_failed"}

    with ThreadPoolExecutor(max_workers=KALSHI_WORKERS) as ex:
        futs = {ex.submit(one, x): x[0] for x in candidates}
        done = 0
        for fut in as_completed(futs):
            cid = futs[fut]
            try:
                res, err = fut.result()
            except Exception as e:
                res, err = None, {"route_id": "PM_KALSHI_CONTRACT_PNL", "canonical_event_id": cid, "stage": "worker", "error": f"{type(e).__name__}:{e}"}
            if res:
                detail_resolved += 1
                if res.get("provisional"):
                    live_provisional += 1
                elif res.get("trade"):
                    history_returned += 1
                    trades.append(res["trade"])
            if err:
                errors.append(err)
            done += 1
            if done % 75 == 0:
                print(f"kalshi_events={done}/{len(candidates)} history={history_returned} live={live_provisional}", flush=True)

    summary = summarize("PM_KALSHI_CONTRACT_PNL", "KALSHI", len(events), history_returned, trades, {
        "canonical_universe": len(events),
        "pre_audited_market_rows": len(markets),
        "pre_audited_resolved_data_market_rows": sum(len(v) for v in by_event.values()),
        "detail_resolved_including_live": detail_resolved,
        "live_provisional_excluded": live_provisional,
        "historical_cutoff": cutoff_obj.get("market_settled_ts") if isinstance(cutoff_obj, dict) else None,
        "candidate_selection": "all 391 W4-B canonical events; lexicographic pre-audited RESOLVED_200_DATA ticker; up to 3 technical fallbacks; no economic fields used",
    })
    funnels = [
        {"route_id": summary["route_id"], "stage": "canonical_events", "count": len(events), "notes": "full W4-B Kalshi canonical universe"},
        {"route_id": summary["route_id"], "stage": "events_with_pre_audited_data_market", "count": sum(bool(by_event.get(e.get('canonical_event_id',''))) for e in events), "notes": f"market_rows={len(markets)}"},
        {"route_id": summary["route_id"], "stage": "live_provisional_excluded", "count": live_provisional, "notes": "excluded from reproducible score until archival"},
        {"route_id": summary["route_id"], "stage": "historical_candlestick_history_returned", "count": history_returned, "notes": f"60m; {KALSHI_LOOKBACK_HOURS}h pre-operational-T0"},
        {"route_id": summary["route_id"], "stage": "trade_rows_materialized", "count": len(trades), "notes": "one technical-history representative per canonical event"},
        {"route_id": summary["route_id"], "stage": "executed_threshold_trades", "count": summary["executed_trades"], "notes": f"YES>={TH_YES}; NO signal when YES<={TH_NO}"},
    ]
    return summary, trades, funnels, errors


# ------------------------------- ForecastEx -------------------------------

def run_forecastex_via_v2() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not V2_BOOTSTRAP.exists():
        raise RuntimeError("missing_v2_bootstrap")
    env = os.environ.copy()
    env.update({
        "ARGOS_MULTI_FORECASTEX_CONTRACTS": "1000",
        "ARGOS_MULTI_FORECASTEX_WORKERS": "8",
        "ARGOS_MULTI_PM_FETCH_MARKETS": "20",
        "ARGOS_MULTI_PM_ALL_MARKETS": "20",
        "ARGOS_MULTI_PM_FILTERED_MARKETS": "20",
        "ARGOS_MULTI_KALSHI_MARKETS": "1",
        "ARGOS_MULTI_HISTORY_LOOKBACK_DAYS": str(PM_LOOKBACK_DAYS),
        "ARGOS_MULTI_THRESHOLD_YES": str(TH_YES),
        "ARGOS_MULTI_THRESHOLD_NO": str(TH_NO),
    })
    subprocess.run([sys.executable, str(V2_BOOTSTRAP)], cwd=ROOT, env=env, check=True)
    v2_summary = json.loads((REG / "presentation_demo_multi_route_backtest_summary_v2.json").read_text(encoding="utf-8"))
    route = next((r for r in v2_summary.get("routes", []) if r.get("route_id") == "FORECASTEX_EVENT_CONTRACTS"), {})
    trades = []
    p = REG / "presentation_demo_multi_route_backtest_trades_v2.csv"
    if p.exists():
        with open(p, "r", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("route_id") != "FORECASTEX_EVENT_CONTRACTS":
                    continue
                et = int(float(r.get("entry_ts") or 0))
                if not et:
                    continue
                side = r.get("side") or "ABSTAIN"
                tr = {
                    "route_id": "FORECASTEX_EVENT_CONTRACTS",
                    "venue": "FORECASTEX",
                    "canonical_event_id": r.get("condition_id", ""),
                    "market_id": r.get("market_id", ""),
                    "ticker": r.get("ticker", ""),
                    "question": r.get("question", ""),
                    "category": r.get("category", ""),
                    "entry_ts": et,
                    "entry_datetime_utc": datetime.fromtimestamp(et, timezone.utc).isoformat(),
                    "entry_date": datetime.fromtimestamp(et, timezone.utc).date().isoformat(),
                    "entry_year": datetime.fromtimestamp(et, timezone.utc).year,
                    "entry_yes_price": fnum(r.get("entry_yes_price")),
                    "entry_no_price": fnum(r.get("entry_no_price")),
                    "terminal_yes_price": fnum(r.get("terminal_yes_price")),
                    "terminal_no_price": fnum(r.get("terminal_no_price")),
                    "side": side,
                    "gross_pnl_per_contract": fnum(r.get("gross_pnl_per_contract")),
                    "net_pnl_per_contract": fnum(r.get("net_pnl_per_contract")),
                    "return_on_stake": fnum(r.get("return_on_stake")),
                    "hit": str(r.get("hit", "")).lower() in {"true", "1", "yes"} if side in {"BUY_YES", "BUY_NO"} else None,
                    "history_points": int(float(r.get("history_points") or 0)),
                    "history_window_days": fnum(r.get("history_window_days")),
                    "price_source": r.get("price_source", "forecastex_official_prices_csv_actual_yes_no"),
                    "data_tier": "official_daily_csv",
                    "source_detail": f"entry_archive_date={r.get('entry_archive_date','')}",
                }
                trades.append(tr)
    canon_n = len(read_gz(FORECASTEX_EVENTS))
    history = int(route.get("history_returned") or 0)
    summary = summarize("FORECASTEX_EVENT_CONTRACTS", "FORECASTEX", canon_n, history, trades, {
        "canonical_universe": canon_n,
        "contract_identifier_rows": len(read_gz(FORECASTEX_CONTRACTS)),
        "complete_yes_no_pairs_selected": route.get("complete_yes_no_pairs_selected"),
        "official_archive_dates_fetched": route.get("official_archive_dates_fetched"),
        "settlement_resolved": route.get("settlement_resolved"),
        "fee_per_executed_contract": route.get("fee_per_executed_contract", 0.01),
        "candidate_selection": "all complete canonical-event Yes/No pairs permitted by v2 official ForecastEx census runner; max selection raised above 481",
    })
    fx_aux = REG / "presentation_demo_multi_route_forecastex_backtest_v2.json"
    if fx_aux.exists():
        aux = json.loads(fx_aux.read_text(encoding="utf-8"))
        OUT_FORECASTEX.write_text(json.dumps(aux, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    funnels = [
        {"route_id": summary["route_id"], "stage": "canonical_events", "count": canon_n, "notes": "full W4-B ForecastEx canonical universe"},
        {"route_id": summary["route_id"], "stage": "complete_yes_no_pairs_selected", "count": int(route.get("complete_yes_no_pairs_selected") or 0), "notes": "actual Yes and No identifiers"},
        {"route_id": summary["route_id"], "stage": "official_price_history_returned", "count": history, "notes": "official daily Prices CSV archive"},
        {"route_id": summary["route_id"], "stage": "trade_rows_materialized", "count": len(trades), "notes": "actual Yes and No entry prices; official settlement_price"},
        {"route_id": summary["route_id"], "stage": "executed_threshold_trades", "count": summary["executed_trades"], "notes": f"YES>={TH_YES}; NO signal when YES<={TH_NO}"},
    ]
    errors = []
    if int(route.get("complete_yes_no_pairs_selected") or 0) < canon_n:
        errors.append({"route_id": summary["route_id"], "canonical_event_id": "", "stage": "coverage", "error": f"selected_complete_pairs={route.get('complete_yes_no_pairs_selected')};canonical_universe={canon_n}"})
    return summary, trades, funnels, errors


# ------------------------------ Aggregations ------------------------------

def summarize_prediction_view(route_id: str, trades: list[dict[str, Any]], note: str) -> dict[str, Any]:
    executed = [t for t in trades if t.get("side") in {"BUY_YES", "BUY_NO"}]
    pnls = [float(t["net_pnl_per_contract"]) for t in executed]
    dates = [t["entry_date"] for t in trades if t.get("entry_date")]
    return {
        "route_id": route_id,
        "status": "DESCRIPTIVE_PREDICTION_CONTRACT_VIEW",
        "trade_rows_total": len(trades),
        "executed_trades": len(executed),
        "canonical_events_executed": len({t.get("canonical_event_id") for t in executed if t.get("canonical_event_id")}),
        "hit_rate": sum(bool(t["hit"]) for t in executed)/len(executed) if executed else None,
        "mean_net_pnl_per_contract": statistics.fmean(pnls) if pnls else None,
        "median_net_pnl_per_contract": statistics.median(pnls) if pnls else None,
        "total_net_pnl_per_1_contract_each": sum(pnls),
        "earliest_entry_date": min(dates) if dates else None,
        "latest_entry_date": max(dates) if dates else None,
        "note": note,
    }


def dedup_sensitivity(trades: list[dict[str, Any]]) -> dict[str, Any]:
    executed = [t for t in trades if t.get("side") in {"BUY_YES", "BUY_NO"} and t.get("canonical_event_id")]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in executed:
        groups[t["canonical_event_id"]].append(t)
    event_pnls = [statistics.fmean(float(t["net_pnl_per_contract"]) for t in rs) for rs in groups.values()]
    multi = sum(len(rs) > 1 for rs in groups.values())
    return {
        "route_id": "PREDICTION_CANONICAL_EVENT_DEDUP_SENSITIVITY",
        "status": "DESCRIPTIVE_EVENT_LEVEL_SENSITIVITY",
        "unique_canonical_events": len(groups),
        "multi_venue_event_groups": multi,
        "event_level_hit_rate": sum(x > 0 for x in event_pnls)/len(event_pnls) if event_pnls else None,
        "mean_event_pnl_equal_venue_average": statistics.fmean(event_pnls) if event_pnls else None,
        "median_event_pnl_equal_venue_average": statistics.median(event_pnls) if event_pnls else None,
        "total_event_pnl_equal_one_event_each": sum(event_pnls),
        "method": "same canonical_event_id trades are averaged across venues first, then each canonical event receives equal weight",
    }


def yearly_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        groups[(t["route_id"], int(t["entry_year"]))].append(t)
    out = []
    for (route, year), rs in sorted(groups.items()):
        ex = [t for t in rs if t["side"] in {"BUY_YES", "BUY_NO"}]
        pnls = [float(t["net_pnl_per_contract"]) for t in ex]
        out.append({
            "route_id": route, "year": year, "trade_rows": len(rs), "executed_trades": len(ex),
            "canonical_events": len({t.get("canonical_event_id") for t in ex if t.get("canonical_event_id")}),
            "hit_rate": sum(bool(t["hit"]) for t in ex)/len(ex) if ex else None,
            "mean_net_pnl_per_contract": statistics.fmean(pnls) if pnls else None,
            "total_net_pnl_per_1_contract_each": sum(pnls),
            "earliest_entry_date": min(t["entry_date"] for t in rs),
            "latest_entry_date": max(t["entry_date"] for t in rs),
        })
    return out


def load_legacy() -> dict[str, Any]:
    p = REG / "w2a_funded_portfolio_run_v1.json"
    if not p.exists():
        return {"status": "MISSING_W2A_FUNDED_BASELINE"}
    obj = json.loads(p.read_text(encoding="utf-8"))
    fr = obj.get("funded_result", {})
    return {
        "status": obj.get("status"),
        "input_identity": obj.get("input_identity"),
        "funded_result": fr,
        "note": "separate funded-equity baseline; NAV/active wealth is not added to prediction-contract PnL",
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    all_trades: list[dict[str, Any]] = []
    all_funnels: list[dict[str, Any]] = []
    all_errors: list[dict[str, Any]] = []
    route_summaries: list[dict[str, Any]] = []

    print("RUN_POLYMARKET_FULL_CANONICAL", flush=True)
    pm_s, pm_t, pm_f, pm_e = run_polymarket()
    route_summaries.append(pm_s); all_trades.extend(pm_t); all_funnels.extend(pm_f); all_errors.extend(pm_e)
    print(json.dumps(pm_s, sort_keys=True), flush=True)

    print("RUN_KALSHI_FULL_CANONICAL", flush=True)
    k_s, k_t, k_f, k_e = run_kalshi()
    route_summaries.append(k_s); all_trades.extend(k_t); all_funnels.extend(k_f); all_errors.extend(k_e)
    print(json.dumps(k_s, sort_keys=True), flush=True)

    print("RUN_FORECASTEX_FULL_CANONICAL", flush=True)
    f_s, f_t, f_f, f_e = run_forecastex_via_v2()
    route_summaries.append(f_s); all_trades.extend(f_t); all_funnels.extend(f_f); all_errors.extend(f_e)
    print(json.dumps(f_s, sort_keys=True), flush=True)

    prediction = [t for t in all_trades if t["venue"] in {"POLYMARKET", "KALSHI", "FORECASTEX"}]
    max_history_view = summarize_prediction_view(
        "PREDICTION_MAX_HISTORY_ALL_VENUES", prediction,
        "Each venue contributes from its own oldest genuinely observed price history; one-contract PnL is descriptive, not portfolio NAV."
    )
    earliest_by_venue = {}
    for venue in ("POLYMARKET", "KALSHI", "FORECASTEX"):
        ds = [t["entry_date"] for t in prediction if t["venue"] == venue and t["side"] in {"BUY_YES", "BUY_NO"}]
        earliest_by_venue[venue] = min(ds) if ds else None
    overlap_candidates = [d for d in earliest_by_venue.values() if d]
    overlap_start = max(overlap_candidates) if len(overlap_candidates) == 3 else None
    overlap = [t for t in prediction if overlap_start and t["entry_date"] >= overlap_start]
    overlap_view = summarize_prediction_view(
        "PREDICTION_COMMON_OVERLAP", overlap,
        f"All prediction venues restricted to dates >= {overlap_start}; comparison slice only, not the primary max-history result."
    )
    overlap_view["overlap_start_date"] = overlap_start
    overlap_view["venue_earliest_executed_dates"] = earliest_by_venue
    dedup = dedup_sensitivity(prediction)
    legacy = load_legacy()

    years = yearly_rows(prediction)
    trade_fields = [
        "route_id","venue","canonical_event_id","market_id","ticker","question","category",
        "entry_ts","entry_datetime_utc","entry_date","entry_year","entry_yes_price","entry_no_price",
        "terminal_yes_price","terminal_no_price","side","gross_pnl_per_contract","net_pnl_per_contract",
        "return_on_stake","hit","history_points","history_window_days","price_source","data_tier","source_detail",
    ]
    write_csv(OUT_TRADES, sorted(all_trades, key=lambda t: (t["entry_ts"], t["venue"], t["canonical_event_id"], t["market_id"])), trade_fields)
    write_csv(OUT_YEARLY, years, ["route_id","year","trade_rows","executed_trades","canonical_events","hit_rate","mean_net_pnl_per_contract","total_net_pnl_per_1_contract_each","earliest_entry_date","latest_entry_date"])
    write_csv(OUT_FUNNELS, all_funnels, ["route_id","stage","count","notes"])
    write_csv(OUT_ERRORS, all_errors, ["route_id","canonical_event_id","stage","error"])

    score = sorted(route_summaries, key=lambda x: (-(x.get("executed_trades") or 0), x["route_id"]))
    score_fields = ["rank","route_id","venue","status","markets_considered","history_returned","trade_rows_total","executed_trades","canonical_events_executed","earliest_entry_date","latest_entry_date","hit_rate","mean_net_pnl_per_contract","median_net_pnl_per_contract","total_net_pnl_per_1_contract_each"]
    score_rows = []
    for i, r in enumerate(score, 1):
        z = dict(r); z["rank"] = i; score_rows.append(z)
    write_csv(OUT_SCORECARD, score_rows, score_fields)

    summary = {
        "artifact": "PRESENTATION_DEMO_MAX_HISTORY_BACKTEST",
        "version": "v3.0",
        "status": "MATERIALIZED_COMPLETE_MAX_HISTORY_BACKTEST",
        "started_at_utc": started,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mode": "RETROSPECTIVE_MAX_HISTORY_NON_CONFIRMATORY",
        "guardrails": [
            "presentation_demo_only",
            "does_not_replace_frozen_competition_protocol",
            "candidate_universes_are_pre_existing_performance_blind_canonical_artifacts",
            "price_and_settlement_read_only_after_candidate_identity",
            "metadata_date_is_not_tradeable_history",
            "prediction_contract_pnl_not_equity_alpha",
            "legacy_funded_equity_nav_reported_separately",
        ],
        "thresholds": {"buy_yes": TH_YES, "buy_no_signal_yes_price": TH_NO},
        "canonical_universes": {
            "POLYMARKET": len(read_gz(PM_CANON)),
            "KALSHI": len(read_gz(KALSHI_EVENTS)),
            "FORECASTEX": len(read_gz(FORECASTEX_EVENTS)),
        },
        "route_summaries": route_summaries,
        "prediction_max_history": max_history_view,
        "prediction_common_overlap": overlap_view,
        "prediction_canonical_event_dedup_sensitivity": dedup,
        "legacy_funded_equity_baseline": legacy,
        "error_count": len(all_errors),
        "error_stage_counts": dict(sorted(Counter((e.get("route_id"), e.get("stage")) for e in all_errors).items(), key=lambda kv: str(kv[0]))),
        "outputs": {
            "scorecard": OUT_SCORECARD.relative_to(ROOT).as_posix(),
            "trades": OUT_TRADES.relative_to(ROOT).as_posix(),
            "yearly": OUT_YEARLY.relative_to(ROOT).as_posix(),
            "funnels": OUT_FUNNELS.relative_to(ROOT).as_posix(),
            "errors": OUT_ERRORS.relative_to(ROOT).as_posix(),
            "forecastex_aux": OUT_FORECASTEX.relative_to(ROOT).as_posix(),
        },
    }
    # JSON cannot serialize tuple keys from stage counts; normalize explicitly.
    summary["error_stage_counts"] = {
        f"{route}|{stage}": n for (route, stage), n in sorted(Counter((e.get("route_id"), e.get("stage")) for e in all_errors).items())
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({
        "status": summary["status"],
        "canonical_universes": summary["canonical_universes"],
        "route_summaries": route_summaries,
        "prediction_max_history": max_history_view,
        "prediction_common_overlap": overlap_view,
        "prediction_canonical_event_dedup_sensitivity": dedup,
        "error_count": len(all_errors),
    }, ensure_ascii=False, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

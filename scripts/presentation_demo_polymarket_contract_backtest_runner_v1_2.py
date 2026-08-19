#!/usr/bin/env python3
"""Polymarket contract-PnL demo backtest v1.2.

Fixes v1/v1.1 price-history blocking by using per-market short windows
anchored near each market's close/end timestamp instead of one global history
window. Always writes outputs; successful backtest requires executed trades.
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics
import time
import traceback
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"
OUT_SUMMARY = REGISTRY / "presentation_demo_polymarket_contract_backtest_summary_v1.json"
OUT_TRADES = REGISTRY / "presentation_demo_polymarket_contract_backtest_trades_v1.csv"
OUT_FUNNEL = REGISTRY / "presentation_demo_polymarket_contract_backtest_funnel_v1.csv"
OUT_UNIVERSE = REGISTRY / "presentation_demo_polymarket_contract_backtest_universe_v1.csv"
OUT_HISTORY = REGISTRY / "presentation_demo_polymarket_contract_price_history_sample_v1.csv"

GAMMA_BASE = os.getenv("ARGOS_PM_GAMMA_BASE", "https://gamma-api.polymarket.com").rstrip("/")
CLOB_BASE = os.getenv("ARGOS_PM_CLOB_BASE", "https://clob.polymarket.com").rstrip("/")
MAX_GAMMA_MARKETS = int(os.getenv("ARGOS_PM_DEMO_MAX_GAMMA_MARKETS", "500"))
MAX_BACKTEST_MARKETS = int(os.getenv("ARGOS_PM_DEMO_MAX_BACKTEST_MARKETS", "100"))
PAGE_LIMIT = int(os.getenv("ARGOS_PM_DEMO_GAMMA_PAGE_LIMIT", "250"))
FIDELITY = int(os.getenv("ARGOS_PM_DEMO_HISTORY_FIDELITY", "1440"))
LOOKBACK_DAYS = int(os.getenv("ARGOS_PM_DEMO_HISTORY_LOOKBACK_DAYS", "14"))
TIMEOUT = float(os.getenv("ARGOS_PM_DEMO_HTTP_TIMEOUT_SECONDS", "15"))
SLEEP = float(os.getenv("ARGOS_PM_DEMO_REQUEST_SLEEP_SECONDS", "0.1"))
COST = float(os.getenv("ARGOS_PM_DEMO_ROUND_TRIP_COST_BPS", "0")) / 10000.0
TH_YES = float(os.getenv("ARGOS_PM_DEMO_THRESHOLD_YES", "0.65"))
TH_NO = float(os.getenv("ARGOS_PM_DEMO_THRESHOLD_NO", "0.35"))

FIELDS_TRADES = ["market_id", "condition_id", "slug", "question", "category", "volume_num", "yes_token", "entry_ts", "entry_yes_price", "terminal_yes_price", "side", "gross_pnl_per_contract", "net_pnl_per_contract", "return_on_stake", "hit", "history_points", "history_window_days"]
FIELDS_UNIVERSE = ["market_id", "condition_id", "slug", "question", "category", "volume_num", "yes_token", "no_token", "terminal_yes_price", "outcomes_json", "prices_json", "end_date", "closed_time", "terminal_ts"]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def http_json(method: str, url: str, payload: Any | None = None) -> Any:
    headers = {"User-Agent": "ARGOS-PM-demo-backtest/1.2", "Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw.strip() else None


def val_present(v: Any) -> bool:
    return v is not None and not (isinstance(v, str) and not v.strip())


def field(d: dict[str, Any], *names: str) -> Any:
    lower = {str(k).lower(): k for k in d.keys()}
    for name in names:
        if name in d and val_present(d[name]):
            return d[name]
        k = lower.get(name.lower())
        if k is not None and val_present(d[k]):
            return d[k]
    return None


def parse_list(v: Any) -> list[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    if isinstance(v, str):
        s = v.strip()
        if not s or s.lower() in {"null", "none", "nan"}:
            return []
        for candidate in (s, s.replace("'", '"')):
            try:
                parsed = json.loads(candidate)
                return parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                pass
        if ";" in s:
            return [x.strip() for x in s.split(";") if x.strip()]
        if "," in s and not s.startswith("{"):
            return [x.strip().strip('"') for x in s.split(",") if x.strip()]
        return [s]
    return [v]


def fnum(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return x if math.isfinite(x) else None
    try:
        x = float(str(v).strip().replace(",", "."))
        return x if math.isfinite(x) else None
    except Exception:
        return None


def parse_ts(v: Any) -> int | None:
    if not val_present(v):
        return None
    s = str(v).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return int(datetime.fromisoformat(s).timestamp())
    except Exception:
        return None


def normalize_market(m: dict[str, Any]) -> dict[str, Any] | None:
    tokens = [str(x).strip() for x in parse_list(field(m, "clobTokenIds", "clob_token_ids")) if str(x).strip()]
    outcomes = [str(x).strip() for x in parse_list(field(m, "outcomes")) if str(x).strip()]
    prices = [fnum(x) for x in parse_list(field(m, "outcomePrices", "outcome_prices"))]
    prices = [x for x in prices if x is not None]
    if len(tokens) < 2:
        return None
    if len(outcomes) < 2:
        outcomes = ["Yes", "No"]
    yes_idx = 0
    for i, out in enumerate(outcomes):
        if out.lower() in {"yes", "sim", "true"}:
            yes_idx = i
            break
    no_idx = 1 if yes_idx == 0 else 0
    terminal = prices[yes_idx] if len(prices) > yes_idx else (prices[0] if prices else None)
    if terminal is not None and not (0 <= terminal <= 1):
        terminal = None
    end_date = str(field(m, "endDate", "endDateIso") or "")
    closed_time = str(field(m, "closedTime") or "")
    terminal_ts = parse_ts(closed_time) or parse_ts(end_date) or int(time.time())
    return {
        "market_id": str(field(m, "id") or ""),
        "condition_id": str(field(m, "conditionId", "condition_id") or ""),
        "slug": str(field(m, "slug") or ""),
        "question": str(field(m, "question", "title") or "")[:500],
        "category": str(field(m, "category") or ""),
        "volume_num": fnum(field(m, "volumeNum", "volume")),
        "yes_token": tokens[yes_idx] if len(tokens) > yes_idx else tokens[0],
        "no_token": tokens[no_idx] if len(tokens) > no_idx else tokens[1],
        "terminal_yes_price": terminal,
        "outcomes_json": json.dumps(outcomes, ensure_ascii=False),
        "prices_json": json.dumps(prices, ensure_ascii=False),
        "end_date": end_date,
        "closed_time": closed_time,
        "terminal_ts": terminal_ts,
    }


def fetch_markets() -> tuple[list[dict[str, Any]], list[str]]:
    raw: list[dict[str, Any]] = []
    errors: list[str] = []
    offset = 0
    while len(raw) < MAX_GAMMA_MARKETS:
        limit = min(PAGE_LIMIT, MAX_GAMMA_MARKETS - len(raw))
        params = {"closed": "true", "limit": limit, "offset": offset, "order": "volumeNum", "ascending": "false"}
        try:
            data = http_json("GET", f"{GAMMA_BASE}/markets?{urllib.parse.urlencode(params)}")
            if not isinstance(data, list) or not data:
                break
            raw.extend([x for x in data if isinstance(x, dict)])
            offset += len(data)
            time.sleep(SLEEP)
            if len(data) < limit:
                break
        except Exception as exc:
            errors.append(f"gamma offset={offset}: {type(exc).__name__}: {exc}")
            break
    return raw, errors


def clean_history(data: Any) -> list[dict[str, float]]:
    hist = data.get("history") if isinstance(data, dict) else None
    cleaned: list[dict[str, float]] = []
    if isinstance(hist, list):
        for p in hist:
            if not isinstance(p, dict):
                continue
            t = fnum(p.get("t") or p.get("timestamp") or p.get("time"))
            price = fnum(p.get("p") or p.get("price"))
            if t is not None and price is not None and 0 <= price <= 1:
                cleaned.append({"t": float(t), "p": float(price)})
    return sorted(cleaned, key=lambda x: x["t"])


def fetch_history_for_market(m: dict[str, Any]) -> tuple[list[dict[str, float]], str | None, int | None]:
    terminal_ts = int(m.get("terminal_ts") or time.time())
    end_ts = min(int(time.time()), terminal_ts + 86400)
    # Try smaller windows when CLOB rejects broad intervals.
    windows = [LOOKBACK_DAYS, 7, 3, 1]
    seen_windows = []
    for days in windows:
        if days in seen_windows or days <= 0:
            continue
        seen_windows.append(days)
        start_ts = max(0, end_ts - days * 86400)
        params = {"market": m["yes_token"], "startTs": start_ts, "endTs": end_ts, "fidelity": FIDELITY}
        try:
            data = http_json("GET", f"{CLOB_BASE}/prices-history?{urllib.parse.urlencode(params)}")
            hist = clean_history(data)
            if hist:
                return hist, None, days
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            if "interval is too long" in last.lower():
                continue
            return [], last, days
        time.sleep(SLEEP)
    return [], "no_history_points_or_interval_rejected", None


def make_trade(m: dict[str, Any], hist: list[dict[str, float]], days: int | None) -> dict[str, Any] | None:
    if not hist or m.get("terminal_yes_price") is None:
        return None
    entry = next((p for p in hist if 0.02 <= p["p"] <= 0.98), None)
    if entry is None:
        return None
    entry_yes = float(entry["p"])
    terminal = float(m["terminal_yes_price"])
    if entry_yes >= TH_YES:
        side = "BUY_YES"
        gross = terminal - entry_yes
        stake = entry_yes
    elif entry_yes <= TH_NO:
        side = "BUY_NO"
        gross = entry_yes - terminal
        stake = 1 - entry_yes
    else:
        side = "ABSTAIN"
        gross = 0.0
        stake = None
    net = gross - (COST if side != "ABSTAIN" else 0.0)
    return {
        **{k: m.get(k) for k in ["market_id", "condition_id", "slug", "question", "category", "volume_num", "yes_token", "terminal_yes_price"]},
        "entry_ts": int(entry["t"]),
        "entry_yes_price": entry_yes,
        "side": side,
        "gross_pnl_per_contract": gross,
        "net_pnl_per_contract": net,
        "return_on_stake": None if not stake else net / stake,
        "hit": None if side == "ABSTAIN" else net > 0,
        "history_points": len(hist),
        "history_window_days": days,
    }


def summarize(trades: list[dict[str, Any]]) -> dict[str, Any]:
    exe = [t for t in trades if t.get("side") in {"BUY_YES", "BUY_NO"}]
    pnls = [float(t["net_pnl_per_contract"]) for t in exe]
    rets = [float(t["return_on_stake"]) for t in exe if t.get("return_on_stake") not in {None, ""}]
    out: dict[str, Any] = {"trade_rows_total": len(trades), "executed_trades": len(exe), "abstained_neutral": len(trades) - len(exe), "buy_yes": sum(t.get("side") == "BUY_YES" for t in exe), "buy_no": sum(t.get("side") == "BUY_NO" for t in exe)}
    if pnls:
        out.update({"total_net_pnl_per_1_contract_each": sum(pnls), "mean_net_pnl_per_contract": statistics.fmean(pnls), "median_net_pnl_per_contract": statistics.median(pnls), "hit_rate": sum(x > 0 for x in pnls) / len(pnls), "min_net_pnl": min(pnls), "max_net_pnl": max(pnls)})
    if rets:
        out.update({"mean_return_on_stake": statistics.fmean(rets), "median_return_on_stake": statistics.median(rets)})
    return out


def materialize_error(err: str) -> None:
    write_csv(OUT_TRADES, [], FIELDS_TRADES)
    write_csv(OUT_UNIVERSE, [], FIELDS_UNIVERSE)
    write_csv(OUT_HISTORY, [], ["yes_token", "market_id", "t", "p"])
    funnel = [{"stage": "runtime_error", "count": 0, "notes": err[:1000]}]
    write_csv(OUT_FUNNEL, funnel, ["stage", "count", "notes"])
    OUT_SUMMARY.write_text(json.dumps({"artifact": "PRESENTATION_DEMO_POLYMARKET_CONTRACT_BACKTEST_SUMMARY", "version": "v1.2", "status": "MATERIALIZED_RUNTIME_ERROR_SUMMARY", "created_at_utc": now(), "mode": "RETROSPECTIVE_MAX_COVERAGE_NON_CONFIRMATORY", "funnel": funnel, "metrics": {}, "error": err, "guardrails": ["presentation_demo_only", "contract_pnl_not_equity_alpha", "does_not_replace_frozen_competition_protocol"]}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run() -> int:
    REGISTRY.mkdir(parents=True, exist_ok=True)
    raw, gamma_errors = fetch_markets()
    seen: set[str] = set()
    markets: list[dict[str, Any]] = []
    for r in raw:
        m = normalize_market(r)
        if m and m.get("yes_token") and m["yes_token"] not in seen:
            seen.add(m["yes_token"])
            markets.append(m)
    markets = sorted(markets, key=lambda x: (x.get("volume_num") is not None, x.get("volume_num") or 0), reverse=True)
    eligible = [m for m in markets if m.get("terminal_yes_price") is not None][:MAX_BACKTEST_MARKETS]
    histories_found = 0
    history_errors: list[str] = []
    trades: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    for idx, m in enumerate(eligible, start=1):
        hist, err, days = fetch_history_for_market(m)
        if hist:
            histories_found += 1
            for p in hist[:3]:
                history_rows.append({"yes_token": m["yes_token"], "market_id": m["market_id"], "t": int(p["t"]), "p": p["p"]})
        elif err and len(history_errors) < 50:
            history_errors.append(f"{m.get('yes_token', '')[:12]}: {err}")
        tr = make_trade(m, hist, days)
        if tr:
            trades.append(tr)
        if idx % 25 == 0:
            print(f"processed histories {idx}/{len(eligible)}", flush=True)
    funnel = [
        {"stage": "gamma_closed_markets_fetched", "count": len(raw), "notes": "; ".join(gamma_errors[:3])},
        {"stage": "markets_with_clob_tokens", "count": len(markets), "notes": "parsed Gamma clobTokenIds/outcomes/outcomePrices"},
        {"stage": "terminal_yes_price_available", "count": len(eligible), "notes": "closed outcomePrices/terminal proxy available"},
        {"stage": "price_history_returned", "count": histories_found, "notes": "; ".join(history_errors[:3])},
        {"stage": "trade_rows_materialized", "count": len(trades), "notes": "executed plus abstain-neutral rows"},
        {"stage": "executed_threshold_trades", "count": sum(t.get("side") in {"BUY_YES", "BUY_NO"} for t in trades), "notes": f"BUY_YES >= {TH_YES}; BUY_NO <= {TH_NO}"},
    ]
    write_csv(OUT_UNIVERSE, eligible, FIELDS_UNIVERSE)
    write_csv(OUT_TRADES, trades, FIELDS_TRADES)
    write_csv(OUT_FUNNEL, funnel, ["stage", "count", "notes"])
    write_csv(OUT_HISTORY, history_rows[:5000], ["yes_token", "market_id", "t", "p"])
    met = summarize(trades)
    status = "MATERIALIZED_BACKTEST" if met.get("executed_trades", 0) else "MATERIALIZED_FUNNEL_NO_EXECUTED_TRADES"
    summary = {
        "artifact": "PRESENTATION_DEMO_POLYMARKET_CONTRACT_BACKTEST_SUMMARY",
        "version": "v1.2",
        "status": status,
        "created_at_utc": now(),
        "mode": "RETROSPECTIVE_MAX_COVERAGE_NON_CONFIRMATORY",
        "route_id": "PM_ALL_POLYMARKET_CONTRACT_PNL",
        "data_sources": {"gamma_markets": f"{GAMMA_BASE}/markets?closed=true", "clob_prices_history": f"{CLOB_BASE}/prices-history"},
        "parameters": {"max_gamma_markets": MAX_GAMMA_MARKETS, "max_backtest_markets": MAX_BACKTEST_MARKETS, "history_fidelity": FIDELITY, "history_lookback_days_initial": LOOKBACK_DAYS, "threshold_yes": TH_YES, "threshold_no": TH_NO, "round_trip_cost_bps": COST * 10000},
        "funnel": funnel,
        "metrics": met,
        "category_counts_executed": dict(Counter(str(t.get("category") or "") for t in trades if t.get("side") in {"BUY_YES", "BUY_NO"})),
        "error_samples": {"gamma": gamma_errors[:10], "history": history_errors[:20]},
        "outputs": {"universe": str(OUT_UNIVERSE.relative_to(ROOT)), "trades": str(OUT_TRADES.relative_to(ROOT)), "funnel": str(OUT_FUNNEL.relative_to(ROOT)), "history_sample": str(OUT_HISTORY.relative_to(ROOT))},
        "presentation_one_liner": "Polymarket contract-PnL demo backtest using Gamma clobTokenIds and per-market short-window CLOB price history; not equity alpha and not the frozen competition result.",
        "guardrails": ["presentation_demo_only", "contract_pnl_not_equity_alpha", "retrospective_non_confirmatory", "does_not_replace_frozen_competition_protocol", "not_deployable_without_separate_oos_liquidity_fee_slippage_controls"],
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "funnel": funnel, "metrics": met}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        err = traceback.format_exc()
        materialize_error(err)
        print(err)
        raise SystemExit(0)

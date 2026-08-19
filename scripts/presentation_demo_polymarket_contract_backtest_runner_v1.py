#!/usr/bin/env python3
"""Presentation-only Polymarket contract-PnL demo backtest.

This post-challenge runner turns the unrestricted expansion route from a map into
computed demo trades. It is deliberately separated from the frozen competition
protocol and must not be described as equity alpha or as a deployable strategy.

Inputs are public Polymarket market-data endpoints:
- Gamma /markets for market metadata, clobTokenIds, outcomes and closed prices.
- CLOB /batch-prices-history for historical token prices.

The runner is dependency-free and safe to run in GitHub Actions. If the online
market-data route is unavailable, it still materializes a blocked funnel instead
of silently fabricating trades.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"

OUT_SUMMARY = REGISTRY / "presentation_demo_polymarket_contract_backtest_summary_v1.json"
OUT_TRADES = REGISTRY / "presentation_demo_polymarket_contract_backtest_trades_v1.csv"
OUT_FUNNEL = REGISTRY / "presentation_demo_polymarket_contract_backtest_funnel_v1.csv"
OUT_UNIVERSE = REGISTRY / "presentation_demo_polymarket_contract_backtest_universe_v1.csv"
OUT_HISTORY_SAMPLE = REGISTRY / "presentation_demo_polymarket_contract_price_history_sample_v1.csv"

GAMMA_BASE = os.getenv("ARGOS_PM_GAMMA_BASE", "https://gamma-api.polymarket.com")
CLOB_BASE = os.getenv("ARGOS_PM_CLOB_BASE", "https://clob.polymarket.com")
MAX_GAMMA_MARKETS = int(os.getenv("ARGOS_PM_DEMO_MAX_GAMMA_MARKETS", "1500"))
GAMMA_PAGE_LIMIT = int(os.getenv("ARGOS_PM_DEMO_GAMMA_PAGE_LIMIT", "500"))
MAX_BACKTEST_MARKETS = int(os.getenv("ARGOS_PM_DEMO_MAX_BACKTEST_MARKETS", "600"))
BATCH_SIZE = int(os.getenv("ARGOS_PM_DEMO_BATCH_SIZE", "35"))
HISTORY_FIDELITY = int(os.getenv("ARGOS_PM_DEMO_HISTORY_FIDELITY", "1440"))
START_TS = int(os.getenv("ARGOS_PM_DEMO_START_TS", "1577836800"))  # 2020-01-01
HTTP_TIMEOUT = float(os.getenv("ARGOS_PM_DEMO_HTTP_TIMEOUT_SECONDS", "20"))
REQUEST_SLEEP_SECONDS = float(os.getenv("ARGOS_PM_DEMO_REQUEST_SLEEP_SECONDS", "0.15"))
ROUND_TRIP_COST_BPS = float(os.getenv("ARGOS_PM_DEMO_ROUND_TRIP_COST_BPS", "0"))
MIN_ENTRY_PRICE = float(os.getenv("ARGOS_PM_DEMO_MIN_ENTRY_PRICE", "0.02"))
MAX_ENTRY_PRICE = float(os.getenv("ARGOS_PM_DEMO_MAX_ENTRY_PRICE", "0.98"))
THRESHOLD_YES = float(os.getenv("ARGOS_PM_DEMO_THRESHOLD_YES", "0.65"))
THRESHOLD_NO = float(os.getenv("ARGOS_PM_DEMO_THRESHOLD_NO", "0.35"))

USER_AGENT = "ARGOS-PM-demo-backtest/1.0 (+presentation-only)"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def http_json(method: str, url: str, *, payload: Any | None = None, retries: int = 3) -> Any:
    body = None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last_err: str | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                if not raw.strip():
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")[:500]
            last_err = f"HTTPError {exc.code}: {raw}"
            if exc.code in {400, 404}:
                break
        except Exception as exc:  # noqa: BLE001 - recorded in summary/funnel
            last_err = f"{type(exc).__name__}: {exc}"
        time.sleep((attempt + 1) * 0.75)
    raise RuntimeError(last_err or f"failed request {method} {url}")


def parse_jsonish(v: Any) -> list[Any]:
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
                x = json.loads(candidate)
                if isinstance(x, list):
                    return x
                return [x]
            except Exception:
                pass
        # Some exports use semicolon/comma-separated token lists.
        if ";" in s:
            return [x.strip() for x in s.split(";") if x.strip()]
        if "," in s and not s.startswith("{"):
            return [x.strip().strip('"') for x in s.split(",") if x.strip()]
        return [s]
    return [v]


def as_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return x if math.isfinite(x) else None
    s = str(v).strip().replace(",", ".")
    if not s or s.lower() in {"nan", "none", "null", "n/a"}:
        return None
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def iso_to_ts(v: Any) -> int | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return int(datetime.fromisoformat(s).timestamp())
    except Exception:
        return None


def get_field(m: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in m and m.get(name) not in {None, ""}:
            return m.get(name)
        # tolerate snake/camel differences
        low = name.lower()
        for k, v in m.items():
            if k.lower() == low and v not in {None, ""}:
                return v
    return None


def normalize_market(m: dict[str, Any], source: str) -> dict[str, Any] | None:
    tokens = [str(x).strip() for x in parse_jsonish(get_field(m, "clobTokenIds", "clob_token_ids", "tokenIds", "token_ids")) if str(x).strip()]
    outcomes = [str(x).strip() for x in parse_jsonish(get_field(m, "outcomes", "outcome_names")) if str(x).strip()]
    prices = [as_float(x) for x in parse_jsonish(get_field(m, "outcomePrices", "outcome_prices"))]
    prices = [x for x in prices if x is not None]
    if len(tokens) < 2:
        return None
    if len(outcomes) < 2:
        outcomes = ["Yes", "No"]
    yes_idx = 0
    for i, outcome in enumerate(outcomes):
        if outcome.strip().lower() in {"yes", "sim", "true"}:
            yes_idx = i
            break
    no_idx = 1 if yes_idx == 0 else 0
    yes_token = tokens[yes_idx] if yes_idx < len(tokens) else tokens[0]
    no_token = tokens[no_idx] if no_idx < len(tokens) else tokens[1]
    terminal_yes = None
    if len(prices) >= len(tokens):
        terminal_yes = prices[yes_idx]
    elif len(prices) >= 2:
        terminal_yes = prices[0]
    elif len(prices) == 1:
        terminal_yes = prices[0]
    closed = str(get_field(m, "closed", "resolved", "active") or "").lower()
    closed_bool = bool(get_field(m, "closed", "resolved")) or closed in {"true", "1", "yes"}
    return {
        "source": source,
        "market_id": str(get_field(m, "id", "market_id") or ""),
        "condition_id": str(get_field(m, "conditionId", "condition_id") or ""),
        "slug": str(get_field(m, "slug") or ""),
        "question": str(get_field(m, "question", "title", "market_question") or "")[:500],
        "category": str(get_field(m, "category") or ""),
        "end_date": str(get_field(m, "endDate", "end_date", "endDateIso") or ""),
        "closed_time": str(get_field(m, "closedTime", "closed_time") or ""),
        "closed": closed_bool,
        "volume_num": as_float(get_field(m, "volumeNum", "volume", "volume_num")),
        "liquidity_num": as_float(get_field(m, "liquidityNum", "liquidity", "liquidity_num")),
        "outcomes_json": json.dumps(outcomes, ensure_ascii=False),
        "prices_json": json.dumps(prices, ensure_ascii=False),
        "yes_token": str(yes_token),
        "no_token": str(no_token),
        "terminal_yes_price": terminal_yes,
        "raw": m,
    }


def fetch_gamma_markets() -> tuple[list[dict[str, Any]], list[str]]:
    markets: list[dict[str, Any]] = []
    errors: list[str] = []
    offset = 0
    while len(markets) < MAX_GAMMA_MARKETS:
        limit = min(GAMMA_PAGE_LIMIT, MAX_GAMMA_MARKETS - len(markets))
        params = {
            "closed": "true",
            "limit": str(limit),
            "offset": str(offset),
            "order": "volumeNum",
            "ascending": "false",
        }
        url = f"{GAMMA_BASE.rstrip('/')}/markets?{urllib.parse.urlencode(params)}"
        try:
            page = http_json("GET", url)
            if not isinstance(page, list) or not page:
                break
            for m in page:
                if isinstance(m, dict):
                    markets.append(m)
            offset += len(page)
            time.sleep(REQUEST_SLEEP_SECONDS)
            if len(page) < limit:
                break
        except Exception as exc:  # noqa: BLE001
            errors.append(f"gamma offset={offset}: {type(exc).__name__}: {exc}")
            break
    return markets, errors


def load_repo_universe_sample() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = [
        REGISTRY / "w4b_polymarket_recensus_venue_events_v1.csv.gz",
        REGISTRY / "w4b_polymarket_w2_overlap_v1.csv.gz",
        REGISTRY / "presentation_demo_all_routes_polymarket_candidates_v1.csv",
    ]
    normalized: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"files_seen": [], "rows_scanned": 0, "normalized_with_tokens": 0, "errors": []}
    for path in files:
        if not path.exists():
            continue
        meta["files_seen"].append(path.relative_to(ROOT).as_posix())
        opener = gzip.open if path.name.endswith(".gz") else open
        try:
            with opener(path, "rt", encoding="utf-8", newline="", errors="replace") as f:  # type: ignore[arg-type]
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i >= 200000:
                        break
                    meta["rows_scanned"] += 1
                    nm = normalize_market(dict(row), path.name)
                    if nm:
                        normalized.append(nm)
                        meta["normalized_with_tokens"] += 1
                        if len(normalized) >= MAX_BACKTEST_MARKETS:
                            return normalized, meta
        except Exception as exc:  # noqa: BLE001
            meta["errors"].append(f"{path.name}: {type(exc).__name__}: {exc}")
    return normalized, meta


def terminal_from_market(m: dict[str, Any]) -> float | None:
    x = m.get("terminal_yes_price")
    if x is None:
        return None
    if 0.0 <= float(x) <= 1.0:
        return float(x)
    return None


def batch_price_history(tokens: list[str]) -> tuple[dict[str, list[dict[str, float]]], list[str]]:
    histories: dict[str, list[dict[str, float]]] = {}
    errors: list[str] = []
    end_ts = int(time.time())
    for i in range(0, len(tokens), BATCH_SIZE):
        batch = tokens[i:i + BATCH_SIZE]
        payload = {"markets": batch, "start_ts": START_TS, "end_ts": end_ts, "fidelity": HISTORY_FIDELITY}
        url = f"{CLOB_BASE.rstrip('/')}/batch-prices-history"
        try:
            data = http_json("POST", url, payload=payload)
            hist_obj = data.get("history") if isinstance(data, dict) else None
            if isinstance(hist_obj, dict):
                for tok, hist in hist_obj.items():
                    parsed: list[dict[str, float]] = []
                    if isinstance(hist, list):
                        for p in hist:
                            if not isinstance(p, dict):
                                continue
                            ts = as_float(p.get("t") or p.get("timestamp") or p.get("time"))
                            price = as_float(p.get("p") or p.get("price"))
                            if ts is not None and price is not None and 0 <= price <= 1:
                                parsed.append({"t": float(ts), "p": float(price)})
                    if parsed:
                        histories[str(tok)] = sorted(parsed, key=lambda z: z["t"])
            time.sleep(REQUEST_SLEEP_SECONDS)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"batch {i // BATCH_SIZE}: {type(exc).__name__}: {exc}")
            # fallback: try individual GET calls for this batch
            for tok in batch:
                try:
                    q = urllib.parse.urlencode({"market": tok, "startTs": START_TS, "endTs": end_ts, "fidelity": HISTORY_FIDELITY})
                    data = http_json("GET", f"{CLOB_BASE.rstrip('/')}/prices-history?{q}")
                    hist = data.get("history") if isinstance(data, dict) else None
                    parsed = []
                    if isinstance(hist, list):
                        for p in hist:
                            ts = as_float(p.get("t") or p.get("timestamp") or p.get("time")) if isinstance(p, dict) else None
                            price = as_float(p.get("p") or p.get("price")) if isinstance(p, dict) else None
                            if ts is not None and price is not None and 0 <= price <= 1:
                                parsed.append({"t": float(ts), "p": float(price)})
                    if parsed:
                        histories[str(tok)] = sorted(parsed, key=lambda z: z["t"])
                    time.sleep(REQUEST_SLEEP_SECONDS)
                except Exception as exc2:  # noqa: BLE001
                    errors.append(f"token {tok[:12]}: {type(exc2).__name__}: {exc2}")
    return histories, errors


def choose_entry(hist: list[dict[str, float]]) -> dict[str, float] | None:
    if not hist:
        return None
    for point in hist:
        p = point["p"]
        if MIN_ENTRY_PRICE <= p <= MAX_ENTRY_PRICE:
            return point
    return None


def compute_trade(m: dict[str, Any], hist: list[dict[str, float]]) -> dict[str, Any] | None:
    entry = choose_entry(hist)
    terminal_yes = terminal_from_market(m)
    if entry is None or terminal_yes is None:
        return None
    entry_yes = float(entry["p"])
    if not (0 <= terminal_yes <= 1):
        return None
    cost = ROUND_TRIP_COST_BPS / 10000.0
    strategy = "ABSTAIN_NEUTRAL"
    side = "ABSTAIN"
    stake_price = None
    gross_pnl = 0.0
    if entry_yes >= THRESHOLD_YES:
        strategy = "THRESHOLD_65_35"
        side = "BUY_YES"
        stake_price = entry_yes
        gross_pnl = terminal_yes - entry_yes
    elif entry_yes <= THRESHOLD_NO:
        strategy = "THRESHOLD_65_35"
        side = "BUY_NO"
        stake_price = 1.0 - entry_yes
        gross_pnl = (1.0 - terminal_yes) - (1.0 - entry_yes)
    else:
        return {
            "market_id": m["market_id"], "condition_id": m["condition_id"], "slug": m["slug"],
            "question": m["question"], "category": m["category"], "volume_num": m["volume_num"],
            "yes_token": m["yes_token"], "entry_ts": int(entry["t"]), "entry_yes_price": entry_yes,
            "terminal_yes_price": terminal_yes, "side": side, "strategy": strategy,
            "gross_pnl_per_contract": 0.0, "net_pnl_per_contract": 0.0,
            "return_on_stake": None, "hit": None, "history_points": len(hist),
        }
    net_pnl = gross_pnl - cost
    return_on_stake = None if not stake_price or stake_price <= 0 else net_pnl / stake_price
    return {
        "market_id": m["market_id"], "condition_id": m["condition_id"], "slug": m["slug"],
        "question": m["question"], "category": m["category"], "volume_num": m["volume_num"],
        "yes_token": m["yes_token"], "entry_ts": int(entry["t"]), "entry_yes_price": entry_yes,
        "terminal_yes_price": terminal_yes, "side": side, "strategy": strategy,
        "gross_pnl_per_contract": gross_pnl, "net_pnl_per_contract": net_pnl,
        "return_on_stake": return_on_stake, "hit": net_pnl > 0, "history_points": len(hist),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    executed = [t for t in trades if t.get("side") in {"BUY_YES", "BUY_NO"}]
    abstained = [t for t in trades if t.get("side") == "ABSTAIN"]
    pnls = [float(t["net_pnl_per_contract"]) for t in executed if t.get("net_pnl_per_contract") is not None]
    rets = [float(t["return_on_stake"]) for t in executed if t.get("return_on_stake") not in {None, ""}]
    out: dict[str, Any] = {
        "trade_rows_total": len(trades),
        "executed_trades": len(executed),
        "abstained_neutral": len(abstained),
        "buy_yes": sum(1 for t in executed if t.get("side") == "BUY_YES"),
        "buy_no": sum(1 for t in executed if t.get("side") == "BUY_NO"),
    }
    if pnls:
        out.update({
            "total_net_pnl_per_1_contract_each": sum(pnls),
            "mean_net_pnl_per_contract": statistics.fmean(pnls),
            "median_net_pnl_per_contract": statistics.median(pnls),
            "hit_rate": sum(1 for x in pnls if x > 0) / len(pnls),
            "min_net_pnl": min(pnls),
            "max_net_pnl": max(pnls),
        })
    if rets:
        out.update({
            "mean_return_on_stake": statistics.fmean(rets),
            "median_return_on_stake": statistics.median(rets),
        })
    return out


def main() -> int:
    REGISTRY.mkdir(parents=True, exist_ok=True)
    started = now_utc()
    gamma_raw, gamma_errors = fetch_gamma_markets()
    gamma_norm = []
    seen_tokens = set()
    for m in gamma_raw:
        nm = normalize_market(m, "gamma_closed_markets")
        if not nm:
            continue
        key = nm["yes_token"]
        if key in seen_tokens:
            continue
        seen_tokens.add(key)
        gamma_norm.append(nm)
    repo_norm, repo_meta = load_repo_universe_sample()

    combined = gamma_norm + [m for m in repo_norm if m["yes_token"] not in seen_tokens]
    combined = sorted(combined, key=lambda m: (m.get("volume_num") is not None, m.get("volume_num") or 0), reverse=True)
    backtest_universe = [m for m in combined if m.get("yes_token") and terminal_from_market(m) is not None][:MAX_BACKTEST_MARKETS]
    tokens = [m["yes_token"] for m in backtest_universe]
    histories, history_errors = batch_price_history(tokens) if tokens else ({}, [])

    trades: list[dict[str, Any]] = []
    history_sample: list[dict[str, Any]] = []
    for m in backtest_universe:
        hist = histories.get(m["yes_token"], [])
        for p in hist[:3]:
            history_sample.append({"yes_token": m["yes_token"], "market_id": m["market_id"], "t": int(p["t"]), "p": p["p"]})
        tr = compute_trade(m, hist)
        if tr:
            trades.append(tr)

    funnel = [
        {"stage": "gamma_closed_markets_fetched", "count": len(gamma_raw), "notes": "; ".join(gamma_errors[:3])},
        {"stage": "gamma_markets_with_binary_tokens", "count": len(gamma_norm), "notes": "parsed clobTokenIds/outcomes/outcomePrices"},
        {"stage": "repo_rows_scanned_for_tokens", "count": repo_meta.get("rows_scanned", 0), "notes": "; ".join(repo_meta.get("files_seen", []))},
        {"stage": "combined_unique_token_markets", "count": len(combined), "notes": "gamma plus repo token-normalized rows"},
        {"stage": "terminal_yes_price_available", "count": len(backtest_universe), "notes": "closed market terminal outcomePrices/proxy available"},
        {"stage": "price_history_returned", "count": len(histories), "notes": "; ".join(history_errors[:3])},
        {"stage": "trade_rows_materialized", "count": len(trades), "notes": "includes executed plus abstain-neutral rows"},
        {"stage": "executed_threshold_trades", "count": sum(1 for t in trades if t.get("side") in {"BUY_YES", "BUY_NO"}), "notes": f"YES>={THRESHOLD_YES}; NO<={THRESHOLD_NO}"},
    ]

    universe_rows = [{k: m.get(k) for k in ["source", "market_id", "condition_id", "slug", "question", "category", "end_date", "closed_time", "volume_num", "liquidity_num", "yes_token", "no_token", "terminal_yes_price", "outcomes_json", "prices_json"]} for m in backtest_universe]
    write_csv(OUT_UNIVERSE, universe_rows, ["source", "market_id", "condition_id", "slug", "question", "category", "end_date", "closed_time", "volume_num", "liquidity_num", "yes_token", "no_token", "terminal_yes_price", "outcomes_json", "prices_json"])
    trade_fields = ["market_id", "condition_id", "slug", "question", "category", "volume_num", "yes_token", "entry_ts", "entry_yes_price", "terminal_yes_price", "side", "strategy", "gross_pnl_per_contract", "net_pnl_per_contract", "return_on_stake", "hit", "history_points"]
    write_csv(OUT_TRADES, trades, trade_fields)
    write_csv(OUT_FUNNEL, funnel, ["stage", "count", "notes"])
    write_csv(OUT_HISTORY_SAMPLE, history_sample[:5000], ["yes_token", "market_id", "t", "p"])

    route_metrics = metrics(trades)
    status = "MATERIALIZED_BACKTEST" if route_metrics.get("executed_trades", 0) else "MATERIALIZED_FUNNEL_NO_EXECUTED_TRADES"
    summary = {
        "artifact": "PRESENTATION_DEMO_POLYMARKET_CONTRACT_BACKTEST_SUMMARY",
        "version": "v1",
        "status": status,
        "mode": "RETROSPECTIVE_MAX_COVERAGE_NON_CONFIRMATORY",
        "created_at_utc": now_utc(),
        "started_at_utc": started,
        "route_id": "PM_ALL_POLYMARKET_CONTRACT_PNL",
        "data_sources": {
            "gamma_markets": f"{GAMMA_BASE.rstrip('/')}/markets?closed=true",
            "clob_batch_prices_history": f"{CLOB_BASE.rstrip('/')}/batch-prices-history",
            "repo_context": repo_meta,
        },
        "parameters": {
            "max_gamma_markets": MAX_GAMMA_MARKETS,
            "max_backtest_markets": MAX_BACKTEST_MARKETS,
            "batch_size": BATCH_SIZE,
            "history_fidelity": HISTORY_FIDELITY,
            "start_ts": START_TS,
            "threshold_yes": THRESHOLD_YES,
            "threshold_no": THRESHOLD_NO,
            "round_trip_cost_bps": ROUND_TRIP_COST_BPS,
        },
        "funnel": funnel,
        "metrics": route_metrics,
        "category_counts_executed": dict(Counter(str(t.get("category") or "") for t in trades if t.get("side") in {"BUY_YES", "BUY_NO"})),
        "error_samples": {
            "gamma": gamma_errors[:10],
            "history": history_errors[:20],
        },
        "outputs": {
            "universe": OUT_UNIVERSE.relative_to(ROOT).as_posix(),
            "trades": OUT_TRADES.relative_to(ROOT).as_posix(),
            "funnel": OUT_FUNNEL.relative_to(ROOT).as_posix(),
            "history_sample": OUT_HISTORY_SAMPLE.relative_to(ROOT).as_posix(),
        },
        "presentation_one_liner": "Polymarket all-events moved from a census route to a computed contract-PnL demo backtest using Gamma clobTokenIds plus CLOB historical prices; this is not equity alpha and does not replace the frozen competition result.",
        "guardrails": [
            "presentation_demo_only",
            "contract_pnl_not_equity_alpha",
            "retrospective_non_confirmatory",
            "does_not_replace_frozen_competition_protocol",
            "not_deployable_without_separate_oos_liquidity_fee_slippage_controls",
        ],
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "funnel": funnel, "metrics": route_metrics}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

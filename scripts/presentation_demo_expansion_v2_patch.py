#!/usr/bin/env python3
"""Runtime fixes for ARGOS presentation expansion v2.

Keeps the frozen competition science untouched. This wrapper only repairs two
post-challenge demo transport issues discovered in the first v2 materialization:
1) Gamma pagination was stopping after the API's 100-row page even though the
   requested page size was larger.
2) Kalshi historical settlement metadata must be resolved by the selected
   market ticker, not inferred from the first pages of a venue-wide listing.
"""
from __future__ import annotations

import importlib.util
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts" / "presentation_demo_expansion_v2.py"
spec = importlib.util.spec_from_file_location("argos_v2_base", BASE_PATH)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def fetch_pm_markets_fixed(max_rows: int):
    """Honor Gamma's effective 100-market page and continue pagination."""
    out = []
    offset = 0
    while len(out) < max_rows:
        lim = min(100, max_rows - len(out))
        q = urlencode({
            "limit": lim,
            "offset": offset,
            "closed": "true",
            "order": "volumeNum",
            "ascending": "false",
        })
        obj, res = m.get_json(f"{m.GAMMA}/markets?{q}")
        if not res["ok"] or not isinstance(obj, list) or not obj:
            break
        out.extend(obj)
        offset += len(obj)
        print(f"pm_gamma_fixed={len(out)}/{max_rows}", flush=True)
        if len(obj) < lim:
            break
    return out


def fetch_kalshi_market_by_ticker(ticker: str):
    """Resolve archived settlement/result directly for the chosen ticker."""
    urls = [
        f"{m.KALSHI}/historical/markets/{quote(ticker, safe='')}",
        f"{m.KALSHI}/markets/{quote(ticker, safe='')}",
    ]
    errors = []
    for url in urls:
        obj, res = m.get_json(url)
        if res["ok"] and isinstance(obj, dict) and isinstance(obj.get("market"), dict):
            return obj["market"], ""
        errors.append(f"{res.get('status')}:{res.get('error','')[:120]}")
    return {}, " | ".join(errors)


def run_kalshi_fixed():
    hist_path = m.REG / "w4b_kalshi_history_market_v1_0_3.csv.gz"
    structural = m.read_gz_csv(hist_path)
    if not structural:
        return [], [], {"status": "BLOCKED_NO_STRUCTURAL_HISTORY_FILE", "details": str(hist_path)}

    by_event = defaultdict(list)
    for r in structural:
        by_event[r.get("canonical_event_id", "")].append(r)

    chosen = []
    for cid, rows in sorted(by_event.items()):
        rows = sorted(
            rows,
            key=lambda r: (-(m.fnum(r.get("candlestick_count")) or 0), str(r.get("market_ticker"))),
        )
        if rows:
            chosen.append(rows[0])
    chosen = chosen[: m.KALSHI_EVENT_LIMIT]

    def worker(r):
        ticker = str(r.get("market_ticker") or "")
        series = str(r.get("series_ticker") or "")
        t0 = int(m.fnum(r.get("operational_t0_ts")) or 0)
        meta, meta_error = fetch_kalshi_market_by_ticker(ticker)
        terminal = m.kalshi_terminal(meta)
        pts, hist_error = ([], "missing_operational_t0")
        if t0:
            pts, hist_error = m.kalshi_fetch_history(series, ticker, t0)
        return {
            "venue": "Kalshi",
            "market_id": ticker,
            "event_id": r.get("canonical_event_id", ""),
            "question": str(meta.get("title") or meta.get("subtitle") or ""),
            "slug": ticker,
            "category": str(meta.get("event_ticker") or ""),
            "volume": m.fnum(meta.get("volume_fp") or meta.get("volume")) or 0.0,
            "t0_ts": t0,
            "terminal_yes_price": terminal if terminal is not None else "",
            "history_ok": bool(pts),
            "entry_ts": pts[0][0] if pts else "",
            "entry_yes_price": pts[0][1] if pts else "",
            "history_points": len(pts),
            "history_window_days": m.LOOKBACK_DAYS,
            "history_error": hist_error,
            "series_ticker": series,
            "structural_candlestick_count": r.get("candlestick_count", ""),
            "terminal_ok": terminal is not None,
            "market_type": str(meta.get("market_type") or ""),
            "result_raw": str(meta.get("result") or ""),
            "settlement_value_raw": str(meta.get("settlement_value_dollars") or ""),
            "metadata_error": meta_error,
        }

    out = []
    with ThreadPoolExecutor(max_workers=max(4, min(m.WORKERS, 8))) as ex:
        futs = {ex.submit(worker, r): r for r in chosen}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                out.append(fut.result())
            except Exception as e:
                r = futs[fut]
                out.append({
                    "venue": "Kalshi",
                    "market_id": str(r.get("market_ticker") or ""),
                    "event_id": r.get("canonical_event_id", ""),
                    "history_ok": False,
                    "terminal_ok": False,
                    "history_error": repr(e),
                    "metadata_error": repr(e),
                })
            if i % 50 == 0:
                print(f"kalshi_fixed={i}/{len(futs)}", flush=True)

    out.sort(key=lambda r: str(r.get("event_id")))
    m.write_csv(m.REG / "presentation_demo_expansion_v2_kalshi_universe.csv.gz", out, gz=True)
    covered = [
        r for r in out
        if r.get("history_ok") and r.get("terminal_ok")
        and m.fnum(r.get("entry_yes_price")) is not None
        and m.fnum(r.get("terminal_yes_price")) is not None
    ]
    trades = m.apply_threshold(covered, 0.65, 0)
    m.write_csv(m.REG / "presentation_demo_expansion_v2_kalshi_trades.csv.gz", trades, gz=True)

    result_counts = defaultdict(int)
    metadata_errors = 0
    for r in out:
        result_counts[str(r.get("result_raw") or "").lower()] += 1
        metadata_errors += bool(r.get("metadata_error"))

    blocker = {
        "status": "MATERIALIZED_BACKTEST" if covered else "BLOCKED_NO_PRICE_SETTLEMENT_JOIN",
        "structural_events": len(by_event),
        "representative_events_attempted": len(chosen),
        "history_resolved": sum(bool(r.get("history_ok")) for r in out),
        "terminal_resolved": sum(bool(r.get("terminal_ok")) for r in out),
        "price_and_terminal_joined": len(covered),
        "direct_ticker_metadata_resolved": len(out) - metadata_errors,
        "direct_ticker_metadata_errors": metadata_errors,
        "result_value_counts": dict(sorted(result_counts.items())),
        "representative_selection": "max structural candlestick_count per canonical event; outcome-blind",
    }
    return out, covered, blocker


m.fetch_pm_markets = fetch_pm_markets_fixed
m.run_kalshi = run_kalshi_fixed

if __name__ == "__main__":
    m.main()

#!/usr/bin/env python3
"""v3.1 transport wrapper for the complete max-history backtest.

The v3 scientific/candidate logic is unchanged. This wrapper changes only the
Polymarket history transport: batch-prices-history remains the fast path, but a
batch HTTP 400 (often one invalid legacy token poisoning the entire request) or
missing token history falls back to the official single-token prices-history
endpoint. Candidate identity, thresholds, settlement rules, and all other venue
logic remain byte-identical to v3.
"""
from __future__ import annotations

import importlib.util
import json
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts" / "presentation_demo_max_history_backtest_v3.py"
spec = importlib.util.spec_from_file_location("max_history_v3_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(base)


def single_history(token: str, start: int, end: int):
    q = urllib.parse.urlencode({"market": token, "startTs": start, "endTs": end, "fidelity": 1440})
    obj = base.request_json(f"{base.PM_CLOB}/prices-history?{q}")
    return base.pm_points(obj.get("history", []) if isinstance(obj, dict) else [])


def run_polymarket_v31():
    canon = base.read_gz(base.PM_CANON)
    selected = []
    errors = []
    with base.ThreadPoolExecutor(max_workers=base.PM_DETAIL_WORKERS) as ex:
        futs = {ex.submit(base.pm_resolve_canonical, r): r for r in canon}
        done = 0
        for fut in base.as_completed(futs):
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
    trades = []
    history_returned = 0
    batch_failures = 0
    single_fallback_markets = 0
    single_fallback_success = 0
    single_token_errors = 0

    def materialize(m, yp, np):
        nonlocal history_returned
        st = m["end_ts"] - base.PM_LOOKBACK_DAYS * 86400
        ent = base.pair_entry(yp, np, st, m["end_ts"])
        if not ent:
            errors.append({"route_id": "PM_ALL_POLYMARKET_CONTRACT_PNL", "canonical_event_id": m["canonical_event_id"], "stage": "entry_pair", "error": f"yes_points={len(yp)};no_points={len(np)}"})
            return
        history_returned += 1
        et, ey, en = ent
        trades.append(base.make_trade(
            route_id="PM_ALL_POLYMARKET_CONTRACT_PNL",
            venue="POLYMARKET",
            canonical_id=m["canonical_event_id"], market_id=m["market_id"], ticker=m["gamma_event_id"],
            question=m["question"], category=m["resolved_family"], entry_ts=et,
            entry_yes=ey, entry_no=en, terminal_yes=m["terminal_yes"], terminal_no=m["terminal_no"],
            history_points=min(len(yp), len(np)), history_window_days=base.PM_LOOKBACK_DAYS,
            price_source="polymarket_prices_history_actual_yes_no_daily_v31",
            source_detail=f"gamma_event={m['gamma_event_id']};yes_token={m['yes_token']};no_token={m['no_token']}",
        ))

    # Fast path is still the official max-20-token batch API.
    for i in range(0, len(selected), 10):
        chunk = selected[i:i+10]
        tokens = [tok for m in chunk for tok in (m["yes_token"], m["no_token"])]
        chunk_start = min(m["end_ts"] - base.PM_LOOKBACK_DAYS * 86400 for m in chunk)
        chunk_end = max(m["end_ts"] for m in chunk)
        hmap = {}
        batch_ok = False
        try:
            obj = base.request_json(
                f"{base.PM_CLOB}/batch-prices-history",
                method="POST",
                body={"markets": tokens, "start_ts": chunk_start, "end_ts": chunk_end, "fidelity": 1440},
            )
            hmap = obj.get("history", {}) if isinstance(obj, dict) else {}
            batch_ok = isinstance(hmap, dict)
        except Exception:
            batch_failures += 1

        for m in chunk:
            yp = base.pm_points(hmap.get(m["yes_token"], [])) if batch_ok else []
            np = base.pm_points(hmap.get(m["no_token"], [])) if batch_ok else []
            # A poisoned batch or partial response must not discard the other
            # valid legacy markets. Retry only the missing market/token pair.
            if not yp or not np:
                single_fallback_markets += 1
                st = m["end_ts"] - base.PM_LOOKBACK_DAYS * 86400
                try:
                    if not yp:
                        yp = single_history(m["yes_token"], st, m["end_ts"])
                    if not np:
                        np = single_history(m["no_token"], st, m["end_ts"])
                    if yp and np:
                        single_fallback_success += 1
                except Exception as e:
                    single_token_errors += 1
                    errors.append({"route_id": "PM_ALL_POLYMARKET_CONTRACT_PNL", "canonical_event_id": m["canonical_event_id"], "stage": "single_history_fallback", "error": f"{type(e).__name__}:{e}"})
            materialize(m, yp, np)
        if (i // 10 + 1) % 25 == 0:
            print(f"pm_history_batches={i//10+1} trades={len(trades)} fallback_markets={single_fallback_markets}", flush=True)
        time.sleep(0.02)

    summary = base.summarize("PM_ALL_POLYMARKET_CONTRACT_PNL", "POLYMARKET", len(canon), history_returned, trades, {
        "canonical_universe": len(canon),
        "settled_binary_market_resolved": len(selected),
        "market_detail_unresolved": len(canon) - len(selected),
        "batch_history_failures": batch_failures,
        "single_fallback_markets": single_fallback_markets,
        "single_fallback_success": single_fallback_success,
        "single_token_errors": single_token_errors,
        "entry_requires_actual_yes_and_no": True,
        "candidate_selection": "full W4-B canonical universe; deterministic lowest market id among settled binary Yes/No markets; no economic fields used for event selection",
        "transport_policy": "batch-prices-history fast path; single-token prices-history recovery on batch validation failure or partial token history",
    })
    funnels = [
        {"route_id": summary["route_id"], "stage": "canonical_events", "count": len(canon), "notes": "full W4-B Polymarket canonical universe"},
        {"route_id": summary["route_id"], "stage": "settled_binary_market_resolved", "count": len(selected), "notes": "deterministic market id; actual outcome token ids"},
        {"route_id": summary["route_id"], "stage": "batch_history_failures", "count": batch_failures, "notes": "recovered per market instead of dropping entire poisoned batch"},
        {"route_id": summary["route_id"], "stage": "single_fallback_markets", "count": single_fallback_markets, "notes": f"successful_actual_yes_no={single_fallback_success}; token_errors={single_token_errors}"},
        {"route_id": summary["route_id"], "stage": "actual_yes_no_history_returned", "count": history_returned, "notes": f"official prices-history; {base.PM_LOOKBACK_DAYS}d pre-settlement window"},
        {"route_id": summary["route_id"], "stage": "trade_rows_materialized", "count": len(trades), "notes": "actual Yes/No entry prices"},
        {"route_id": summary["route_id"], "stage": "executed_threshold_trades", "count": summary["executed_trades"], "notes": f"YES>={base.TH_YES}; NO signal when YES<={base.TH_NO}"},
    ]
    return summary, trades, funnels, errors


base.run_polymarket = run_polymarket_v31
rc = int(base.main())
if base.OUT_SUMMARY.exists():
    doc = json.loads(base.OUT_SUMMARY.read_text(encoding="utf-8"))
    doc["version"] = "v3.1"
    doc.setdefault("transport_recoveries", {})["polymarket"] = "batch 400/partial -> official single-token prices-history; candidate logic unchanged"
    base.OUT_SUMMARY.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
raise SystemExit(rc)

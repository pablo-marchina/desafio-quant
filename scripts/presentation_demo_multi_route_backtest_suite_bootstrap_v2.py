#!/usr/bin/env python3
"""Bootstrap presentation/demo multi-route backtest v2.2.

Loads the byte-validated v2.1 payload, then applies a small runtime policy layer:
Kalshi live-tier observations remain supported/diagnostic, but only archived
historical-tier markets enter the default retrospective score for reproducibility.
"""
from __future__ import annotations

import gzip
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "scripts" / "_payloads" / "presentation_demo_multi_route_backtest_suite_v2.py.gz"
GENERATED = ROOT / "scripts" / ".generated_presentation_demo_multi_route_backtest_suite_v2.py"

source = gzip.decompress(PAYLOAD.read_bytes()).decode("utf-8")
compile(source, str(GENERATED), "exec")
GENERATED.write_text(source, encoding="utf-8")

mod: dict[str, Any] = {
    "__name__": "argos_multi_route_v21_payload",
    "__file__": str(GENERATED),
}
exec(compile(source, str(GENERATED), "exec"), mod, mod)

NS = mod["NS"]
MAX_KALSHI = int(mod["MAX_KALSHI"])
INCLUDE_LIVE = os.getenv("ARGOS_MULTI_KALSHI_INCLUDE_LIVE_PROVISIONAL", "0") == "1"


def run_kalshi_route_v22():
    cutoff_ts, cutoff_err = mod["_kalshi_cutoff"]()
    candidates, universe_stats, universe_errs = mod["_w4b_kalshi_candidates"](cutoff_ts)

    # v2.1 returns at most MAX_KALSHI. This is enough to validate the stable
    # policy while keeping its frozen candidate order and avoiding outcome-based
    # reselection. No price/PnL field participates in this gate.
    enriched: list[dict[str, Any]] = []
    detail_errors: list[str] = []
    for m in candidates:
        em, err = mod["_kalshi_detail"](m, cutoff_ts)
        if err and len(detail_errors) < 10:
            detail_errors.append(f"{m.get('ticker')}:{err}")
        if em.get("terminal_yes_price") is not None:
            enriched.append(em)

    historical_ready = [m for m in enriched if m.get("data_tier") == "historical"]
    live_provisional = [m for m in enriched if m.get("data_tier") == "live"]
    score_markets = list(historical_ready)
    if INCLUDE_LIVE:
        score_markets.extend(live_provisional)
    score_markets = score_markets[:MAX_KALSHI]

    route_trades: list[dict[str, Any]] = []
    hist_n = 0
    hist_by_tier: dict[str, int] = defaultdict(int)
    err_samples: list[str] = (universe_errs + detail_errors)[:6]
    if cutoff_err:
        err_samples.append(f"cutoff:{cutoff_err}")

    for m in score_markets:
        hist, err, used_tier = mod["_kalshi_history"](m)
        if hist:
            hist_n += 1
            hist_by_tier[used_tier] += 1
        elif err and len(err_samples) < 14:
            err_samples.append(f"{m.get('ticker')}[{m.get('data_tier')}]: {err}")
        tr = NS["trade_from_history"]("PM_KALSHI_CONTRACT_PNL", m, hist)
        if tr:
            tr["data_tier"] = used_tier
            tr["price_source"] = "kalshi_candlesticks_60m_w4b_universe"
            route_trades.append(tr)

    funnels = [
        {"route_id": "PM_KALSHI_CONTRACT_PNL", "stage": "historical_cutoff_resolved", "count": int(cutoff_ts is not None), "notes": str(cutoff_ts or cutoff_err or "")},
        {"route_id": "PM_KALSHI_CONTRACT_PNL", "stage": "w4b_distributional_core_events", "count": int(universe_stats.get("distributional_core_events", 0)), "notes": json.dumps(universe_stats, sort_keys=True)},
        {"route_id": "PM_KALSHI_CONTRACT_PNL", "stage": "candidate_markets", "count": len(candidates), "notes": "pre-audited W4-B distributional-core universe; no price/outcome/PnL used for selection"},
        {"route_id": "PM_KALSHI_CONTRACT_PNL", "stage": "settlement_detail_resolved", "count": len(enriched), "notes": f"detail_errors={len(detail_errors)}"},
        {"route_id": "PM_KALSHI_CONTRACT_PNL", "stage": "live_provisional_excluded", "count": 0 if INCLUDE_LIVE else len(live_provisional), "notes": "default reproducibility gate; live tier is diagnostic-only until archived"},
        {"route_id": "PM_KALSHI_CONTRACT_PNL", "stage": "score_markets", "count": len(score_markets), "notes": f"historical_ready={len(historical_ready)}; include_live={INCLUDE_LIVE}"},
        {"route_id": "PM_KALSHI_CONTRACT_PNL", "stage": "candlestick_history_returned", "count": hist_n, "notes": f"historical={hist_by_tier.get('historical',0)}; live={hist_by_tier.get('live',0)}; interval=60m; " + "; ".join(err_samples[:3])},
        {"route_id": "PM_KALSHI_CONTRACT_PNL", "stage": "trade_rows_materialized", "count": len(route_trades), "notes": "tier-specific endpoint; 60m candles anchored to frozen W4-B operational T0"},
        {"route_id": "PM_KALSHI_CONTRACT_PNL", "stage": "executed_threshold_trades", "count": sum(t.get("side") in {"BUY_YES", "BUY_NO"} for t in route_trades), "notes": f"BUY_YES >= {NS['TH_YES']}; BUY_NO <= {NS['TH_NO']}"},
    ]

    summary = NS["summarize_route"](
        "PM_KALSHI_CONTRACT_PNL", route_trades, len(score_markets), hist_n, "; ".join(err_samples[:3])
    )
    summary.update({
        "market_cutoff_ts": cutoff_ts,
        "history_by_tier": dict(hist_by_tier),
        "w4b_universe_stats": universe_stats,
        "settlement_detail_resolved": len(enriched),
        "historical_ready": len(historical_ready),
        "live_provisional_excluded": 0 if INCLUDE_LIVE else len(live_provisional),
        "include_live_provisional": INCLUDE_LIVE,
        "candidate_selection": "W4-B distributional-core availability universe; no economic-field ranking",
        "reproducibility_gate": "default score includes historical tier only; live tier remains supported but provisional",
    })
    return summary, route_trades, funnels


NS["run_kalshi_route"] = run_kalshi_route_v22
rc = int(mod["main"]())

summary_path: Path = NS["SUMMARY"]
if summary_path.exists():
    doc = json.loads(summary_path.read_text(encoding="utf-8"))
    doc["version"] = "v2.2"
    doc.setdefault("v2_changes", {})["kalshi_reproducibility"] = (
        "default retrospective score excludes live-tier Kalshi markets; live routing remains supported for diagnostics until archival"
    )
    doc.setdefault("parameters", {})["kalshi_include_live_provisional"] = INCLUDE_LIVE
    summary_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

raise SystemExit(rc)

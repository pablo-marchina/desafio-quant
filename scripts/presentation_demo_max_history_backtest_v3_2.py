#!/usr/bin/env python3
"""v3.2 quality wrapper for the complete max-history backtest.

Scientific/candidate logic remains v3; Polymarket transport recovery remains
v3.1. This layer fixes an execution-quality issue found by post-run audit:
ForecastEx daily Prices CSV rows where both Yes and No close at zero are not
interpreted as free executable contracts. A ForecastEx trade row is scoreable
only when both actual side prices are positive and their sum is economically
coherent (0.90..1.10). Raw history/settlement coverage is still reported.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V31 = ROOT / "scripts" / "presentation_demo_max_history_backtest_v3_1.py"
src = V31.read_text(encoding="utf-8")

needle = 'base.run_polymarket = run_polymarket_v31\nrc = int(base.main())\n'
if src.count(needle) != 1:
    raise SystemExit(f"v31_patch_identity_failure:{src.count(needle)}")

replacement = r'''base.run_polymarket = run_polymarket_v31

_original_forecastex = base.run_forecastex_via_v2

def run_forecastex_v32():
    old_summary, raw_trades, old_funnels, errors = _original_forecastex()
    valid = []
    excluded = []
    for t in raw_trades:
        y = base.fnum(t.get("entry_yes_price"))
        n = base.fnum(t.get("entry_no_price"))
        coherent = (
            y is not None and n is not None and
            y > 0.0 and n > 0.0 and
            0.90 <= (y + n) <= 1.10
        )
        if coherent:
            valid.append(t)
        else:
            excluded.append(t)
            errors.append({
                "route_id": "FORECASTEX_EVENT_CONTRACTS",
                "canonical_event_id": t.get("canonical_event_id", ""),
                "stage": "non_executable_quote_pair",
                "error": f"entry_yes={y};entry_no={n};sum={(y+n) if y is not None and n is not None else None}",
            })

    summary = base.summarize(
        "FORECASTEX_EVENT_CONTRACTS", "FORECASTEX",
        int(old_summary.get("markets_considered") or 0),
        int(old_summary.get("history_returned") or 0),
        valid,
        {
            "canonical_universe": old_summary.get("canonical_universe"),
            "contract_identifier_rows": old_summary.get("contract_identifier_rows"),
            "complete_yes_no_pairs_selected": old_summary.get("complete_yes_no_pairs_selected"),
            "official_archive_dates_fetched": old_summary.get("official_archive_dates_fetched"),
            "settlement_resolved_raw": old_summary.get("settlement_resolved"),
            "raw_trade_rows_before_execution_gate": len(raw_trades),
            "non_executable_quote_pairs_excluded": len(excluded),
            "fee_per_executed_contract": old_summary.get("fee_per_executed_contract", 0.01),
            "entry_quote_gate": "actual Yes>0 and No>0 and 0.90<=Yes+No<=1.10",
            "candidate_selection": old_summary.get("candidate_selection"),
        },
    )
    funnels = []
    for row in old_funnels:
        if row.get("stage") in {"trade_rows_materialized", "executed_threshold_trades"}:
            continue
        funnels.append(row)
    funnels.extend([
        {
            "route_id": "FORECASTEX_EVENT_CONTRACTS",
            "stage": "raw_settlement_trade_rows",
            "count": len(raw_trades),
            "notes": "before execution-quality quote gate",
        },
        {
            "route_id": "FORECASTEX_EVENT_CONTRACTS",
            "stage": "non_executable_quote_pairs_excluded",
            "count": len(excluded),
            "notes": "both-side zero/malformed or incoherent actual closing pair; never treated as free executable contract",
        },
        {
            "route_id": "FORECASTEX_EVENT_CONTRACTS",
            "stage": "trade_rows_materialized",
            "count": len(valid),
            "notes": "actual positive Yes/No closes with 0.90<=Yes+No<=1.10",
        },
        {
            "route_id": "FORECASTEX_EVENT_CONTRACTS",
            "stage": "executed_threshold_trades",
            "count": summary["executed_trades"],
            "notes": f"YES>={base.TH_YES}; NO signal when YES<={base.TH_NO}; fee=${summary.get('fee_per_executed_contract',0.01)}",
        },
    ])
    return summary, valid, funnels, errors

base.run_forecastex_via_v2 = run_forecastex_v32
rc = int(base.main())
'''
src = src.replace(needle, replacement, 1)
src = src.replace('doc["version"] = "v3.1"', 'doc["version"] = "v3.2"', 1)
src = src.replace(
    'doc.setdefault("transport_recoveries", {})["polymarket"] = "batch 400/partial -> official single-token prices-history; candidate logic unchanged"',
    'doc.setdefault("transport_recoveries", {})["polymarket"] = "batch 400/partial -> official single-token prices-history; candidate logic unchanged"\n    doc.setdefault("execution_quality_gates", {})["forecastex"] = "actual Yes>0 and No>0 and 0.90<=Yes+No<=1.10; zero quote pairs excluded from scoring"',
    1,
)

exec(compile(src, str(V31) + "[v3.2-forecastex-execution-gate]", "exec"), {"__name__": "__main__", "__file__": str(V31)})

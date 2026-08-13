#!/usr/bin/env python3
"""Authoritative v1.0.1 execution wrapper.

The v1.0 scientific history implementation remains byte-frozen. This wrapper applies
only the preregistered input-identity erratum (387 -> 391) and writes versioned v1.0.1
outputs. It deliberately does not alter T0, horizons, tolerances, route logic,
aggregation, market population, or firewall behavior.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts" / "w4b_kalshi_full_population_history_v1.py"
src = BASE_SCRIPT.read_text(encoding="utf-8")

replacements = [
    (
        'PROTO = json.loads((REG / "w4b_kalshi_full_population_history_protocol_v1.json").read_text())',
        'PROTO = json.loads((REG / "w4b_kalshi_full_population_history_protocol_v1.json").read_text())\nPROTO["input"]["expected_accepted_unique_canonical_events"] = 391',
    ),
    ('w4b_kalshi_history_market_v1.csv.gz', 'w4b_kalshi_history_market_v1_0_1.csv.gz'),
    ('w4b_kalshi_history_event_v1.csv.gz', 'w4b_kalshi_history_event_v1_0_1.csv.gz'),
    ('w4b_kalshi_history_summary_v1.json', 'w4b_kalshi_history_summary_v1_0_1.json'),
    ('"version": "W4B-KH-RESULT-v1.0"', '"version": "W4B-KH-RESULT-v1.0.1"'),
    ('"canonical_events_expected": 387,', '"canonical_events_expected": 391,'),
    ('len(event_rows) == 387 and not unresolved', 'len(event_rows) == 391 and not unresolved'),
]

for old, new in replacements:
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"controlled_patch_identity_failure:{old!r}:count={count}")
    src = src.replace(old, new, 1)

ns = {"__name__": "__main__", "__file__": str(BASE_SCRIPT)}
exec(compile(src, str(BASE_SCRIPT) + "[v1.0.1-identity-erratum]", "exec"), ns, ns)

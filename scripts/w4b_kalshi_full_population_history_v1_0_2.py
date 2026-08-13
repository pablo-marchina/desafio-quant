#!/usr/bin/env python3
"""Authoritative W4-B history v1.0.2 transport-recovery wrapper.

Scientific logic remains byte-frozen in w4b_kalshi_full_population_history_v1.py.
This wrapper applies the already-recorded 391-event identity erratum and transport-only
recovery: lower concurrency plus two serial retries for requests that remain
API_UNRESOLVED. T0, horizons, staleness, route semantics, aggregation and gates do not change.
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
    ('with ThreadPoolExecutor(max_workers=8) as ex:', 'with ThreadPoolExecutor(max_workers=4) as ex:'),
    ('w4b_kalshi_history_market_v1.csv.gz', 'w4b_kalshi_history_market_v1_0_2.csv.gz'),
    ('w4b_kalshi_history_event_v1.csv.gz', 'w4b_kalshi_history_event_v1_0_2.csv.gz'),
    ('w4b_kalshi_history_summary_v1.json', 'w4b_kalshi_history_summary_v1_0_2.json'),
    ('"version": "W4B-KH-RESULT-v1.0"', '"version": "W4B-KH-RESULT-v1.0.2"'),
    ('"canonical_events_expected": 387,', '"canonical_events_expected": 391,'),
    ('len(event_rows) == 387 and not unresolved', 'len(event_rows) == 391 and not unresolved'),
]

for old, new in replacements:
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"controlled_patch_identity_failure:{old!r}:count={count}")
    src = src.replace(old, new, 1)

marker = '    market_rows = []\n'
if src.count(marker) != 1:
    raise SystemExit(f"controlled_recovery_insertion_failure:count={src.count(marker)}")
recovery = '''    # v1.0.2 transport-only recovery: retry only API_UNRESOLVED requests.\n    for recovery_round in (1, 2):\n        targets = [\n            (key, value)\n            for key, value in sorted(fetched.items())\n            if value[3].get("http_resolution_status") == "API_UNRESOLVED"\n        ]\n        print(f"transport_recovery_round={recovery_round} unresolved_before={len(targets)}", flush=True)\n        if not targets:\n            break\n        for recovery_idx, ((cid, ticker), (series, start, t0, _old_res)) in enumerate(targets, 1):\n            time.sleep(0.35)\n            res2 = fetch_candles(series, ticker, start, t0)\n            fetched[(cid, ticker)] = (series, start, t0, res2)\n            if recovery_idx % 25 == 0:\n                print(f"transport_recovery_round={recovery_round} processed={recovery_idx}/{len(targets)}", flush=True)\n\n'''
src = src.replace(marker, recovery + marker, 1)

ns = {"__name__": "__main__", "__file__": str(BASE_SCRIPT)}
exec(compile(src, str(BASE_SCRIPT) + "[v1.0.2-transport-recovery]", "exec"), ns, ns)

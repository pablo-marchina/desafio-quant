#!/usr/bin/env python3
"""ForecastEx census v1.0.1 sequence-only wrapper.

The frozen ForecastEx census science remains in w4b_forecastex_census_v1.py.
This wrapper updates only the predecessor closeout/version from failed Kalshi
history v1.0.2 to authoritative transport-repaired v1.0.3.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / 'scripts' / 'w4b_forecastex_census_v1.py'
src = BASE_SCRIPT.read_text(encoding='utf-8')
old_proto = "PROTO = json.loads((REG / 'w4b_forecastex_census_protocol_v1.json').read_text())"
new_proto = old_proto + "\nPROTO['sequence_prerequisite']['required_history_version']='W4B-KH-RESULT-v1.0.3'\nPROTO['sequence_prerequisite']['required_history_api_unresolved_count']=0"
old_close = "closeout_path = REG / 'w4b_kalshi_history_closeout_v1_0_2.json'"
new_close = "closeout_path = REG / 'w4b_kalshi_history_closeout_v1_0_3.json'"
for old,new in ((old_proto,new_proto),(old_close,new_close)):
    if src.count(old) != 1:
        raise SystemExit(f'controlled_forecastex_sequence_patch_failure:{old!r}:count={src.count(old)}')
    src = src.replace(old,new,1)
ns={'__name__':'__main__','__file__':str(BASE_SCRIPT)}
exec(compile(src,str(BASE_SCRIPT)+'[v1.0.1-history-sequence-update]','exec'),ns,ns)

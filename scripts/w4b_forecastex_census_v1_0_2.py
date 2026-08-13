#!/usr/bin/env python3
"""ForecastEx census v1.0.2 authoritative pre-result wrapper.

The base W4B-FX-C-v1.0 census logic remains frozen. This wrapper applies the
pre-result sequence update to Kalshi history v1.0.3 and the pre-result archive
recall amendment that probes every calendar day through UTC D-1 rather than
stopping at the latest date rendered by the ForecastEx data-page UI.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / 'scripts' / 'w4b_forecastex_census_v1.py'
src = BASE_SCRIPT.read_text(encoding='utf-8')
patches = [
    (
        "PROTO = json.loads((REG / 'w4b_forecastex_census_protocol_v1.json').read_text())",
        "PROTO = json.loads((REG / 'w4b_forecastex_census_protocol_v1.json').read_text())\nPROTO['sequence_prerequisite']['required_history_version']='W4B-KH-RESULT-v1.0.3'\nPROTO['sequence_prerequisite']['required_history_api_unresolved_count']=0"
    ),
    (
        "closeout_path = REG / 'w4b_kalshi_history_closeout_v1_0_2.json'",
        "closeout_path = REG / 'w4b_kalshi_history_closeout_v1_0_3.json'"
    ),
    (
        "latest = max(displayed)",
        "latest = datetime.now(timezone.utc).date() - timedelta(days=1)"
    ),
]
for old,new in patches:
    count=src.count(old)
    if count != 1:
        raise SystemExit(f'controlled_forecastex_v1_0_2_patch_failure:{old!r}:count={count}')
    src=src.replace(old,new,1)
ns={'__name__':'__main__','__file__':str(BASE_SCRIPT)}
exec(compile(src,str(BASE_SCRIPT)+'[v1.0.2-sequence-and-calendar-completeness]','exec'),ns,ns)

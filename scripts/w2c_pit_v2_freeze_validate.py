#!/usr/bin/env python3
"""Byte-freeze validator for W2C-PIT-v2.0. No network access."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path

MANIFEST=Path('registry/w2c_pit_v2_freeze_manifest.json')
REAL_OUTPUTS=[
 'registry/w2c_pit_v2_platform_events.csv.gz',
 'registry/w2c_pit_v2_platform_request_manifest.jsonl.gz',
 'registry/w2c_pit_v2_platform_summary.json',
 'registry/w2c_pit_v2_combined_events.csv',
 'registry/w2c_pit_v2_family_gates.json',
 'registry/w2c_ias_scores.csv',
]

def blob(path):
    return subprocess.check_output(['git','rev-parse',f'HEAD:{path}'],text=True).strip()

def run(cmd): subprocess.run(cmd,check=True)

def main():
    m=json.loads(MANIFEST.read_text())
    assert m['version']=='W2C-PIT-FREEZE-v2.0'
    assert m['performance_blind'] is True and m['science_reopened'] is False
    assert m['network_collection_authorized'] is False
    assert m['f1_f9_execution_authorized'] is False
    assert m['ias_execution_authorized'] is False
    assert m['w3_execution_authorized'] is False
    observed={}
    for path,expected in m['frozen_git_blobs'].items():
        got=blob(path); observed[path]=got; assert got==expected,(path,got,expected)
    canonical=''.join(f'{p}\t{observed[p]}\n' for p in sorted(observed))
    digest=hashlib.sha256(canonical.encode()).hexdigest()
    assert digest==m['bundle_sha256'],(digest,m['bundle_sha256'])
    assert blob(m['population']['path'])==m['population']['git_blob_sha1']
    assert not any(Path(x).exists() for x in REAL_OUTPUTS), 'real PIT/F1-F9/IAS output exists before authorization'
    # Static firewall on real collectors/scorer only; synthetic tests intentionally mention forbidden examples.
    forbidden=('registry/w2a_results','registry/art030','data/art030','active_terminal_wealth','linked_asset_realized_return')
    for path in ['scripts/w2c_pit_v2_platform_collect.py','scripts/w2c_pit_v2_primary_queue.py','scripts/w2c_pit_v2_gate_score.py']:
        text=Path(path).read_text().lower()
        for token in forbidden: assert token.lower() not in text,(path,token)
    run(['python','scripts/w2c_pit_v2_population_validate.py'])
    run(['python','scripts/w2c_pit_v2_synthetic_validation.py'])
    run(['python','scripts/w2c_pit_v2_pipeline_synthetic.py'])
    run(['python','scripts/w2c_pit_v2_primary_queue.py'])
    assert not Path('registry/w2c_pit_v2_family_gates.json').exists()
    assert not Path('registry/w2c_ias_scores.csv').exists()
    print(json.dumps({'artifact':'W2C_PIT_V2_FREEZE_VALIDATION','version':'W2C-PIT-FREEZE-VAL-v2.0','status':'PASS','bundle_sha256':digest,'frozen_files':len(observed),'network_called':False,'performance_blind':True,'science_reopened':False},indent=2))
if __name__=='__main__': main()

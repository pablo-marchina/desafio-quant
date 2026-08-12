#!/usr/bin/env python3
"""Validate exact PIT-v2.1 Layer B/C + combined evidence before F1-F9."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path('.')
MANIFEST = ROOT / 'registry/w2c_pit_v2_1_evidence_freeze.json'


def git_blob(path: str) -> str:
    return subprocess.check_output(['git','rev-parse',f'HEAD:{path}'], text=True).strip()


def main() -> None:
    m=json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert m['artifact']=='W2C_PIT_V2_1_EVIDENCE_FREEZE'
    assert m['version']=='W2C-PIT-EVIDENCE-FREEZE-v2.1'
    assert m['science_reopened'] is False and m['performance_blind'] is True
    assert m['source_execution']=={
        'workflow_run_id':31643971392,
        'workflow_conclusion':'success',
        'evidence_branch':'w2c-pit-v2-1-layer-bc-results',
        'evidence_commit':'5b96f8b2adaa154cc1d82d95bb332139581da41e'}
    assert m['requires_scientific_bundle_sha256']=='741ab5985bbf34c454cc8050bbecb001123ecf3110ba1bb5e9f5cab079da4a68'
    assert all(v is False for v in m['authorization'].values())
    assert m['observed_state_is_not_gate_result'] is True

    actual={}
    for path,expected in sorted(m['objects'].items()):
        got=git_blob(path); actual[path]=got
        assert got==expected,f'EVIDENCE_BLOB_MISMATCH {path}: {got} != {expected}'
    assert len(actual)==6
    payload=''.join(f'{p}\t{actual[p]}\n' for p in sorted(actual))
    digest=hashlib.sha256(payload.encode()).hexdigest()
    assert digest==m['evidence_bundle_sha256']=='d73591e1fc511313b0c36f34d0abe14e483d11d98efa3beeebed932b21a0bb84'

    q=list(csv.DictReader(open('registry/w2c_pit_v2_1_primary_source_queue.csv',encoding='utf-8',newline='')))
    with gzip.open('registry/w2c_pit_v2_1_primary_asset_events.csv.gz','rt',encoding='utf-8',newline='') as fh:
        p=list(csv.DictReader(fh))
    c=list(csv.DictReader(open('registry/w2c_pit_v2_1_combined_events.csv',encoding='utf-8',newline='')))
    for name,rows in [('queue',q),('primary',p),('combined',c)]:
        assert len(rows)==260,f'{name} rows={len(rows)}'
        assert len({r['event_id'] for r in rows})==260,f'{name} duplicate event_id'
    assert {r['event_id'] for r in q}=={r['event_id'] for r in p}=={r['event_id'] for r in c}

    ps=json.load(open('registry/w2c_pit_v2_1_primary_asset_summary.json'))
    cs=json.load(open('registry/w2c_pit_v2_1_combined_summary.json'))
    assert ps['rows']==cs['rows']==260
    assert ps['performance_blind'] is True and cs['performance_blind'] is True
    assert ps['science_reopened'] is False and cs['science_reopened'] is False
    assert ps['f1_f9_scored'] is False and cs['f1_f9_scored'] is False
    assert ps['ias_computed'] is False and cs['ias_computed'] is False
    assert ps['smaa_computed'] is False and cs['smaa_computed'] is False
    assert ps['w3_selected'] is False and cs['w3_selected'] is False
    assert ps['linked_asset_movement_values_persisted'] is False

    forbidden_exact={'return','realized_return','abnormal_return','pnl','beta','correlation','event_response'}
    cols={x.strip().lower() for x in c[0]}
    assert not (cols & forbidden_exact),f'PERFORMANCE_COLUMNS {sorted(cols & forbidden_exact)}'
    assert not Path('registry/w2c_pit_v2_1_family_gates.json').exists(),'F1-F9 already executed before evidence freeze'
    assert not Path('registry/w2c_ias_scores.csv').exists(),'IAS already executed before evidence freeze'
    assert not Path('registry/w2c_smaa_ranking.json').exists(),'SMAA already executed before evidence freeze'

    # Revalidate upstream scientific byte freeze and immutable Layer A identities.
    subprocess.run(['python','scripts/w2c_pit_v2_1_freeze_validate.py'],check=True)
    subprocess.run(['python','scripts/repository_hygiene_validate.py'],check=True)

    print(json.dumps({
        'artifact':'W2C_PIT_V2_1_EVIDENCE_FREEZE_VALIDATION',
        'version':'W2C-PIT-EVIDENCE-FREEZE-VALIDATION-v2.1',
        'status':'PASS',
        'evidence_bundle_sha256':digest,
        'object_count':6,
        'rows':260,
        'performance_blind':True,
        'science_reopened':False,
        'f1_f9_real_execution_authorized':False,
        'ias_real_scoring_authorized':False,
        'smaa_ranking_authorized':False,
        'w3_execution_authorized':False
    },indent=2))

if __name__=='__main__': main()

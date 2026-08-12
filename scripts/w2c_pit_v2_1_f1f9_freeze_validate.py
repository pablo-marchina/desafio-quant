#!/usr/bin/env python3
"""Validate exact PIT-v2.1 F1-F9 result before IAS."""
from __future__ import annotations
import json, subprocess
from pathlib import Path

M=Path('registry/w2c_pit_v2_1_f1f9_freeze.json')
R=Path('registry/w2c_pit_v2_1_family_gates.json')

def blob(path): return subprocess.check_output(['git','rev-parse',f'HEAD:{path}'],text=True).strip()

def main():
    m=json.loads(M.read_text()); z=json.loads(R.read_text())
    assert m['artifact']=='W2C_PIT_V2_1_F1_F9_FREEZE'
    assert m['version']=='W2C-PIT-F1F9-FREEZE-v2.1'
    assert m['science_reopened'] is False and m['performance_blind'] is True
    assert blob(m['result_path'])==m['result_blob_sha1']=='1dfbc01fe7bebfc6c2a1b09037285fef8159fbaa'
    assert z['artifact']=='W2C_PIT_V2_1_F1_F9_RESULTS'
    assert z['version']=='W2C-PIT-F1F9-v2.1'
    assert z['protocol']=='W2C-PIT-v2.1' and z['gate_contract']=='W2C-PIT-GATES-v2.1'
    assert z['performance_blind'] is True and z['science_reopened'] is False
    assert z['ias_execution_authorized'] is False and z['smaa_execution_authorized'] is False and z['w3_execution_authorized'] is False
    assert set(z['families'])==set(m['families'])
    for fam in m['families']:
        r=z['families'][fam]
        assert r['overall_feasibility']==m['frozen_family_overall_feasibility'][fam]=='NO_GO_CURRENT_PROTOCOL'
        assert all(r['gates'][g]=='FAIL' for g in m['confirmed_shared_failures'])
        assert set(r['gates'])=={f'F{i}' for i in range(1,10)}
    assert all(v is False for v in m['authorization'].values())
    # Revalidate all upstream evidence/scientific identities.
    subprocess.run(['python','scripts/w2c_pit_v2_1_evidence_freeze_validate.py'],check=True)
    subprocess.run(['python','scripts/repository_hygiene_validate.py'],check=True)
    print(json.dumps({'artifact':'W2C_PIT_V2_1_F1_F9_FREEZE_VALIDATION','version':'W2C-PIT-F1F9-FREEZE-VALIDATION-v2.1','status':'PASS','result_blob_sha1':m['result_blob_sha1'],'families':m['families'],'shared_confirmed_failures':m['confirmed_shared_failures'],'performance_blind':True,'science_reopened':False,'ias_real_scoring_authorized':False,'smaa_ranking_authorized':False,'w3_execution_authorized':False},indent=2))
if __name__=='__main__': main()

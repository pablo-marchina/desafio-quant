#!/usr/bin/env python3
"""Validate exact PIT-v2.1 F1-F9 result before IAS.

This is a post-F1 lifecycle validator. It revalidates immutable upstream
scientific/evidence identities directly; it intentionally does not invoke the
pre-F1 evidence-freeze validator whose safety contract requires the F1-F9
result file to be absent.
"""
from __future__ import annotations
import json, subprocess
from pathlib import Path

M=Path('registry/w2c_pit_v2_1_f1f9_freeze.json')
R=Path('registry/w2c_pit_v2_1_family_gates.json')
E=Path('registry/w2c_pit_v2_1_evidence_freeze.json')
EV=Path('registry/w2c_pit_v2_1_evidence_freeze_validation.json')
S=Path('registry/w2c_pit_v2_1_freeze_manifest.json')

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

    # Post-F1 upstream identity validation. Do not call the pre-F1 evidence
    # validator because that validator correctly asserts the result file is absent.
    e=json.loads(E.read_text()); ev=json.loads(EV.read_text()); s=json.loads(S.read_text())
    SCI='741ab5985bbf34c454cc8050bbecb001123ecf3110ba1bb5e9f5cab079da4a68'
    EVID='d73591e1fc511313b0c36f34d0abe14e483d11d98efa3beeebed932b21a0bb84'
    assert s['bundle_sha256']==m['requires_scientific_bundle_sha256']==SCI
    assert e['requires_scientific_bundle_sha256']==SCI
    assert e['evidence_bundle_sha256']==m['requires_evidence_bundle_sha256']==ev['evidence_bundle_sha256']==EVID
    assert ev['evidence_freeze_workflow_run_id']==31644613489
    assert ev['evidence_freeze_conclusion']=='success'
    assert ev['repository_hygiene_conclusion']=='success'
    assert ev['combined_events_blob']=='879100adffa7df88b518ed062d88c4c30662f91d'
    assert len(e['objects'])==6
    for path, expected in sorted(e['objects'].items()):
        assert blob(path)==expected, f'UPSTREAM_EVIDENCE_BLOB_MISMATCH {path}'
    assert blob('registry/w2c_pit_v2_1_combined_events.csv')==ev['combined_events_blob']

    # The original scientific byte freeze remains independently reproducible
    # post-F1; it does not depend on absence of result artifacts.
    subprocess.run(['python','scripts/w2c_pit_v2_1_freeze_validate.py'],check=True)
    subprocess.run(['python','scripts/repository_hygiene_validate.py'],check=True)
    print(json.dumps({'artifact':'W2C_PIT_V2_1_F1_F9_FREEZE_VALIDATION','version':'W2C-PIT-F1F9-FREEZE-VALIDATION-v2.1','status':'PASS','result_blob_sha1':m['result_blob_sha1'],'scientific_bundle_sha256':SCI,'evidence_bundle_sha256':EVID,'upstream_evidence_objects_verified':6,'families':m['families'],'shared_confirmed_failures':m['confirmed_shared_failures'],'performance_blind':True,'science_reopened':False,'ias_real_scoring_authorized':False,'smaa_ranking_authorized':False,'w3_execution_authorized':False},indent=2))
if __name__=='__main__': main()

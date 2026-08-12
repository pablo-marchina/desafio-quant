#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess
from pathlib import Path
R=Path('.')
def blob(p):return subprocess.check_output(['git','rev-parse',f'HEAD:{p}'],text=True).strip()
def main():
 f=json.loads((R/'registry/w2b_ias_smaa_result_freeze_v1_0.json').read_text())
 got=blob(f['result']['path'])
 if got!=f['result']['git_blob_sha1']:raise SystemExit(f'result blob mismatch {got}')
 x=json.loads((R/f['result']['path']).read_text())
 assert x['artifact']=='W2B_IAS_SMAA_RESULTS'
 assert x['samples']==200000 and x['seed']==20260812
 assert x['performance_blind'] is True and x['f1_f9_read'] is False and x['w3_decision_computed'] is False
 c=x['comparative_claim'];o=f['comparative_claim_observed']
 for k in ['label','leader','leader_rank1','runnerup','runnerup_rank1','margin','permitted']:assert c[k]==o[k],(k,c[k],o[k])
 assert c['permitted'] is False and c['leader_rank1']<0.50
 print(json.dumps({'artifact':'W2B_IAS_SMAA_RESULT_FREEZE_VALIDATION','status':'PASS','result_blob':got,'families':len(x['families']),'samples':x['samples'],'comparative_claim':c},indent=2))
if __name__=='__main__':main()

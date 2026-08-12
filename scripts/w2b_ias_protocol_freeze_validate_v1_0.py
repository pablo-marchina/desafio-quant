#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
R=Path('.')
M=R/'registry/w2b_ias_protocol_freeze_v1_0.json'
def blob(p):return subprocess.check_output(['git','rev-parse',f'HEAD:{p}'],text=True).strip()
def main():
 m=json.loads(M.read_text()); lines=[]
 for p,sha in sorted(m['frozen_objects'].items()):
  got=blob(p)
  if got!=sha: raise SystemExit(f'blob mismatch {p}: {got} != {sha}')
  lines.append(f'{p}:{got}\n')
 digest=hashlib.sha256(''.join(lines).encode()).hexdigest()
 if digest!=m['bundle_sha256']: raise SystemExit(f'bundle mismatch {digest}')
 if m['execution_authorized'] is not False: raise SystemExit('freeze must not authorize real scoring')
 for p in ['registry/w2b_ias_evidence_matrix_v1.csv','registry/w2b_ias_smaa_results_v1.json','registry/w2b_ias_execution_authorization_v1.json']:
  if Path(p).exists(): raise SystemExit(f'real artifact existed before freeze: {p}')
 print(json.dumps({'artifact':'W2B_IAS_PROTOCOL_FREEZE_VALIDATION','status':'PASS','bundle_sha256':digest,'frozen_objects':len(lines),'real_scoring_authorized':False},indent=2))
if __name__=='__main__':main()

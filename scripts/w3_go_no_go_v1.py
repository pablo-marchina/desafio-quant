#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess
from pathlib import Path
R=Path('.')
IAS=R/'registry/w2b_ias_smaa_results_v1.json'
PIT=R/'registry/w2c_pit_v2_1_family_gates.json'
C=R/'registry/w3_go_no_go_contract_v1_0.json'
OUT=R/'registry/w3_go_no_go_result_v1.json'
def blob(p):return subprocess.check_output(['git','rev-parse',f'HEAD:{p.as_posix()}'],text=True).strip()
def evaluate(robust,evidence,pit_state,all_pass):
 if not evidence:return 'NO_GO_STRUCTURAL_EVIDENCE_INCOMPLETE'
 if not robust:
  return 'NO_GO_STRUCTURAL_HIGH_IAS_NOT_ESTABLISHED'
 if pit_state=='NOT_ESTABLISHED':return 'NO_GO_FEASIBILITY_NOT_ESTABLISHED'
 if pit_state=='TESTED' and not all_pass:return 'NO_GO_CURRENT_PROTOCOL'
 if pit_state=='TESTED' and all_pass:return 'W3_GO_CANDIDATE'
 raise ValueError(pit_state)
def main():
 c=json.loads(C.read_text());ias=json.loads(IAS.read_text());pit=json.loads(PIT.read_text())
 assert blob(IAS)==c['inherits']['ias_result_blob'];assert blob(PIT)==c['inherits']['pit_f1_f9_blob']
 rows={};go=[]
 for f,x in sorted(ias['families'].items()):
  mapped=c['pit_exact_family_mapping'].get(f)
  if mapped:
   px=pit['families'][mapped];g=px['gates'];all_pass=all(g[f'F{i}']=='PASS' for i in range(1,10));ps='TESTED'
   pit_summary={'state':'TESTED','mapped_family':mapped,'all_f1_f9_pass':all_pass,'gates':g,'overall_feasibility':px['overall_feasibility']}
  else:
   ps='NOT_ESTABLISHED';all_pass=False;pit_summary={'state':'FEASIBILITY_NOT_ESTABLISHED','mapped_family':None,'all_f1_f9_pass':False}
  d=evaluate(bool(x['robust_high']),bool(x['evidence_gate']),ps,all_pass)
  if d=='W3_GO_CANDIDATE':go.append(f)
  rows[f]={'IAS_central':x['IAS_central'],'P_IAS_ge_3':x['P_IAS_ge_3'],'rank1_acceptability':x['rank1_acceptability'],'evidence_gate':x['evidence_gate'],'robust_high':x['robust_high'],'pit':pit_summary,'decision':d}
 global_decision='GO_W3_PROTOCOL_DRAFTING_ONLY' if go else c['global_decision']['no_go_label']
 out={'artifact':'W3_GO_NO_GO_RESULT','version':'W3-GATE-RESULT-v1.0','science_reopened':False,'performance_blind':True,'ias_result_blob':blob(IAS),'pit_f1_f9_blob':blob(PIT),'comparative_claim':ias['comparative_claim'],'families':rows,'w3_go_candidates':go,'global_decision':global_decision,'w3_execution_authorized':False,'interpretation':'Current protocol/evidence gate only; not proof that structural asymmetry is absent.'}
 OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':'PASS','global_decision':global_decision,'go_candidates':go,'families':len(rows)},indent=2))
if __name__=='__main__':main()

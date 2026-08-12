#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json
from pathlib import Path
R=Path('.')
s=importlib.util.spec_from_file_location('w3',R/'scripts/w3_go_no_go_v1.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
 cases={
  'high_pass_go':m.evaluate(True,True,'TESTED',True)=='W3_GO_CANDIDATE',
  'high_fail_nogo':m.evaluate(True,True,'TESTED',False)=='NO_GO_CURRENT_PROTOCOL',
  'high_unknown_nogo':m.evaluate(True,True,'NOT_ESTABLISHED',False)=='NO_GO_FEASIBILITY_NOT_ESTABLISHED',
  'low_pass_nogo':m.evaluate(False,True,'TESTED',True)=='NO_GO_STRUCTURAL_HIGH_IAS_NOT_ESTABLISHED',
  'incomplete_blocks':m.evaluate(True,False,'TESTED',True)=='NO_GO_STRUCTURAL_EVIDENCE_INCOMPLETE'
 }
 assert all(cases.values()),cases
 c=json.loads((R/'registry/w3_go_no_go_contract_v1_0.json').read_text())
 assert c['no_cross_family_imputation'] and c['no_euas_imputation'] and c['no_nearest_family_proxy']
 assert len(c['pit_exact_family_mapping'])==3 and len(c['pit_not_established_exact_families'])==7
 out={'artifact':'W3_GO_NO_GO_SYNTHETIC','status':'PASS','cases':cases,'real_combination_executed':False,'w3_execution_authorized':False}
 print(json.dumps(out,indent=2))
if __name__=='__main__':main()

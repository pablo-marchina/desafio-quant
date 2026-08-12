#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json
from pathlib import Path
R=Path('.')
s=importlib.util.spec_from_file_location('m',R/'scripts/w2b_ias_score_v1_0.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
c=json.loads((R/'registry/w2b_ias_real_scoring_contract_v1_0.json').read_text())

def make():
 out=[]
 for f in c['taxonomy']:
  for d in m.DIMS: out.append({'family':f,'dimension':d,'anchor':'3','ecg':'A','rationale':'synthetic structural evidence','primary_source_ids':'S1','corroborating_source_ids':'S2','evidence_scope':'synthetic','adjudication_note':'synthetic'})
 return out

def fails(x):
 try:m.validate_input(x,c);return False
 except ValueError:return True

def main():
 cases=[]
 def ok(n,v):assert v,n;cases.append(n)
 x=make();m.validate_input(x,c);ok('complete-grid',len(x)==50)
 y=make();y[0]['anchor']='2.5';ok('integer-anchor',fails(y))
 y=make();y[0]['ecg']='D';y[0]['anchor']='4';ok('D-null-rule',fails(y))
 y=make();y[0]['ecg']='D';y[0]['anchor']='';m.validate_input(y,c);ok('D-unresolved',True)
 e={d:'A' for d in m.DIMS};a={d:4 for d in m.DIMS};ok('central',m.central(a,e)==4)
 ed=dict(e);ed['PAC']='D';ad=dict(a);ad['PAC']=None;ok('D-blocks',m.central(ad,ed) is None and not m.evidence_gate(ed))
 fam={'H':{'anchors':{d:5 for d in m.DIMS},'ecg':e},'L':{'anchors':{d:0 for d in m.DIMS},'ecg':e}}
 z=m.run_smaa(fam,4000,20260812);ok('dominance',z['H']['rank1_acceptability']>.99)
 eq={'A':{'anchors':{d:4 for d in m.DIMS},'ecg':e,'evidence_gate':True},'B':{'anchors':{d:4 for d in m.DIMS},'ecg':e,'evidence_gate':True}}
 q=m.run_smaa(eq,10000,20260812);ok('tie-blocks-claim',not m.comparative(eq,q)['permitted'])
 ok('deterministic',m.run_smaa(fam,300,7)==m.run_smaa(fam,300,7))
 ok('authorization-separated',m.AUTH.name=='w2b_ias_execution_authorization_v1.json' and c['execution_authorized'] is False)
 out={'artifact':'W2B_IAS_SCORER_SYNTHETIC','status':'PASS','cases':len(cases),'real_evidence_read':False,'performance_blind':True,'case_names':cases}
 (R/'registry/w2b_ias_score_synthetic_v1.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()

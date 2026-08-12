#!/usr/bin/env python3
from __future__ import annotations
import csv,importlib.util,json
from pathlib import Path
R=Path('.')
def load(path):
 s=importlib.util.spec_from_file_location('ias',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def ids(v):return [x for x in (v or '').split(';') if x]
def main():
 c=json.loads((R/'registry/w2b_ias_real_scoring_contract_v1_0.json').read_text())
 src=json.loads((R/'registry/w2b_ias_source_registry_v1.json').read_text())['sources']
 rows=list(csv.DictReader((R/'registry/w2b_ias_evidence_matrix_v1.csv').open(encoding='utf-8',newline='')))
 m=load(R/'scripts/w2b_ias_score_v1_0.py');m.validate_input(rows,c)
 unknown=[];unsupported=[]
 for r in rows:
  for sid in ids(r['primary_source_ids'])+ids(r['corroborating_source_ids']):
   if sid not in src: unknown.append((r['family'],r['dimension'],sid));continue
   if r['family'] not in src[sid]['supports']: unsupported.append((r['family'],r['dimension'],sid))
 if unknown: raise SystemExit(f'unknown source ids: {unknown}')
 if unsupported: raise SystemExit(f'source-family mismatch: {unsupported}')
 d=sum(r['ecg']=='D' for r in rows);ab=sum(r['ecg'] in {'A','B'} for r in rows)
 print(json.dumps({'artifact':'W2B_IAS_EVIDENCE_VALIDATION','status':'PASS','rows':len(rows),'families':len({r['family'] for r in rows}),'dimensions':len({r['dimension'] for r in rows}),'ecg_D_rows':d,'ecg_A_or_B_rows':ab,'source_registry_entries':len(src),'real_scoring_executed':False,'f1_f9_read':False,'performance_blind':True},indent=2))
if __name__=='__main__':main()

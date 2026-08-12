#!/usr/bin/env python3
"""Validate/materialize W2C-ADJ-v1.1 decisions; expects exactly 335 initial rows."""
from __future__ import annotations
import csv,gzip,json
from collections import Counter,defaultdict
from pathlib import Path
QUEUE=Path('registry/w2c_semantic_v2_adjudication_queue.csv.gz')
DECISIONS=Path('registry/w2c_semantic_v2_adjudication_decisions_v1_1.csv')
OUT_RESULTS=Path('registry/w2c_semantic_v2_adjudication_results_v1_1.csv')
OUT_ACCEPTED=Path('registry/w2c_semantic_v2_accepted_clusters_v1_1.csv')
OUT_SUMMARY=Path('registry/w2c_semantic_v2_adjudication_summary_v1_1.json')
STATES={'ACCEPT_STRICT_FAMILY','REJECT_FALSE_POSITIVE','AMBIGUOUS_UNRESOLVED'}
PROVISIONAL_POOL={'ANTITRUST_ENFORCEMENT_SINGLE_NAME':1,'CORPORATE_LITIGATION_BINARY':8,'EARNINGS_EPS':1280,'FDA_FINAL_PDUFA_DECISION':63,'FOMC_DECISION':48,'MACRO_STATISTICAL_RELEASE':167,'MA_PENDING_COMPLETION':3,'MA_PRE_ANNOUNCEMENT_OR_RUMOR':12}
def main():
 with gzip.open(QUEUE,'rt',encoding='utf-8',newline='') as fh:q=list(csv.DictReader(fh))
 assert len(q)==335
 with DECISIONS.open(encoding='utf-8',newline='') as fh:d=list(csv.DictReader(fh))
 assert len(d)==335
 qmap={r['event_id']:r for r in q};dmap={r['event_id']:r for r in d};assert len(qmap)==335 and len(dmap)==335 and set(qmap)==set(dmap)
 results=[]
 for eid in sorted(qmap,key=lambda x:(qmap[x]['resolved_family'],qmap[x]['adjudication_rank'])):
  qr=qmap[eid];dr=dmap[eid];state=dr['adjudication_state'];assert state in STATES
  assert dr.get('resolved_family','')==qr['resolved_family'];assert dr.get('independence_cluster_id','')==qr['independence_cluster_id']
  results.append({'event_id':eid,'title':qr['title'],'slug':qr['slug'],'resolved_family':qr['resolved_family'],'independence_cluster_id':qr['independence_cluster_id'],'end_utc':qr['end_utc'],'adjudication_rank':qr['adjudication_rank'],'adjudication_state':state,'adjudication_reason':dr.get('adjudication_reason',''),'adjudication_mode':'MODEL_ASSISTED_OUTCOME_BLIND_SEMANTIC_ADJUDICATION'})
 fields=list(results[0].keys())
 for path,rows in [(OUT_RESULTS,results),(OUT_ACCEPTED,[r for r in results if r['adjudication_state']=='ACCEPT_STRICT_FAMILY'])]:
  with path.open('w',encoding='utf-8',newline='') as fh:w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)
 fam=defaultdict(Counter)
 for r in results:fam[r['resolved_family']][r['adjudication_state']]+=1
 accepted=Counter(r['resolved_family'] for r in results if r['adjudication_state']=='ACCEPT_STRICT_FAMILY')
 initial=Counter(r['resolved_family'] for r in q)
 topup={f:{'accepted':accepted.get(f,0),'initial_rows':initial.get(f,0),'provisional_pool':PROVISIONAL_POOL[f],'required':accepted.get(f,0)<80 and PROVISIONAL_POOL[f]>initial.get(f,0)} for f in sorted(PROVISIONAL_POOL)}
 summary={'artifact':'W2C_SEMANTIC_V2_ADJUDICATION_SUMMARY','version':'W2C-ADJ-RUN-v1.1','protocol_version':'W2C-ADJ-v1.1','performance_blind':True,'science_reopened':False,'input_rows':335,'decision_rows':335,'accepted_total':sum(accepted.values()),'family_decisions':{k:dict(v) for k,v in sorted(fam.items())},'accepted_by_family':dict(sorted(accepted.items())),'top_up_status':topup,'validated_independent_events':sum(accepted.values()),'f1_f9_scored':False,'ias_computed':False,'pit_evidence_collected':False,'linked_asset_realized_returns_read':False,'w3_family_selected':False,'interpretation':'Only ACCEPT_STRICT_FAMILY rows are semantically validated. Top-up is mechanical and hash-ordered; F1-F9 remain unscored.'}
 OUT_SUMMARY.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

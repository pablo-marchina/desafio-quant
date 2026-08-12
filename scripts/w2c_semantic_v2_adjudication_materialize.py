#!/usr/bin/env python3
"""Validate and materialize W2C-ADJ-v1.0 adjudication decisions."""
from __future__ import annotations
import csv,gzip,json
from collections import Counter,defaultdict
from pathlib import Path

QUEUE=Path('registry/w2c_semantic_v2_adjudication_queue.csv.gz')
DECISIONS=Path('registry/w2c_semantic_v2_adjudication_decisions.csv')
OUT_RESULTS=Path('registry/w2c_semantic_v2_adjudication_results.csv')
OUT_ACCEPTED=Path('registry/w2c_semantic_v2_accepted_clusters.csv')
OUT_SUMMARY=Path('registry/w2c_semantic_v2_adjudication_summary.json')
STATES={'ACCEPT_STRICT_FAMILY','REJECT_FALSE_POSITIVE','AMBIGUOUS_UNRESOLVED'}


def main():
    with gzip.open(QUEUE,'rt',encoding='utf-8',newline='') as fh:q=list(csv.DictReader(fh))
    assert len(q)==329
    with DECISIONS.open(encoding='utf-8',newline='') as fh:d=list(csv.DictReader(fh))
    assert len(d)==329
    qmap={r['event_id']:r for r in q}; assert len(qmap)==329
    dmap={r['event_id']:r for r in d}; assert len(dmap)==329 and set(dmap)==set(qmap)
    results=[]
    for eid in sorted(qmap,key=lambda x:(qmap[x]['resolved_family'],qmap[x]['adjudication_rank'])):
        qr=qmap[eid];dr=dmap[eid];state=dr['adjudication_state']
        assert state in STATES
        assert dr.get('resolved_family','')==qr['resolved_family']
        assert dr.get('independence_cluster_id','')==qr['independence_cluster_id']
        results.append({
            'event_id':eid,'title':qr['title'],'slug':qr['slug'],'resolved_family':qr['resolved_family'],
            'independence_cluster_id':qr['independence_cluster_id'],'end_utc':qr['end_utc'],'adjudication_rank':qr['adjudication_rank'],
            'adjudication_state':state,'adjudication_reason':dr.get('adjudication_reason',''),
            'adjudication_mode':'MODEL_ASSISTED_OUTCOME_BLIND_SEMANTIC_ADJUDICATION'
        })
    fields=list(results[0].keys())
    with OUT_RESULTS.open('w',encoding='utf-8',newline='') as fh:w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(results)
    accepted=[r for r in results if r['adjudication_state']=='ACCEPT_STRICT_FAMILY']
    with OUT_ACCEPTED.open('w',encoding='utf-8',newline='') as fh:w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(accepted)
    fam=defaultdict(Counter)
    for r in results:fam[r['resolved_family']][r['adjudication_state']]+=1
    accepted_by_family=Counter(r['resolved_family'] for r in accepted)
    earnings_topup=accepted_by_family.get('EARNINGS_EPS',0)<80
    summary={
      'artifact':'W2C_SEMANTIC_V2_ADJUDICATION_SUMMARY','version':'W2C-ADJ-RUN-v1.0','protocol_version':'W2C-ADJ-v1.0',
      'performance_blind':True,'science_reopened':False,'input_rows':329,'decision_rows':329,'accepted_total':len(accepted),
      'family_decisions':{k:dict(v) for k,v in sorted(fam.items())},'accepted_by_family':dict(sorted(accepted_by_family.items())),
      'earnings_top_up_required':earnings_topup,'validated_independent_events':len(accepted),
      'f1_f9_scored':False,'ias_computed':False,'pit_evidence_collected':False,'linked_asset_realized_returns_read':False,'w3_family_selected':False,
      'interpretation':'Only ACCEPT_STRICT_FAMILY rows are semantically validated. F3 and other feasibility gates are not scored here.'}
    OUT_SUMMARY.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

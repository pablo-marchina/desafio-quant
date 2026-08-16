#!/usr/bin/env python3
from __future__ import annotations

import csv, gzip, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'registry'
QUEUE=REG/'w4c_r1_earnings_ir_queue_v1.csv.gz'
PROTO=REG/'w4c_r1_earnings_ir_discovery_probe_protocol_v1.json'
OUT=REG/'w4c_r1_earnings_ir_probe_sample_v1.json'

SEED='W4C-R1-EIR-DP-v1.0|'

def main():
    p=json.loads(PROTO.read_text(encoding='utf-8'))
    assert p['version']=='W4C-R1-EIR-DP-v1.0.1'
    assert p['pre_amendment_probe_requests_performed'] is False
    with gzip.open(QUEUE,'rt',encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==1355
    ids=sorted((r.get('exact_group_id') or '').strip() for r in rows)
    assert len(set(ids))==1355
    assert hashlib.sha256(('\n'.join(ids)+'\n').encode()).hexdigest()=='c9fd3a13e87ea720e961fa087098130fd20da74c96aa02419aaeebef1e64b05c'
    chosen=[]
    for year in ('2025','2026'):
        yr=[r for r in rows if (r.get('pretruth_event_reference_date') or '').startswith(year)]
        ranked=sorted(yr,key=lambda r:(hashlib.sha256((SEED+r['exact_group_id']).encode()).hexdigest(),r['exact_group_id']))
        assert len(ranked)>=20
        for r in ranked[:20]:
            chosen.append({
              'exact_group_id':r['exact_group_id'],
              'year':year,
              'pretruth_event_reference_date':r.get('pretruth_event_reference_date',''),
              'pretruth_subject_key':r.get('pretruth_subject_key',''),
              'selection_hash':hashlib.sha256((SEED+r['exact_group_id']).encode()).hexdigest()
            })
    ids2=sorted(x['exact_group_id'] for x in chosen)
    assert len(chosen)==len(set(ids2))==40
    digest=hashlib.sha256(('\n'.join(ids2)+'\n').encode()).hexdigest()
    out={
      'artifact':'W4C_R1_EARNINGS_IR_DISCOVERY_PROBE_SAMPLE',
      'version':'W4C-R1-EIR-DP-SAMPLE-v1.0',
      'status':'FROZEN_SAMPLE_PRE_EXTERNAL_REQUEST',
      'science_reopened':False,
      'sample_size':40,
      'allocation':{'2025':20,'2026':20},
      'sorted_sample_group_ids_sha256':digest,
      'selection_seed_prefix':SEED,
      'rows':chosen,
      'external_probe_requests_performed':False,
      'issuer_ir_lookup_performed':False,
      'event_truth_verification_authorized':False,
      'prediction_market_performance_read':False,
      'linked_asset_realized_returns_read':False,
      'n_final_backtestable_authorized':False,
      'outcome_reveal_authorized':False,
      'gate_decision':'PASS_W4C_R1_EARNINGS_IR_PROBE_SAMPLE_FROZEN_PRE_REQUEST'
    }
    OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2,sort_keys=True))
if __name__=='__main__': main()

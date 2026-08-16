#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'registry'
QUEUE=REG/'w4c_r1_earnings_ir_queue_v1.csv.gz'
OUT=REG/'w4c_r1_earnings_ticker_profile_v1.json'

NOISE={'GAAP','NONGAAP','EPS','FY','Q1','Q2','Q3','Q4','USD','US','CEO','CFO','ETF','FC'}

def read_rows():
    with gzip.open(QUEUE,'rt',encoding='utf-8',newline='') as f:
        return list(csv.DictReader(f))

def tokens(s):
    return [x for x in re.split(r'[^A-Za-z0-9]+',s or '') if x]

def main():
    rows=read_rows()
    ids=sorted((r.get('exact_group_id') or '').strip() for r in rows)
    assert len(rows)==len(set(ids))==1355
    assert hashlib.sha256(('\n'.join(ids)+'\n').encode()).hexdigest()=='c9fd3a13e87ea720e961fa087098130fd20da74c96aa02419aaeebef1e64b05c'
    output=[]; modes=Counter(); ticker_counts=Counter()
    for r in rows:
        raw=(r.get('pretruth_subject_key') or '')
        # Subject keys are lowercase-normalized; identify ticker-like tokens by position
        # immediately before GAAP/NONGAAP markers, a common frozen Polymarket earnings form.
        ts=tokens(raw)
        cand=[]
        for i,t in enumerate(ts):
            if t.lower() in {'gaap','nongaap'} and i>0:
                prev=ts[i-1]
                if re.fullmatch(r'[a-z]{1,5}',prev,re.I) and prev.upper() not in NOISE:
                    cand.append(prev.upper())
        cand=list(dict.fromkeys(cand))
        if len(cand)==1:
            mode='UNIQUE_PRE_GAAP_TICKER_CANDIDATE'; ticker=cand[0]; ticker_counts[ticker]+=1
        elif len(cand)>1:
            mode='MULTIPLE_TICKER_CANDIDATES_FAIL_CLOSED'; ticker=''
        else:
            mode='NO_TICKER_CANDIDATE'; ticker=''
        modes[mode]+=1
        output.append({'exact_group_id':r['exact_group_id'],'pretruth_subject_key':raw,'ticker_candidate':ticker,'mode':mode})
    summary={
      'artifact':'W4C_R1_EARNINGS_TICKER_PROFILE',
      'version':'W4C-R1-EIR-TP-v1.0',
      'status':'DESCRIPTIVE_FROZEN_METADATA_ONLY',
      'science_reopened':False,
      'queue_groups':1355,
      'mode_counts':dict(sorted(modes.items())),
      'unique_ticker_candidates':len(ticker_counts),
      'largest_ticker_candidate_group_counts':[{'ticker':k,'groups':v} for k,v in ticker_counts.most_common(50)],
      'rows':output,
      'ticker_candidate_is_truth_evidence':False,
      'ticker_candidate_may_vote':False,
      'new_external_source_reads':False,
      'issuer_ir_lookup_performed':False,
      'sec_lookup_performed':False,
      'prediction_market_performance_read':False,
      'linked_asset_realized_returns_read':False,
      'n_final_backtestable_authorized':False,
      'outcome_reveal_authorized':False,
      'gate_decision':'PASS_W4C_R1_EARNINGS_TICKER_PROFILE_DESCRIPTIVE_ONLY'
    }
    OUT.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2,sort_keys=True))
if __name__=='__main__': main()

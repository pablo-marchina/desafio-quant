#!/usr/bin/env python3
"""Synthetic validation of PIT-v2 frozen collector/scorer code without network."""
from __future__ import annotations
import csv, importlib.util, json, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def make_row(fam,i,mode):
    base={
      'event_id':f'{fam}-{i}','resolved_family':fam,'independence_cluster_id':f'{fam}-c{i}','public_revelation_utc':(datetime(2026,1,1,13,30,tzinfo=timezone.utc)+timedelta(days=i)).isoformat().replace('+00:00','Z'),
      'pm_price_witness_pre_cutoff':'true','pm_pre_cutoff_state':'PASS','pm_price_witness_24h':'true','pm_24h_state':'PASS','pre_cutoff_history_hours_lower_bound':'72','history_state':'PASS',
      'f2_event_pass':'true','f2_state':'PASS','pm_mapping_conflict':'false','pm_mapping_state':'PASS','pit_event_eligible':'true','pit_event_eligible_state':'PASS',
      'resolution_state':'PASS','resolution_ambiguous':'false','linked_asset_mapping_state':'PASS','asset_data_state':'PASS','safe_cutoff_state':'PASS','mandatory_field_state':'PASS','mandatory_account_gated_dependency':'false'
    }
    if mode=='unresolved' and i < 20:
        for k in ['pm_pre_cutoff_state','pm_24h_state','history_state','f2_state','pm_mapping_state','resolution_state','linked_asset_mapping_state','asset_data_state','safe_cutoff_state']:
            base[k]='UNRESOLVED'
        for k in ['pm_price_witness_pre_cutoff','pm_price_witness_24h','f2_event_pass','pit_event_eligible']:
            base[k]='false'
        base['pre_cutoff_history_hours_lower_bound']=''; base['pit_event_eligible_state']='UNRESOLVED'; base['public_revelation_utc']=''
    if mode=='conflict' and i==0:
        base['pm_mapping_conflict']='true'; base['f2_event_pass']='false'
    return base

def main():
    root=Path('.')
    score=load('score',root/'scripts/w2c_pit_v2_gate_score.py')
    platform=load('platform',root/'scripts/w2c_pit_v2_platform_collect.py')
    assert platform.parse_tokens('["1","2"]')==['1','2']
    assert score.rate_eval(75,10,100,.8)['status']=='INDETERMINATE'
    assert score.rate_eval(70,5,100,.8)['status']=='FAIL'
    assert score.zero_eval(0,1)=='INDETERMINATE'
    assert score.median_eval([72]*80,20,48)['status']=='PASS'
    rows=[]
    for fam,n,mode in [('EARNINGS_EPS',100,'pass'),('FDA_FINAL_PDUFA_DECISION',63,'unresolved'),('MACRO_STATISTICAL_RELEASE',97,'conflict')]:
        rows += [make_row(fam,i,mode) for i in range(n)]
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); inp=td/'combined.csv'; out=td/'gates.json'
        fields=list(rows[0]);
        with inp.open('w',newline='',encoding='utf-8') as fh:
            w=csv.DictWriter(fh,fieldnames=fields); w.writeheader(); w.writerows(rows)
        score.INPUT=inp; score.OUT=out; score.PROTOCOL=root/'registry/w2c_pit_protocol_v2_0.json'; score.main()
        z=json.loads(out.read_text())
    e=z['families']['EARNINGS_EPS']; f=z['families']['FDA_FINAL_PDUFA_DECISION']; m=z['families']['MACRO_STATISTICAL_RELEASE']
    assert e['all_pass'] is True and all(v=='PASS' for v in e['gates'].values())
    assert f['gates']['F7']=='INDETERMINATE' and f['gates']['F3']=='PASS'
    assert m['gates']['F2']=='FAIL' and m['all_pass'] is False
    print(json.dumps({'artifact':'W2C_PIT_V2_PIPELINE_SYNTHETIC','status':'PASS','assertions':8,'performance_blind':True,'network_called':False},indent=2))
if __name__=='__main__': main()

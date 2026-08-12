#!/usr/bin/env python3
"""Frozen F1-F9 scorer. Requires completed PIT-v2 combined event evidence."""
from __future__ import annotations
import csv, json, statistics
from collections import defaultdict
from pathlib import Path
PROTOCOL=Path('registry/w2c_pit_protocol_v2_0.json'); INPUT=Path('registry/w2c_pit_v2_combined_events.csv'); OUT=Path('registry/w2c_pit_v2_family_gates.json')

def b(v): return str(v).lower() in {'1','true','yes','pass'}
def rate_eval(pass_n, unresolved_n, n, threshold):
    lo=pass_n/n if n else 0; hi=(pass_n+unresolved_n)/n if n else 0
    return {'status':'PASS' if lo>=threshold else ('FAIL' if hi<threshold else 'INDETERMINATE'),'pass':pass_n,'unresolved':unresolved_n,'n':n,'lower':lo,'upper':hi,'threshold':threshold}
def zero_eval(conflict,unresolved): return 'FAIL' if conflict else ('INDETERMINATE' if unresolved else 'PASS')
def med_bounds(vals, unresolved_n):
    vals=sorted(float(x) for x in vals)
    if not vals and unresolved_n: return None,'INF'
    lower=statistics.median(sorted(vals+[0.0]*unresolved_n)) if vals or unresolved_n else None
    upper_num=statistics.median(sorted(vals+[float('inf')]*unresolved_n)) if vals or unresolved_n else None
    upper='INF' if upper_num==float('inf') else upper_num
    return lower,upper
def median_eval(vals, unresolved_n, threshold):
    lo,hi=med_bounds(vals,unresolved_n)
    if lo is not None and lo>=threshold: st='PASS'
    elif hi != 'INF' and hi is not None and hi<threshold: st='FAIL'
    else: st='INDETERMINATE'
    return {'status':st,'lower':lo,'upper':hi,'threshold':threshold,'resolved_n':len(vals),'unresolved':unresolved_n}
def main():
    p=json.loads(PROTOCOL.read_text()); rows=list(csv.DictReader(INPUT.open(encoding='utf-8',newline=''))); assert len(rows)==260
    fams=defaultdict(list)
    for r in rows: fams[r['resolved_family']].append(r)
    results={}
    for f,rr in sorted(fams.items()):
        n=len(rr)
        pre=sum(b(x['pm_price_witness_pre_cutoff']) for x in rr); pre_u=sum(x['pm_pre_cutoff_state']=='UNRESOLVED' for x in rr)
        w24=sum(b(x['pm_price_witness_24h']) for x in rr); w24_u=sum(x['pm_24h_state']=='UNRESOLVED' for x in rr)
        hist=[x['pre_cutoff_history_hours_lower_bound'] for x in rr if x['pre_cutoff_history_hours_lower_bound'] not in ('',None)]
        hist_u=sum(x['history_state']=='UNRESOLVED' for x in rr)
        f1a=rate_eval(pre,pre_u,n,p['gates']['F1_contractability']['pre_revelation_contract_rate_min']); f1b=rate_eval(w24,w24_u,n,p['gates']['F1_contractability']['analysis_window_24h_rate_min']); f1c=median_eval(hist,hist_u,p['gates']['F1_contractability']['median_pre_cutoff_history_hours_lower_bound_min'])
        f1='PASS' if all(z['status']=='PASS' for z in [f1a,f1b,f1c]) else ('FAIL' if any(z['status']=='FAIL' for z in [f1a,f1b,f1c]) else 'INDETERMINATE')
        obs=sum(b(x['f2_event_pass']) for x in rr); obs_u=sum(x['f2_state']=='UNRESOLVED' for x in rr); f2rate=rate_eval(obs,obs_u,n,p['gates']['F2_pm_pit_observability']['coverage_min']); conf=sum(b(x['pm_mapping_conflict']) for x in rr); conf_u=sum(x['pm_mapping_state']=='UNRESOLVED' for x in rr); f2z=zero_eval(conf,conf_u); f2='PASS' if f2rate['status']=='PASS' and f2z=='PASS' else ('FAIL' if 'FAIL' in [f2rate['status'],f2z] else 'INDETERMINATE')
        indep=len({x['independence_cluster_id'] for x in rr}); elig=[x for x in rr if x.get('pit_event_eligible_state')=='PASS' or b(x.get('pit_event_eligible',False))]; elig_u=[x for x in rr if x.get('pit_event_eligible_state')=='UNRESOLVED']; dates={x['public_revelation_utc'][:10] for x in elig if x.get('public_revelation_utc')}; eligible_lo=len(elig); eligible_hi=len(elig)+len(elig_u); date_lo=len(dates); date_hi=len(dates)+len(elig_u); req_e=p['gates']['F3_sampleability_floor']['pit_eligible_events_min']; req_d=p['gates']['F3_sampleability_floor']['distinct_revelation_date_clusters_min']; components=['PASS' if indep>=50 else 'FAIL', 'PASS' if eligible_lo>=req_e else ('FAIL' if eligible_hi<req_e else 'INDETERMINATE'), 'PASS' if date_lo>=req_d else ('FAIL' if date_hi<req_d else 'INDETERMINATE')]; f3='PASS' if all(z=='PASS' for z in components) else ('FAIL' if 'FAIL' in components else 'INDETERMINATE')
        res=sum(x['resolution_state']=='PASS' for x in rr); res_u=sum(x['resolution_state']=='UNRESOLVED' for x in rr); f4rate=rate_eval(res,res_u,n,p['gates']['F4_resolution']['objective_primary_source_rate_min']); amb=sum(b(x['resolution_ambiguous']) for x in elig); amb_u=sum(x['resolution_state']=='AMBIGUOUS' for x in elig); f4z=zero_eval(amb,amb_u); f4='PASS' if f4rate['status']=='PASS' and f4z=='PASS' else ('FAIL' if 'FAIL' in [f4rate['status'],f4z] else 'INDETERMINATE')
        lm=sum(x['linked_asset_mapping_state']=='PASS' for x in rr); lm_u=sum(x['linked_asset_mapping_state']=='UNRESOLVED' for x in rr); f5e=rate_eval(lm,lm_u,n,p['gates']['F5_linked_asset']['preoutcome_mapping_rate_min']); f5=f5e['status']
        ad=sum(x['asset_data_state']=='PASS' for x in rr); ad_u=sum(x['asset_data_state']=='UNRESOLVED' for x in rr); f6e=rate_eval(ad,ad_u,n,p['gates']['F6_pit_asset_data']['coverage_min']); f6=f6e['status']
        sc=sum(x['safe_cutoff_state']=='PASS' for x in rr); sc_u=sum(x['safe_cutoff_state']=='UNRESOLVED' for x in rr); f7e=rate_eval(sc,sc_u,n,p['gates']['F7_safe_cutoff']['rate_min']); f7=f7e['status']
        mf=sum(x['mandatory_field_state']=='PASS' for x in rr); mf_u=sum(x['mandatory_field_state']=='UNRESOLVED' for x in rr); f8e=rate_eval(mf,mf_u,n,p['gates']['F8_mandatory_input_coverage']['rate_min']); f8=f8e['status']
        f9='PASS' if all(not b(x.get('mandatory_account_gated_dependency',False)) for x in rr) else 'FAIL'
        gates={'F1':f1,'F2':f2,'F3':f3,'F4':f4,'F5':f5,'F6':f6,'F7':f7,'F8':f8,'F9':f9}
        results[f]={'n':n,'gates':gates,'all_pass':all(v=='PASS' for v in gates.values()),'details':{'F1_pre':f1a,'F1_24h':f1b,'F1_history':f1c,'F2_rate':f2rate,'F2_zero_conflict':f2z,'F3_independent':indep,'F3_eligible_lower':eligible_lo,'F3_eligible_upper':eligible_hi,'F3_date_clusters_lower':date_lo,'F3_date_clusters_upper':date_hi,'F4_rate':f4rate,'F4_zero_ambiguity':f4z,'F5_rate':f5e,'F6_rate':f6e,'F7_rate':f7e,'F8_rate':f8e}}
    out={'artifact':'W2C_PIT_V2_F1_F9_RESULTS','protocol':'W2C-PIT-v2.0','science_reopened':False,'performance_blind':True,'families':results,'ias_execution_authorized':False,'w3_execution_authorized':False}
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n'); print(json.dumps(out,indent=2,allow_nan=False))
if __name__=='__main__': main()

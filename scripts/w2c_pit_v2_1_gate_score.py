#!/usr/bin/env python3
"""Frozen PIT-v2.1 F1-F9 scorer with right-censoring and non-circular F4."""
from __future__ import annotations
import csv, json, math, statistics
from collections import defaultdict
from pathlib import Path

PROTOCOL=Path('registry/w2c_pit_protocol_v2_1.json')
CONTRACT=Path('registry/w2c_pit_v2_1_gate_contract.json')
INPUT=Path('registry/w2c_pit_v2_1_combined_events.csv')
OUT=Path('registry/w2c_pit_v2_1_family_gates.json')

PASS_STATES={'PASS','PASS_STRUCTURAL_FIXED','PASS_HISTORY_OBSERVED'}
UNRESOLVED_STATES={'UNRESOLVED','PENDING_PRIMARY_REVIEW','PENDING_AVAILABILITY_PROBE','AMBIGUOUS'}

def truth(v): return str(v).strip().lower() in {'1','true','yes','pass'}
def state(v): return str(v or '').strip().upper()
def is_pass(v): return state(v) in PASS_STATES
def is_unresolved(v): return state(v) in UNRESOLVED_STATES

def rate_eval(pass_n, unresolved_n, n, threshold):
    assert n>0 and 0<=pass_n<=n and 0<=unresolved_n<=n-pass_n
    lo=pass_n/n; hi=(pass_n+unresolved_n)/n
    status='PASS' if lo>=threshold else ('FAIL' if hi<threshold else 'INDETERMINATE')
    return {'status':status,'pass':pass_n,'unresolved_capable':unresolved_n,'n':n,'lower':lo,'upper':hi,'threshold':threshold}

def count_eval(lower, upper, floor):
    return {'status':'PASS' if lower>=floor else ('FAIL' if upper<floor else 'INDETERMINATE'),'lower':lower,'upper':upper,'floor':floor}

def zero_eval(confirmed_problem, unresolved_capable):
    return {'status':'FAIL' if confirmed_problem>0 else ('INDETERMINATE' if unresolved_capable>0 else 'PASS'),'confirmed_problem':confirmed_problem,'unresolved_capable':unresolved_capable,'max_allowed':0}

def median_eval(values, unresolved_n, threshold):
    vals=sorted(float(x) for x in values)
    lower_pool=sorted(vals+[0.0]*unresolved_n)
    lo=statistics.median(lower_pool) if lower_pool else None
    # +infinity is used only internally; external JSON uses string INF.
    upper_pool=sorted(vals+[math.inf]*unresolved_n)
    hi_num=statistics.median(upper_pool) if upper_pool else None
    hi='INF' if hi_num is not None and math.isinf(hi_num) else hi_num
    if lo is not None and lo>=threshold: st='PASS'
    elif hi!='INF' and hi is not None and hi<threshold: st='FAIL'
    else: st='INDETERMINATE'
    return {'status':st,'resolved_values':len(vals),'unresolved_capable':unresolved_n,'lower':lo,'upper':hi,'threshold':threshold}

def component_state(r, key):
    s=state(r.get(key,''))
    if s in PASS_STATES: return 'PASS'
    if s in UNRESOLVED_STATES: return 'UNRESOLVED'
    if s=='RIGHT_CENSORED_ASOF': return 'RIGHT_CENSORED_ASOF'
    return 'FAIL'

def f4_candidate_state(r):
    # All PIT eligibility components except F4 itself. Confirmed failure means not a
    # candidate; unresolved-capable means the event can still enter the candidate set.
    keys=['pm_pre_cutoff_state','pm_24h_state','f2_state','linked_asset_mapping_state','asset_data_state','safe_cutoff_state','mandatory_field_state']
    states=[component_state(r,k) for k in keys]
    if truth(r.get('mandatory_account_gated_dependency',False)): return 'FAIL'
    if any(s=='FAIL' for s in states): return 'FAIL'
    if any(s=='UNRESOLVED' for s in states): return 'UNRESOLVED'
    return 'PASS'

def aggregate_status(items):
    sts=[x['status'] if isinstance(x,dict) else x for x in items]
    return 'PASS' if all(x=='PASS' for x in sts) else ('FAIL' if any(x=='FAIL' for x in sts) else 'INDETERMINATE')

def main():
    p=json.loads(PROTOCOL.read_text()); c=json.loads(CONTRACT.read_text()); t=c['thresholds']
    rows=list(csv.DictReader(INPUT.open(encoding='utf-8',newline='')))
    assert len(rows)==p['population']['total']==260 and len({r['event_id'] for r in rows})==260
    fams=defaultdict(list)
    for r in rows: fams[r['resolved_family']].append(r)
    expected=p['population']['counts']; assert {k:len(v) for k,v in fams.items()}==expected
    results={}
    for fam,all_rows in sorted(fams.items()):
        due=[r for r in all_rows if state(r['asof_state'])=='DUE_ASOF']; full=all_rows
        expected_due=p['right_censoring']['frozen_structure']['past_or_due'][fam]; assert len(due)==expected_due,(fam,len(due),expected_due)
        # F1 due-only.
        pre=sum(component_state(r,'pm_pre_cutoff_state')=='PASS' for r in due); pre_u=sum(component_state(r,'pm_pre_cutoff_state')=='UNRESOLVED' for r in due)
        h24=sum(component_state(r,'pm_24h_state')=='PASS' for r in due); h24_u=sum(component_state(r,'pm_24h_state')=='UNRESOLVED' for r in due)
        hist=[r['pre_cutoff_history_hours_lower_bound'] for r in due if r.get('pre_cutoff_history_hours_lower_bound','') not in ('',None) and component_state(r,'history_state')=='PASS']
        hist_u=sum(component_state(r,'history_state')=='UNRESOLVED' for r in due)
        f1a=rate_eval(pre,pre_u,len(due),t['F1']['pre_revelation_contract_rate_min']); f1b=rate_eval(h24,h24_u,len(due),t['F1']['analysis_window_24h_rate_min']); f1c=median_eval(hist,hist_u,t['F1']['median_pre_cutoff_history_hours_lower_bound_min']); f1=aggregate_status([f1a,f1b,f1c])
        # F2 due-only. Mapping conflicts are explicit and cannot self-disappear.
        f2p=sum(component_state(r,'f2_state')=='PASS' for r in due); f2u=sum(component_state(r,'f2_state')=='UNRESOLVED' for r in due); f2rate=rate_eval(f2p,f2u,len(due),t['F2']['coverage_min'])
        conflicts=sum(truth(r.get('pm_mapping_conflict')) for r in due); conflict_u=sum(component_state(r,'pm_mapping_state')=='UNRESOLVED' for r in due); f2z=zero_eval(conflicts,conflict_u); f2=aggregate_status([f2rate,f2z])
        # F3: independent cluster floor uses full population; eligibility/dates due-only.
        indep=len({r['independence_cluster_id'] for r in full}); f3i=count_eval(indep,indep,t['F3']['validated_independent_events_min'])
        elig_pass=[r for r in due if component_state(r,'pit_event_eligible_state')=='PASS']; elig_u=[r for r in due if component_state(r,'pit_event_eligible_state')=='UNRESOLVED']; f3e=count_eval(len(elig_pass),len(elig_pass)+len(elig_u),t['F3']['pit_eligible_events_min'])
        dates={r['public_revelation_utc'][:10] for r in elig_pass if r.get('public_revelation_utc')}; f3d=count_eval(len(dates),min(len(due),len(dates)+len(elig_u)),t['F3']['distinct_revelation_date_clusters_min']); f3=aggregate_status([f3i,f3e,f3d])
        # F4 objective rate due-only; ambiguity on non-circular F4-candidate set.
        rp=sum(component_state(r,'resolution_state')=='PASS' for r in due); ru=sum(component_state(r,'resolution_state')=='UNRESOLVED' for r in due); f4rate=rate_eval(rp,ru,len(due),t['F4']['objective_primary_source_rate_min'])
        candidates=[(r,f4_candidate_state(r)) for r in due]; amb=sum(truth(r.get('resolution_ambiguous')) for r,s in candidates if s!='FAIL'); amb_u=sum(s=='UNRESOLVED' and not truth(r.get('resolution_ambiguous')) and component_state(r,'resolution_state')=='UNRESOLVED' for r,s in candidates); f4z=zero_eval(amb,amb_u); f4=aggregate_status([f4rate,f4z])
        # F5 full population; F6/F7 due; F8 full.
        f5p=sum(component_state(r,'linked_asset_mapping_state')=='PASS' for r in full); f5u=sum(component_state(r,'linked_asset_mapping_state')=='UNRESOLVED' for r in full); f5e=rate_eval(f5p,f5u,len(full),t['F5']['preoutcome_mapping_rate_min']); f5=f5e['status']
        f6p=sum(component_state(r,'asset_data_state')=='PASS' for r in due); f6u=sum(component_state(r,'asset_data_state')=='UNRESOLVED' for r in due); f6e=rate_eval(f6p,f6u,len(due),t['F6']['coverage_min']); f6=f6e['status']
        f7p=sum(component_state(r,'safe_cutoff_state')=='PASS' for r in due); f7u=sum(component_state(r,'safe_cutoff_state')=='UNRESOLVED' for r in due); f7e=rate_eval(f7p,f7u,len(due),t['F7']['rate_min']); f7=f7e['status']
        f8p=sum(component_state(r,'mandatory_field_state')=='PASS' for r in full); f8u=sum(component_state(r,'mandatory_field_state')=='UNRESOLVED' for r in full); f8e=rate_eval(f8p,f8u,len(full),t['F8']['rate_min']); f8=f8e['status']
        f9='FAIL' if any(truth(r.get('mandatory_account_gated_dependency')) for r in full) else 'PASS'
        gates={'F1':f1,'F2':f2,'F3':f3,'F4':f4,'F5':f5,'F6':f6,'F7':f7,'F8':f8,'F9':f9}
        if all(x=='PASS' for x in gates.values()): overall='ELIGIBLE_TO_DRAFT_W3_PROTOCOL'
        elif any(x=='FAIL' for x in gates.values()): overall='NO_GO_CURRENT_PROTOCOL'
        else: overall='INDETERMINATE_PENDING_EVIDENCE'
        results[fam]={'full_n':len(full),'due_n':len(due),'right_censored_n':len(full)-len(due),'gates':gates,'overall_feasibility':overall,'details':{'F1_pre':f1a,'F1_24h':f1b,'F1_history':f1c,'F2_rate':f2rate,'F2_zero_conflict':f2z,'F3_independent':f3i,'F3_eligible':f3e,'F3_date_clusters':f3d,'F4_rate':f4rate,'F4_zero_ambiguity_non_circular':f4z,'F4_candidate_pass':sum(s=='PASS' for _,s in candidates),'F4_candidate_unresolved':sum(s=='UNRESOLVED' for _,s in candidates),'F5_rate':f5e,'F6_rate':f6e,'F7_rate':f7e,'F8_rate':f8e}}
    out={'artifact':'W2C_PIT_V2_1_F1_F9_RESULTS','version':'W2C-PIT-F1F9-v2.1','protocol':'W2C-PIT-v2.1','gate_contract':'W2C-PIT-GATES-v2.1','frozen_asof_utc':p['frozen_asof_utc'],'science_reopened':False,'performance_blind':True,'families':results,'ias_execution_authorized':False,'smaa_execution_authorized':False,'w3_execution_authorized':False}
    OUT.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n'); print(json.dumps(out,indent=2,allow_nan=False))
if __name__=='__main__': main()

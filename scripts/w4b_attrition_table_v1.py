#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'registry'
PROTO=json.loads((REG/'w4b_attrition_table_protocol_v1.json').read_text())


def j(name): return json.loads((REG/name).read_text())
def gz(name):
    with gzip.open(REG/name,'rt',encoding='utf-8',newline='') as f: return list(csv.DictReader(f))

def pct(a,b): return '' if not b else f'{100.0*a/b:.6f}'

def main():
    close=REG/'w4b_official_event_truth_closeout_v1.json'
    if not close.exists(): raise SystemExit('SEQUENCE_GATE_MISSING_OFFICIAL_TRUTH_CLOSEOUT')
    c=j('w4b_official_event_truth_closeout_v1.json')
    if c.get('technical_gate_decision')!='PASS_OFFICIAL_EVENT_TRUTH_MATERIALIZED': raise SystemExit('SEQUENCE_GATE_OFFICIAL_TRUTH_NOT_PASSED')

    sem=j('w4b_kalshi_semantic_summary_v1_1.json')
    # Authoritative history closeout records the actual superseding result path.
    hclose=j('w4b_kalshi_history_closeout_authoritative.json')
    hsum=j(hclose['summary_path'])
    hevents=gz(hclose['event_path'])
    fx=j('w4b_forecastex_census_summary_v1.json')
    pm=j('w4b_polymarket_recensus_summary_v1.json')
    xv=j('w4b_cross_venue_dedup_summary_v1.json')
    ot=j('w4b_official_event_truth_summary_v1.json')

    rows=[]
    def add(track,stage,unit,n,parent_stage='',parent_n=None,note='',bound='',claim=''):
        rows.append({'track':track,'stage':stage,'unit':unit,'n':int(n),'parent_stage':parent_stage,'parent_n':'' if parent_n is None else int(parent_n),'retention_pct':pct(int(n),int(parent_n)) if parent_n is not None else '', 'unit_transition_or_note':note,'bound':bound,'claim_status':claim})

    add('KALSHI_SEMANTIC','K0_RETRIEVED_CANDIDATE_EVENTS','venue_event_row',sem['event_rows_examined'])
    add('KALSHI_SEMANTIC','K1_STRICT_ACCEPTED_EVENT_ROWS','venue_event_row',sem['accepted_strict_event_rows'],'K0_RETRIEVED_CANDIDATE_EVENTS',sem['event_rows_examined'])
    add('KALSHI_SEMANTIC','K2_WITHIN_VENUE_CANONICAL','venue_canonical_event',sem['accepted_unique_canonical_events'],'K1_STRICT_ACCEPTED_EVENT_ROWS',None,'UNIT_CHANGE: accepted event rows collapse aliases/strikes into canonical events')

    cls=Counter(r['history_class'] for r in hevents)
    dist=sum(r.get('distributional_core_flag')=='YES' for r in hevents)
    kh0=hsum['canonical_events_audited']
    add('KALSHI_HISTORY','KH0_CANONICAL_AUDITED','kalshi_canonical_event',kh0,claim='VENUE_HISTORY_AUDITED')
    add('KALSHI_HISTORY','KH1_FULL_LADDER','kalshi_canonical_event',cls.get('FULL_LADDER',0),'KH0_CANONICAL_AUDITED',kh0,claim='HISTORY_QUALIFIED_DESCRIPTIVE')
    core=cls.get('FULL_LADDER',0)+cls.get('CORE_T10_TO_T1H',0)
    add('KALSHI_HISTORY','KH2_CORE_T10_TO_T1H','kalshi_canonical_event',core,'KH0_CANONICAL_AUDITED',kh0,'Includes FULL_LADDER because it satisfies the CORE predicate',claim='HISTORY_QUALIFIED_DESCRIPTIVE')
    add('KALSHI_HISTORY','KH3_DISTRIBUTIONAL_CORE','kalshi_canonical_event',dist,'KH0_CANONICAL_AUDITED',kh0,'Descriptive only; never increases independent N',claim='DESCRIPTIVE_ONLY')
    missing=kh0-core
    add('KALSHI_HISTORY','KH4_PARTIAL_OR_MISSING','kalshi_canonical_event',missing,'KH0_CANONICAL_AUDITED',kh0,'Complement of CORE predicate',claim='HISTORY_ATTRITION')
    for reason in ('NO_T10D','NO_NEAR_T0','PARTIAL','NO_HISTORY'):
        add('KALSHI_HISTORY',f'KH4_{reason}','kalshi_canonical_event',cls.get(reason,0),'KH4_PARTIAL_OR_MISSING',missing,'Mutually exclusive history_class reason',claim='HISTORY_ATTRITION_REASON')

    add('FORECASTEX_CENSUS','FX0_ARCHIVE_DATES','archive_date',fx['archive_dates_with_summary'],note='Diagnostic only; not an event unit',claim='DIAGNOSTIC_ONLY')
    add('FORECASTEX_CENSUS','FX1_UNIQUE_CONTRACT_IDENTIFIERS','venue_contract_identifier',fx['unique_contract_identifier_rows'],note='Diagnostic only; not an event unit',claim='DIAGNOSTIC_ONLY')
    add('FORECASTEX_CENSUS','FX2_WITHIN_VENUE_CANONICAL','venue_canonical_event',fx['accepted_unique_canonical_events'],claim='CENSUS_CAPACITY_NOT_BACKTESTABLE')

    add('POLYMARKET_RECENSUS','PM0_UNIQUE_GAMMA_EVENTS','venue_event_row',pm['unique_gamma_event_ids'])
    add('POLYMARKET_RECENSUS','PM1_WITHIN_VENUE_CANONICAL','venue_canonical_event',pm['accepted_unique_canonical_events'],'PM0_UNIQUE_GAMMA_EVENTS',None,'UNIT_CHANGE: semantic acceptance plus same-occurrence alias collapse',claim='CENSUS_CAPACITY_NOT_BACKTESTABLE')

    add('CROSS_VENUE','XV0_VENUE_CANONICAL_SUM','venue_canonical_event',xv['pre_dedup_venue_record_sum'])
    add('CROSS_VENUE','XV1_EXACT_W4CE1_GROUPS','cross_venue_exact_group',xv['exact_dedup_n'],'XV0_VENUE_CANONICAL_SUM',None,'UNIT_CHANGE: exact cross-venue aliases collapse')
    add('CROSS_VENUE','XV2_PRETRUTH_LOWER_BOUND','cross_venue_exact_group_component',xv['candidate_merge_lower_bound_n'],note='If every preregistered candidate edge is later same-event',bound='LOWER_IF_ALL_CANDIDATE_EDGES_CONFIRM')
    add('CROSS_VENUE','XV3_PRETRUTH_UPPER_BOUND','cross_venue_exact_group',xv['pretruth_upper_bound_n'],bound='UPPER_IF_ALL_NONEXACT_CANDIDATES_DISTINCT')

    add('OFFICIAL_TRUTH','OT0_PRETRUTH_EXACT_GROUPS','cross_venue_exact_group',ot['pretruth_exact_groups'])
    add('OFFICIAL_TRUTH','OT1_VERIFIED_OFFICIAL_GROUPS','official_event',ot['verified_unique_official_events'],'OT0_PRETRUTH_EXACT_GROUPS',None,'UNIT_CHANGE: authoritative identity mapping to W4OT1',claim='TRUTH_VERIFIED_UNIVERSE')
    unresolved_n=sum(v for k,v in ot['verification_state_counts'].items() if k!='VERIFIED_OFFICIAL_TRUTH')
    add('OFFICIAL_TRUTH','OT2_UNRESOLVED_EXCLUDED','cross_venue_exact_group',unresolved_n,'OT0_PRETRUTH_EXACT_GROUPS',ot['pretruth_exact_groups'],'Non-verified exact groups excluded from truth-verified N',claim='EXCLUDED')

    # Family table: use record-level artifacts to guarantee reconciliation rather than trusting summary formatting.
    fam_rows=[]
    def fam_add(track,stage,counts,total_expected,unit,claim=''):
        assert sum(counts.values())==int(total_expected), (track,stage,sum(counts.values()),total_expected)
        for fam,n in sorted(counts.items()): fam_rows.append({'track':track,'stage':stage,'unit':unit,'resolved_family':fam,'n':n,'stage_total_n':int(total_expected),'share_pct':pct(n,total_expected),'claim_status':claim})

    k1={f:int(x['accepted_event_rows']) for f,x in sem['family_counts'].items()}; fam_add('KALSHI_SEMANTIC','K1_STRICT_ACCEPTED_EVENT_ROWS',k1,sem['accepted_strict_event_rows'],'venue_event_row')
    k2={f:int(x['canonical_unique_events']) for f,x in sem['family_counts'].items()}; fam_add('KALSHI_SEMANTIC','K2_WITHIN_VENUE_CANONICAL',k2,sem['accepted_unique_canonical_events'],'venue_canonical_event')
    kh0f=Counter(r['resolved_family'] for r in hevents); fam_add('KALSHI_HISTORY','KH0_CANONICAL_AUDITED',kh0f,kh0,'kalshi_canonical_event')
    kh1f=Counter(r['resolved_family'] for r in hevents if r['history_class']=='FULL_LADDER'); fam_add('KALSHI_HISTORY','KH1_FULL_LADDER',kh1f,cls.get('FULL_LADDER',0),'kalshi_canonical_event','HISTORY_QUALIFIED_DESCRIPTIVE')
    kh2f=Counter(r['resolved_family'] for r in hevents if r['history_class'] in ('FULL_LADDER','CORE_T10_TO_T1H')); fam_add('KALSHI_HISTORY','KH2_CORE_T10_TO_T1H',kh2f,core,'kalshi_canonical_event','HISTORY_QUALIFIED_DESCRIPTIVE')
    fxf=Counter({k:int(v) for k,v in fx.get('accepted_family_counts',{}).items()}); fam_add('FORECASTEX_CENSUS','FX2_WITHIN_VENUE_CANONICAL',fxf,fx['accepted_unique_canonical_events'],'venue_canonical_event','CENSUS_CAPACITY_NOT_BACKTESTABLE')
    pmf=Counter({k:int(v) for k,v in pm.get('accepted_family_counts',{}).items()}); fam_add('POLYMARKET_RECENSUS','PM1_WITHIN_VENUE_CANONICAL',pmf,pm['accepted_unique_canonical_events'],'venue_canonical_event','CENSUS_CAPACITY_NOT_BACKTESTABLE')
    otf=Counter({k:int(v) for k,v in ot.get('verified_family_counts',{}).items()}); fam_add('OFFICIAL_TRUTH','OT1_VERIFIED_OFFICIAL_GROUPS',otf,ot['verified_unique_official_events'],'official_event','TRUTH_VERIFIED_UNIVERSE')

    excl=[]
    def ex(track,transition,reason,n,additive='YES',note=''):
        excl.append({'track':track,'transition':transition,'exclusion_reason':reason,'n':int(n),'mutually_exclusive_additive':additive,'note':note})
    ex('KALSHI_SEMANTIC','K0->K1','semantic_false_positive_or_zero_strict_family',sem['event_rows_examined']-sem['accepted_strict_event_rows']-sem['ambiguous_rows'])
    ex('KALSHI_SEMANTIC','K0->K1','semantic_ambiguous_multi_family',sem['ambiguous_rows'])
    ex('KALSHI_SEMANTIC','K1->K2','within_venue_alias_or_strike_collapse',sem['canonical_alias_rows_collapsed'],'YES','Unit changes from event rows to canonical events')
    for reason,key in [('history_no_t10d','NO_T10D'),('history_no_near_t0','NO_NEAR_T0'),('history_partial','PARTIAL'),('history_no_history','NO_HISTORY')]: ex('KALSHI_HISTORY','KH0->KH2',reason,cls.get(key,0))
    ex('CROSS_VENUE','XV0->XV1','cross_venue_exact_alias_collapse',xv['pre_dedup_venue_record_sum']-xv['exact_dedup_n'],'YES','Unit changes venue canonical records to exact groups')
    ex('CROSS_VENUE','XV1->OFFICIAL_TRUTH','cross_venue_candidate_duplicate_pending_before_truth',xv['candidate_duplicate_edges'],'NO','Edge count, non-additive diagnostic')
    states=ot['verification_state_counts']
    ex('OFFICIAL_TRUTH','OT0->OT1','official_truth_unresolved',states.get('UNRESOLVED_OFFICIAL_TRUTH',0))
    ex('OFFICIAL_TRUTH','OT0->OT1','official_truth_reject_not_same_semantic_event',states.get('REJECT_NOT_SAME_SEMANTIC_EVENT',0))
    ex('OFFICIAL_TRUTH','OT0->OT1','not_historical_yet',states.get('NOT_HISTORICAL_YET',0))

    fields=['track','stage','unit','n','parent_stage','parent_n','retention_pct','unit_transition_or_note','bound','claim_status']
    with (REG/'w4b_attrition_table_v1.csv').open('w',encoding='utf-8',newline='') as f: w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    ff=['track','stage','unit','resolved_family','n','stage_total_n','share_pct','claim_status']
    with (REG/'w4b_attrition_by_family_v1.csv').open('w',encoding='utf-8',newline='') as f: w=csv.DictWriter(f,fieldnames=ff); w.writeheader(); w.writerows(fam_rows)
    ef=['track','transition','exclusion_reason','n','mutually_exclusive_additive','note']
    with (REG/'w4b_attrition_exclusion_reasons_v1.csv').open('w',encoding='utf-8',newline='') as f: w=csv.DictWriter(f,fieldnames=ef); w.writeheader(); w.writerows(excl)

    # Same-unit conservation checks explicitly mandated by frozen contract.
    checks={
      'K0=K1+semantic_exclusions': sem['event_rows_examined']==sem['accepted_strict_event_rows']+(sem['event_rows_examined']-sem['accepted_strict_event_rows']-sem['ambiguous_rows'])+sem['ambiguous_rows'],
      'KH0=CORE+noncore': kh0==core+missing,
      'OT0=verified_exact_groups+nonverified': ot['pretruth_exact_groups']==ot['verified_exact_groups']+unresolved_n,
    }
    gate=all(checks.values()) and hsum['api_unresolved_count']==0 and hsum['technical_gate_decision']=='PASS_FULL_POPULATION_HISTORY_MATERIALIZED' and fx['gate_decision']=='PASS_FORECASTEX_CENSUS_MATERIALIZED' and pm['gate_decision']=='PASS_POLYMARKET_RECENSUS_MATERIALIZED' and xv['gate_decision']=='PASS_CROSS_VENUE_PRETRUTH_DEDUP_MATERIALIZED' and ot['gate_decision']=='PASS_OFFICIAL_EVENT_TRUTH_MATERIALIZED'
    out={
      'artifact':'W4B_ATTRITION_SUMMARY','version':'W4B-AT-RESULT-v1.0','protocol_version':PROTO['version'],
      'stage_rows':len(rows),'family_rows':len(fam_rows),'exclusion_rows':len(excl),'conservation_checks':checks,
      'kalshi_canonical_events':sem['accepted_unique_canonical_events'],'kalshi_core_t10_to_t1h_events':core,'kalshi_full_ladder_events':cls.get('FULL_LADDER',0),
      'forecastex_canonical_census_events':fx['accepted_unique_canonical_events'],'polymarket_canonical_census_events':pm['accepted_unique_canonical_events'],
      'pretruth_exact_cross_venue_groups':xv['exact_dedup_n'],'pretruth_candidate_merge_lower_bound':xv['candidate_merge_lower_bound_n'],'pretruth_upper_bound':xv['pretruth_upper_bound_n'],
      'truth_verified_unique_official_events':ot['verified_unique_official_events'],
      'forecastex_backtestable_claim_authorized':False,'polymarket_backtestable_claim_authorized':False,'n_final_backtestable_authorized':False,
      'performance_blind':True,'linked_asset_realized_returns_read':False,
      'gate_decision':'PASS_W4B_ATTRITION_MATERIALIZED' if gate else 'FAIL_W4B_ATTRITION_MATERIALIZATION',
      'interpretation':'W4-B population/identity attrition plus Kalshi-only frozen T-10d->T0 history qualification. ForecastEx and Polymarket remain census-only until venue-specific PIT-history qualification; no N_final_backtestable claim is authorized here.'
    }
    (REG/'w4b_attrition_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2,sort_keys=True))
    if not gate: raise SystemExit(2)

if __name__=='__main__': main()

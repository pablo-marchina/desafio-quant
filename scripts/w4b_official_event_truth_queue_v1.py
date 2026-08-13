#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'registry'
PROTO=json.loads((REG/'w4b_official_event_truth_protocol_v1.json').read_text())

STRATEGY={
 'CPI_INFLATION_RELEASE':'BLS_CPI_ARCHIVE',
 'PAYROLLS_JOBS_RELEASE':'BLS_EMPLOYMENT_SITUATION_ARCHIVE',
 'UNEMPLOYMENT_RELEASE':'BLS_EMPLOYMENT_OR_DOL_UI_BY_SUBJECT',
 'GDP_RELEASE':'BEA_GDP_ARCHIVE',
 'PCE_RELEASE':'BEA_PERSONAL_INCOME_OUTLAYS_ARCHIVE',
 'RETAIL_SALES_RELEASE':'CENSUS_ADVANCE_RETAIL_ARCHIVE',
 'FOMC_DECISION':'FED_FOMC_STATEMENT_CALENDAR',
 'FDA_ADVISORY_COMMITTEE':'FDA_ADVISORY_CALENDAR_MATERIALS',
 'FDA_FINAL_PDUFA_DECISION':'FDA_DRUGSATFDA_THEN_SEC_ISSUER_IF_NONPUBLIC',
 'EARNINGS_EPS':'SEC_EDGAR_THEN_ISSUER_IR',
 'MA_PRE_ANNOUNCEMENT_OR_RUMOR':'SEC_EDGAR_AND_ISSUER_IR',
 'MA_PENDING_COMPLETION':'SEC_EDGAR_AND_ISSUER_IR',
 'MA_REGULATORY_CLEARANCE':'OFFICIAL_REGULATOR_THEN_SEC_ISSUER',
 'ANTITRUST_ENFORCEMENT_SINGLE_NAME':'FTC_DOJ_REGULATOR_OR_OFFICIAL_COURT',
 'CORPORATE_LITIGATION_BINARY':'OFFICIAL_COURT_THEN_SEC_ISSUER',
}


def read_gz(name):
    with gzip.open(REG/name,'rt',encoding='utf-8',newline='') as f: return list(csv.DictReader(f))


def main():
    close=REG/'w4b_cross_venue_dedup_closeout_v1.json'
    if not close.exists(): raise SystemExit('SEQUENCE_GATE_MISSING_CROSS_VENUE_CLOSEOUT')
    c=json.loads(close.read_text())
    if c.get('technical_gate_decision')!='PASS_CROSS_VENUE_PRETRUTH_DEDUP_MATERIALIZED': raise SystemExit('SEQUENCE_GATE_CROSS_VENUE_NOT_PASSED')
    groups=read_gz('w4b_cross_venue_exact_groups_v1.csv.gz')
    edges=read_gz('w4b_cross_venue_candidate_edges_v1.csv.gz')
    comps=read_gz('w4b_cross_venue_candidate_components_v1.csv.gz')
    comp_by_group={}
    for x in comps:
        for gid in filter(None,(x.get('exact_group_ids') or '').split('|')): comp_by_group[gid]=x.get('candidate_component_id','')
    degree=Counter()
    for e in edges:
        degree[e['group_a']]+=1; degree[e['group_b']]+=1
    rows=[]
    for g in groups:
        fam=g['resolved_family']; subj=g['normalized_subject_key']
        strategy=STRATEGY.get(fam,'UNMAPPED_SOURCE_STRATEGY')
        if fam=='UNEMPLOYMENT_RELEASE':
            strategy='DOL_UI_WEEKLY_CLAIMS' if subj=='US_INITIAL_JOBLESS_CLAIMS' else 'BLS_EMPLOYMENT_SITUATION_ARCHIVE'
        rows.append({
          'exact_group_id':g['exact_group_id'],'resolved_family':fam,'pretruth_event_reference_date':g['event_reference_date'],
          'normalized_subject_key':subj,'venues':g['venues'],'venue_count':g['venue_count'],
          'candidate_component_id':comp_by_group.get(g['exact_group_id'],''),'candidate_edge_degree':degree[g['exact_group_id']],
          'source_strategy':strategy,'review_priority':'CANDIDATE_COMPONENT' if degree[g['exact_group_id']] else 'SINGLETON',
        })
    fields=['exact_group_id','resolved_family','pretruth_event_reference_date','normalized_subject_key','venues','venue_count','candidate_component_id','candidate_edge_degree','source_strategy','review_priority']
    with gzip.open(REG/'w4b_official_event_truth_queue_v1.csv.gz','wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    dfields=['exact_group_id','verification_state','official_event_reference_date','official_event_timestamp_utc_if_published','official_subject_key','source_authority','source_url','retrieved_at_utc','source_body_sha256_or_document_hash','evidence_excerpt_hash_or_structured_field_reference','verification_reason','review_mode']
    with (REG/'w4b_official_event_truth_decisions_template_v1.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=dfields); w.writeheader()
        for r in rows:
            w.writerow({'exact_group_id':r['exact_group_id'],'official_subject_key':r['normalized_subject_key']})
    summary={'artifact':'W4B_OFFICIAL_EVENT_TRUTH_QUEUE_SUMMARY','version':'W4B-OET-Q-v1.0','queue_rows':len(rows),'candidate_component_rows':sum(r['review_priority']=='CANDIDATE_COMPONENT' for r in rows),'singleton_rows':sum(r['review_priority']=='SINGLETON' for r in rows),'family_counts':dict(sorted(Counter(r['resolved_family'] for r in rows).items())),'performance_blind':True,'linked_asset_realized_returns_read':False,'official_truth_decisions_read':False}
    (REG/'w4b_official_event_truth_queue_summary_v1.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__': main()

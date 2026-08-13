#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'registry'
PROTO=json.loads((REG/'w4b_official_event_truth_protocol_v1.json').read_text())
CLAR=json.loads((REG/'w4b_official_event_truth_state_clarification_v1_0_1.json').read_text())
DECISIONS=REG/'w4b_official_event_truth_decisions_v1.csv'

ALLOWED={
 'CPI_INFLATION_RELEASE':{'BLS'},
 'PAYROLLS_JOBS_RELEASE':{'BLS'},
 'GDP_RELEASE':{'BEA'},
 'PCE_RELEASE':{'BEA'},
 'RETAIL_SALES_RELEASE':{'CENSUS'},
 'FOMC_DECISION':{'FEDERAL_RESERVE'},
 'FDA_ADVISORY_COMMITTEE':{'FDA','FEDERAL_REGISTER'},
 'FDA_FINAL_PDUFA_DECISION':{'FDA','SEC_EDGAR','ISSUER_IR'},
 'EARNINGS_EPS':{'SEC_EDGAR','ISSUER_IR'},
 'MA_PRE_ANNOUNCEMENT_OR_RUMOR':{'SEC_EDGAR','ISSUER_IR'},
 'MA_PENDING_COMPLETION':{'SEC_EDGAR','ISSUER_IR'},
 'MA_REGULATORY_CLEARANCE':{'FTC','DOJ','OFFICIAL_REGULATOR','SEC_EDGAR','ISSUER_IR'},
 'ANTITRUST_ENFORCEMENT_SINGLE_NAME':{'FTC','DOJ','OFFICIAL_REGULATOR','OFFICIAL_COURT','SEC_EDGAR'},
 'CORPORATE_LITIGATION_BINARY':{'OFFICIAL_COURT','SEC_EDGAR','ISSUER_IR'},
}


def read_gz(name):
    with gzip.open(REG/name,'rt',encoding='utf-8',newline='') as f: return list(csv.DictReader(f))


def write_gz(name,rows,fields):
    with gzip.open(REG/name,'wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows([{k:r.get(k,'') for k in fields} for r in rows])


def valid_date(s):
    try: datetime.strptime(s,'%Y-%m-%d'); return True
    except Exception: return False


def official_id(fam,dt,subject):
    return 'W4OT1-'+hashlib.sha256(f'{fam}|{dt}|{subject}'.encode()).hexdigest()[:20]


def main():
    close=REG/'w4b_cross_venue_dedup_closeout_v1.json'
    if not close.exists(): raise SystemExit('SEQUENCE_GATE_MISSING_CROSS_VENUE_CLOSEOUT')
    c=json.loads(close.read_text())
    if c.get('technical_gate_decision')!='PASS_CROSS_VENUE_PRETRUTH_DEDUP_MATERIALIZED': raise SystemExit('SEQUENCE_GATE_CROSS_VENUE_NOT_PASSED')
    if not DECISIONS.exists(): raise SystemExit('OFFICIAL_TRUTH_DECISIONS_MISSING')

    groups={r['exact_group_id']:r for r in read_gz('w4b_cross_venue_exact_groups_v1.csv.gz')}
    edges=read_gz('w4b_cross_venue_candidate_edges_v1.csv.gz')
    rows=list(csv.DictReader(DECISIONS.open('r',encoding='utf-8',newline='')))
    if len(rows)!=len(groups): raise SystemExit(f'DECISION_CARDINALITY_MISMATCH:{len(rows)}!={len(groups)}')
    by_gid=defaultdict(list)
    for r in rows: by_gid[(r.get('exact_group_id') or '').strip()].append(r)
    dup=[k for k,v in by_gid.items() if len(v)!=1 or k not in groups]
    missing=[k for k in groups if k not in by_gid]
    if dup or missing: raise SystemExit(f'DECISION_KEY_MISMATCH:dup_or_unknown={dup[:10]} missing={missing[:10]}')

    truth=[]; unresolved=[]; source_manifest={}; errors=[]
    states=set(CLAR['authoritative_states'])
    for gid,g in sorted(groups.items()):
        d=by_gid[gid][0]
        state=(d.get('verification_state') or '').strip()
        fam=g['resolved_family']; predate=g['event_reference_date']; presub=g['normalized_subject_key']
        if state not in states:
            errors.append({'exact_group_id':gid,'error':'invalid_state','value':state}); continue
        od=(d.get('official_event_reference_date') or '').strip(); osub=(d.get('official_subject_key') or '').strip(); auth=(d.get('source_authority') or '').strip(); url=(d.get('source_url') or '').strip()
        oid=''
        if state=='VERIFIED_OFFICIAL_TRUTH':
            if fam=='UNEMPLOYMENT_RELEASE':
                allowed={'DOL_ETA'} if presub=='US_INITIAL_JOBLESS_CLAIMS' else {'BLS'}
            else:
                allowed=ALLOWED.get(fam,set())
            if not valid_date(od): errors.append({'exact_group_id':gid,'error':'verified_missing_or_invalid_official_date','value':od}); continue
            if not osub: errors.append({'exact_group_id':gid,'error':'verified_missing_official_subject'}); continue
            if auth not in allowed: errors.append({'exact_group_id':gid,'error':'authority_not_allowed_for_family','value':auth,'allowed':'|'.join(sorted(allowed))}); continue
            parsed=urlparse(url)
            if parsed.scheme!='https' or not parsed.netloc: errors.append({'exact_group_id':gid,'error':'verified_invalid_source_url','value':url}); continue
            if not (d.get('retrieved_at_utc') or '').strip(): errors.append({'exact_group_id':gid,'error':'verified_missing_retrieval_timestamp'}); continue
            if not (d.get('evidence_excerpt_hash_or_structured_field_reference') or '').strip(): errors.append({'exact_group_id':gid,'error':'verified_missing_evidence_reference'}); continue
            oid=official_id(fam,od,osub)
            skey=(auth,url,(d.get('source_body_sha256_or_document_hash') or '').strip())
            source_manifest[skey]={
                'source_authority':auth,'source_url':url,'retrieved_at_utc':(d.get('retrieved_at_utc') or '').strip(),
                'source_body_sha256_or_document_hash':skey[2],
                'evidence_excerpt_hash_or_structured_field_reference':(d.get('evidence_excerpt_hash_or_structured_field_reference') or '').strip()
            }
        rec={
            'exact_group_id':gid,'resolved_family':fam,'pretruth_event_reference_date':predate,'pretruth_subject_key':presub,
            'venues':g.get('venues',''),'verification_state':state,'official_event_id':oid,
            'official_event_reference_date':od,'official_event_timestamp_utc_if_published':(d.get('official_event_timestamp_utc_if_published') or '').strip(),
            'official_subject_key':osub,'source_authority':auth,'source_url':url,
            'source_body_sha256_or_document_hash':(d.get('source_body_sha256_or_document_hash') or '').strip(),
            'evidence_excerpt_hash_or_structured_field_reference':(d.get('evidence_excerpt_hash_or_structured_field_reference') or '').strip(),
            'verification_reason':(d.get('verification_reason') or '').strip(),'review_mode':(d.get('review_mode') or '').strip(),
            'reference_date_delta_days':(datetime.strptime(od,'%Y-%m-%d').date()-datetime.strptime(predate,'%Y-%m-%d').date()).days if state=='VERIFIED_OFFICIAL_TRUTH' and valid_date(predate) else '',
        }
        truth.append(rec)
        if state!='VERIFIED_OFFICIAL_TRUTH': unresolved.append(rec)

    if errors:
        (REG/'w4b_official_event_truth_validation_errors_v1.json').write_text(json.dumps(errors,indent=2,sort_keys=True)+'\n')
        raise SystemExit(f'OFFICIAL_TRUTH_DECISION_VALIDATION_ERRORS:{errors[:5]}')

    truth_by_gid={r['exact_group_id']:r for r in truth}
    edge_rows=[]
    for e in edges:
        a=truth_by_gid[e['group_a']]; b=truth_by_gid[e['group_b']]
        if a['verification_state']=='VERIFIED_OFFICIAL_TRUTH' and b['verification_state']=='VERIFIED_OFFICIAL_TRUTH':
            state='CONFIRMED_SAME_OFFICIAL_EVENT' if a['official_event_id']==b['official_event_id'] else 'CONFIRMED_DISTINCT_OFFICIAL_EVENTS'
        else:
            state='UNRESOLVED_OFFICIAL_IDENTITY'
        edge_rows.append({
          'group_a':e['group_a'],'group_b':e['group_b'],'resolved_family':e['resolved_family'],'pretruth_edge_type':e['edge_type'],
          'official_event_id_a':a['official_event_id'],'official_event_id_b':b['official_event_id'],'adjudication_state':state,
        })

    verified=[r for r in truth if r['verification_state']=='VERIFIED_OFFICIAL_TRUTH']
    final=defaultdict(list)
    for r in verified: final[r['official_event_id']].append(r)
    final_rows=[]; contradictions=[]
    for oid,rs in sorted(final.items()):
        fams={r['resolved_family'] for r in rs}; ods={r['official_event_reference_date'] for r in rs}; subs={r['official_subject_key'] for r in rs}
        if len(fams)!=1 or len(ods)!=1 or len(subs)!=1:
            contradictions.append({'official_event_id':oid,'families':sorted(fams),'dates':sorted(ods),'subjects':sorted(subs)}); continue
        final_rows.append({
          'official_event_id':oid,'resolved_family':next(iter(fams)),'official_event_reference_date':next(iter(ods)),'official_subject_key':next(iter(subs)),
          'exact_group_ids':'|'.join(sorted(r['exact_group_id'] for r in rs)),'exact_group_count':len(rs),
          'venues':'|'.join(sorted({v for r in rs for v in r['venues'].split('|') if v})),
          'source_authorities':'|'.join(sorted({r['source_authority'] for r in rs if r['source_authority']})),
        })

    # A confirmed-distinct edge may never land inside one final official event; same edges must land inside one.
    for e in edge_rows:
        if e['adjudication_state']=='CONFIRMED_DISTINCT_OFFICIAL_EVENTS' and e['official_event_id_a']==e['official_event_id_b']:
            contradictions.append({'edge':f"{e['group_a']}|{e['group_b']}",'error':'distinct_same_oid'})
        if e['adjudication_state']=='CONFIRMED_SAME_OFFICIAL_EVENT' and e['official_event_id_a']!=e['official_event_id_b']:
            contradictions.append({'edge':f"{e['group_a']}|{e['group_b']}",'error':'same_different_oid'})

    truth_fields=['exact_group_id','resolved_family','pretruth_event_reference_date','pretruth_subject_key','venues','verification_state','official_event_id','official_event_reference_date','official_event_timestamp_utc_if_published','official_subject_key','source_authority','source_url','source_body_sha256_or_document_hash','evidence_excerpt_hash_or_structured_field_reference','verification_reason','review_mode','reference_date_delta_days']
    write_gz('w4b_official_event_truth_records_v1.csv.gz',truth,truth_fields)
    write_gz('w4b_official_event_truth_unresolved_v1.csv.gz',unresolved,truth_fields)
    write_gz('w4b_official_event_truth_edge_adjudication_v1.csv.gz',edge_rows,['group_a','group_b','resolved_family','pretruth_edge_type','official_event_id_a','official_event_id_b','adjudication_state'])
    write_gz('w4b_official_event_truth_groups_v1.csv.gz',final_rows,['official_event_id','resolved_family','official_event_reference_date','official_subject_key','exact_group_ids','exact_group_count','venues','source_authorities'])
    write_gz('w4b_official_event_truth_source_manifest_v1.csv.gz',list(source_manifest.values()),['source_authority','source_url','retrieved_at_utc','source_body_sha256_or_document_hash','evidence_excerpt_hash_or_structured_field_reference'])

    state_counts=Counter(r['verification_state'] for r in truth); edge_counts=Counter(r['adjudication_state'] for r in edge_rows); fam_counts=Counter(r['resolved_family'] for r in final_rows)
    gate=not contradictions and len(truth)==len(groups)
    out={
      'artifact':'W4B_OFFICIAL_EVENT_TRUTH_SUMMARY','version':'W4B-OET-RESULT-v1.0','date_utc':datetime.now(timezone.utc).isoformat(),
      'protocol_version':PROTO['version'],'state_clarification_version':CLAR['version'],'performance_blind':True,
      'linked_asset_realized_returns_read':False,'prediction_market_performance_read':False,'prediction_market_settlement_result_used':False,
      'pretruth_exact_groups':len(groups),'decision_rows_accounted':len(truth),'verification_state_counts':dict(sorted(state_counts.items())),
      'verified_exact_groups':len(verified),'verified_unique_official_events':len(final_rows),'official_truth_alias_groups_collapsed':len(verified)-len(final_rows),
      'verified_family_counts':dict(sorted(fam_counts.items())),'candidate_edge_adjudication_counts':dict(sorted(edge_counts.items())),
      'source_manifest_rows':len(source_manifest),'transitivity_or_identity_contradictions':contradictions,
      'gate_decision':'PASS_OFFICIAL_EVENT_TRUTH_MATERIALIZED' if gate else 'FAIL_OFFICIAL_EVENT_TRUTH_MATERIALIZATION',
      'interpretation':'Only VERIFIED_OFFICIAL_TRUTH groups enter the truth-verified multi-venue event universe. Unresolved/rejected/not-historical rows remain explicit attrition and never increase verified N.'
    }
    (REG/'w4b_official_event_truth_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2,sort_keys=True))
    if not gate: raise SystemExit(2)

if __name__=='__main__': main()

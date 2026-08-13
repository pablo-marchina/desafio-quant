#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,json
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; R=ROOT/'registry'
PROTO=json.loads((R/'w4b_official_macro_truth_automation_protocol_v1.json').read_text())
AS_OF=date.fromisoformat(PROTO['date'])
ELIGIBLE={(v['family'],subject):v for subject,v in PROTO['eligible_subjects'].items()}
QUEUE=R/'w4b_official_event_truth_queue_v1.csv.gz'; TEMPLATE=R/'w4b_official_event_truth_decisions_template_v1.csv'; OCC=R/'w4b_official_macro_occurrences_v1.csv.gz'; OUT=R/'w4b_official_event_truth_decisions_v1.csv'; SUMMARY=R/'w4b_official_truth_decision_generation_summary_v1.json'
if OUT.exists(): raise SystemExit('DECISIONS_ALREADY_EXIST_FAIL_CLOSED')
with gzip.open(QUEUE,'rt',encoding='utf-8',newline='') as f:q=list(csv.DictReader(f))
with TEMPLATE.open('r',encoding='utf-8',newline='') as f:t=list(csv.DictReader(f)); fields=list(t[0].keys())
with gzip.open(OCC,'rt',encoding='utf-8',newline='') as f:o=list(csv.DictReader(f))
assert len(q)==len(t)==2275
by_t={r['exact_group_id']:r for r in t}; assert len(by_t)==2275
by_occ=defaultdict(list)
for r in o: by_occ[(r['resolved_family'],r['normalized_subject_key'])].append(r)
for k in by_occ: by_occ[k].sort(key=lambda r:r['official_event_reference_date'])
states=Counter(); verified_family=Counter(); deltas=Counter(); candidate_hist=Counter(); out=[]
for qr in q:
    gid=qr['exact_group_id']; row=dict(by_t[gid]); fam=qr['resolved_family']; sub=qr['normalized_subject_key']; pd=date.fromisoformat(qr['pretruth_event_reference_date']); key=(fam,sub)
    row['official_subject_key']=sub
    if pd>AS_OF:
        state='NOT_HISTORICAL_YET'; row.update(verification_state=state,verification_reason=f'pretruth_date={pd.isoformat()} after frozen as_of={AS_OF.isoformat()}',review_mode='FAIL_CLOSED_NOT_HISTORICAL_YET')
    elif key not in ELIGIBLE:
        state='UNRESOLVED_OFFICIAL_TRUTH'; row.update(verification_state=state,verification_reason='nonmacro automatic verification is outside W4B-OET-MACRO-v1.0 and remains fail-closed',review_mode='FAIL_CLOSED_NONMACRO_NOT_AUTOMATED')
    else:
        candidate_hist[fam]+=1; cand=[]
        for ev in by_occ.get(key,[]):
            od=date.fromisoformat(ev['official_event_reference_date']); dd=abs((od-pd).days)
            if od<=AS_OF and dd<=PROTO['matching']['maximum_absolute_date_distance_days']: cand.append((dd,od,ev))
        cand.sort(key=lambda x:(x[0],x[1]))
        if len(cand)==1:
            dd,od,ev=cand[0]; state='VERIFIED_OFFICIAL_TRUTH'; verified_family[fam]+=1; deltas[str(dd)]+=1
            row.update(verification_state=state,official_event_reference_date=od.isoformat(),official_event_timestamp_utc_if_published='',official_subject_key=sub,source_authority=ev['source_authority'],source_url=ev['source_url'],retrieved_at_utc=ev['retrieved_at_utc'],source_body_sha256_or_document_hash=ev['source_body_sha256'],evidence_excerpt_hash_or_structured_field_reference=ev['structured_release_date_reference']+f';pretruth_date={pd.isoformat()};official_date={od.isoformat()};absolute_date_delta_days={dd}',verification_reason=f'unique primary official occurrence within frozen +/-3 calendar-day window; absolute_date_delta_days={dd}',review_mode=PROTO['evidence']['review_mode'])
        else:
            state='UNRESOLVED_OFFICIAL_TRUTH'; reason='zero primary official occurrences within frozen +/-3 calendar-day window' if not cand else f'{len(cand)} primary official occurrences within frozen +/-3 calendar-day window; multiple candidates fail closed'
            row.update(verification_state=state,verification_reason=reason,review_mode=PROTO['evidence']['review_mode'])
    states[state]+=1; out.append(row)
assert len(out)==2275 and sum(states.values())==2275
with OUT.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
summary={'artifact':'W4B_OFFICIAL_TRUTH_DECISION_GENERATION_SUMMARY','version':'W4B-OET-DECGEN-v1.0','as_of_date':AS_OF.isoformat(),'queue_rows':len(q),'occurrence_rows':len(o),'decision_state_counts':dict(states),'historical_macro_candidates_by_family':dict(sorted(candidate_hist.items())),'verified_by_family':dict(sorted(verified_family.items())),'verified_absolute_date_delta_counts':dict(sorted(deltas.items())),'performance_blind':True,'prediction_market_performance_read':False,'prediction_market_settlement_result_used':False,'linked_asset_realized_returns_read':False,'economic_release_values_read':False,'nonmacro_automatically_verified':False,'matching_rule':'same exact family+subject; exactly one primary occurrence within +/-3 calendar days; otherwise unresolved; future after 2026-08-13 is NOT_HISTORICAL_YET'}
SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n'); print(json.dumps(summary,indent=2,sort_keys=True))

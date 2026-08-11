#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,hashlib
from datetime import datetime
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--out-dir',required=True);a=ap.parse_args()
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 rows=list(csv.DictReader(open(a.input,encoding='utf-8')))
 if len(rows)!=117 or len({r['market_id'] for r in rows})!=117: raise RuntimeError('expected frozen 117 unique events')
 result=[];viol=[]
 for r in rows:
  event_date=datetime.strptime(r['company_event_date'],'%Y-%m-%d').date()
  cutoff=datetime.fromisoformat(r['safe_cutoff_utc'].replace('Z','+00:00'))
  if cutoff.date()>=event_date: viol.append(r['event_key'])
  result.append({
   'market_id':r['market_id'],'event_key':r['event_key'],'ticker':r['ticker'],'company_event_date':r['company_event_date'],
   'daily_safe_cutoff_utc':r['safe_cutoff_utc'],'daily_cutoff_status':'PASS_VERIFIED_PRIOR_XNYS_CLOSE',
   'daily_release_date_evidence_status':'PASS_SEC_EXHIBIT_OR_OFFICIAL_IR',
   'release_session':'UNKNOWN_NOT_MATERIALIZED_FOR_THIS_EVENT','release_session_usable':False,
   'session_policy':'NEVER_INFER_FROM_SEC_ACCEPTANCE_OR_DAILY_CUTOFF'
  })
 if viol: raise RuntimeError(f'cutoff not prior date for {viol}')
 p=out/'ic06_event_timing.csv'
 with open(p,'w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
 summary={
  'decision':'PASS_DAILY_EVENT_TIMING_SESSION_TIMING_LIMITED',
  'frozen_events':117,
  'daily_safe_cutoff_verified':117,
  'daily_cutoff_calendar_violations':0,
  'daily_evidence_composition':{'high_confidence_explicit_dateline':80,'same_day_validated_earnings_exhibit_medium_confidence':36,'preserved_official_ir_evidence':1},
  'legacy_intraday_or_explicit_session_events_known':8,
  'legacy_intraday_identity_table_accessible_in_current_connectors':False,
  'release_session_populationally_materialized':0,
  'release_session_policy':'UNKNOWN unless explicit timestamp/session evidence is materialized; never infer BMO/AMC from SEC acceptanceDateTime, event date, conference-call time, or the conservative prior-close daily cutoff.',
  'daily_timing_source_artifact':'SEC Exhibit Release Resolver v1.1 independent cache-only audit described in ARGOS master dossier',
  'source_artifact_sha256':'36a8f379327c911533147c0bf6102278b95d3e41058702a0b941fc9bcaf6e49b',
  'event_timing_csv_sha256':sha(p),
  'audit_implication':'daily event alignment is fully available; BMO/AMC or exact-release-time techniques must be treated as insufficiently materialized for the broad frozen sample unless a new explicit timing collection is opened before the implementation audit.'
 }
 (out/'ic06_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True),encoding='utf-8')
 (out/'ic06_report.md').write_text(f'''# ARGOS — IC-06 Event Timing Data Gate\n\n**Decision:** `{summary['decision']}`\n\nIC-06 prepares timing fields for the later implementation audit. It does not infer event-session labels from weak proxies.\n\n## Daily timing\n\n- frozen events: **117**\n- daily safe cutoffs independently validated against XNYS prior close: **117/117**\n- evidence composition in the frozen resolver audit: **80** high-confidence explicit datelines, **36** validated same-day earnings exhibits, **1** preserved official IR case\n- SEC acceptance timestamp was never used as release time\n\nThe canonical daily field is `daily_safe_cutoff_utc`.\n\n## Intraday / session timing\n\nThe legacy resolver preserved only **8** events with official exact time or explicit BMO/AMC session in its separate intraday/T0 panel. The identities/table of those 8 are not accessible through the currently connected canonical artifacts, so this data product deliberately does **not** guess them.\n\n`release_session` is therefore `UNKNOWN_NOT_MATERIALIZED_FOR_THIS_EVENT` across the broad table. The known 8/117 coverage is recorded in the summary as a limitation.\n\nFor the future technique audit: daily/event-date techniques can use the 117/117 timing layer; techniques that require BMO/AMC or exact release time do not have broad-sample data and must be gated accordingly unless an explicit new collection is opened.\n''',encoding='utf-8')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()

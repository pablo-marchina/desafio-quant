#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,json,statistics,urllib.parse,concurrent.futures
from datetime import datetime,timezone
from pathlib import Path
import ic04_dense_price_history_audit as base

WORKERS=10
CHUNK_SECONDS=5*24*60*60

def event_worker(args):
 idx,e,ic02,out=args
 mid=e['market_id'];g=json.load(open(ic02/'raw/gamma'/f'{mid}.json',encoding='utf-8'))
 labels=base.jlist(g['outcomes']);tokens=[str(x) for x in base.jlist(g['clobTokenIds'])]
 if len(labels)!=2 or len(tokens)!=2:raise RuntimeError(f'nonbinary {e["event_key"]}')
 mapping={str(lbl).strip().lower():tok for lbl,tok in zip(labels,tokens)}
 if 'yes' not in mapping or 'no' not in mapping:raise RuntimeError(f'no yes/no mapping {e["event_key"]}: {labels}')
 cutoff=base.parse_dt(e['safe_cutoff_utc']);start=base.parse_dt(g['startDate']) if g.get('startDate') else None
 structurally_unavailable=bool(start is not None and start>cutoff);event_rows=[];manifest=[];errors=[];stats={}
 for label in ('yes','no'):
  tok=mapping[label];status='MARKET_NOT_YET_OPEN' if structurally_unavailable else 'OK';merged={};raw_points=0;boundary_duplicates=0;conflicts=0;chunk_count=0
  if not structurally_unavailable:
   lo=max(0,(start or cutoff-31*86400)-3600);chunk=0
   while lo<cutoff:
    hi=min(lo+CHUNK_SECONDS,cutoff);q=urllib.parse.urlencode({'market':tok,'startTs':lo,'endTs':hi,'fidelity':1});url=base.BASE+'?'+q
    try:
     body=base.fetch(url);rpath=out/'raw'/f'{mid}_{label}_{chunk:03d}.json';rpath.write_bytes(body);manifest.append({'path':str(rpath.relative_to(out)),'bytes':rpath.stat().st_size,'sha256':base.sha(rpath),'market_id':mid,'event_key':e['event_key'],'token_label':label,'token_id':tok,'chunk_index':chunk,'start_ts':lo,'end_ts':hi,'request_url':url});hist=json.loads(body).get('history',[])
     if not isinstance(hist,list):raise RuntimeError('history not list')
     raw_points+=len(hist);chunk_count+=1
     for pt in hist:
      t=int(pt['t']);p=float(pt['p'])
      if t in merged:
       boundary_duplicates+=1
       if abs(merged[t]-p)>1e-12:conflicts+=1
      else:merged[t]=p
    except Exception as ex:
     status='ERROR';errors.append({'market_id':mid,'event_key':e['event_key'],'token_label':label,'token_id':tok,'chunk_index':chunk,'start_ts':lo,'end_ts':hi,'error':repr(ex),'request_url':url})
    if hi==cutoff:break
    lo=hi;chunk+=1
  history=sorted(merged.items());bad=sum(int(t>cutoff or p<0 or p>1) for t,p in history)
  for t,p in history:event_rows.append({'market_id':mid,'event_key':e['event_key'],'ticker':e['ticker'],'company_event_date':e['company_event_date'],'safe_cutoff_utc':e['safe_cutoff_utc'],'token_label':label.upper(),'token_id':tok,'timestamp':t,'timestamp_utc':datetime.fromtimestamp(t,timezone.utc).isoformat().replace('+00:00','Z'),'price':format(p,'.12g')})
  ts=[t for t,_ in history];gaps=[(b-a)/60 for a,b in zip(ts,ts[1:])]
  stats[label]={'status':status,'rows':len(history),'raw_points':raw_points,'chunk_count':chunk_count,'boundary_duplicates':boundary_duplicates,'conflicting_duplicate_timestamps':conflicts,'bad_rows':bad,'last_age_min':(cutoff-ts[-1])/60 if ts else None,'first_delay_min':(ts[0]-start)/60 if ts and start else None,'median_gap_min':statistics.median(gaps) if gaps else None,'p95_gap_min':base.percentile(gaps,.95),'max_gap_min':max(gaps) if gaps else None,'unique_prices':len({p for _,p in history})}
 y=stats['yes'];n=stats['no']
 summary={'market_id':mid,'event_key':e['event_key'],'ticker':e['ticker'],'safe_cutoff_utc':e['safe_cutoff_utc'],'gamma_start_utc':g.get('startDate',''),'structurally_unavailable':structurally_unavailable,'yes_rows':y['rows'],'no_rows':n['rows'],'yes_raw_points':y['raw_points'],'no_raw_points':n['raw_points'],'yes_chunks':y['chunk_count'],'no_chunks':n['chunk_count'],'yes_boundary_duplicates':y['boundary_duplicates'],'no_boundary_duplicates':n['boundary_duplicates'],'yes_conflicting_duplicates':y['conflicting_duplicate_timestamps'],'no_conflicting_duplicates':n['conflicting_duplicate_timestamps'],'yes_bad_rows':y['bad_rows'],'no_bad_rows':n['bad_rows'],'yes_last_age_min':y['last_age_min'],'no_last_age_min':n['last_age_min'],'yes_first_delay_min':y['first_delay_min'],'yes_median_gap_min':y['median_gap_min'],'yes_p95_gap_min':y['p95_gap_min'],'yes_max_gap_min':y['max_gap_min'],'yes_unique_prices':y['unique_prices'],'yes_status':y['status'],'no_status':n['status']}
 return idx,event_rows,summary,manifest,errors

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--ic02-dir',required=True);ap.add_argument('--input',required=True);ap.add_argument('--output-dir',required=True);a=ap.parse_args()
 ic02=Path(a.ic02_dir);out=Path(a.output_dir);(out/'raw').mkdir(parents=True,exist_ok=True);events=list(csv.DictReader(open(a.input,encoding='utf-8')))
 if len(events)!=117:raise RuntimeError(f'expected 117 got {len(events)}')
 results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
  futs=[ex.submit(event_worker,(i,e,ic02,out)) for i,e in enumerate(events,1)]
  done=0
  for f in concurrent.futures.as_completed(futs):
   results.append(f.result());done+=1
   if done%10==0 or done==117:print('events',done,'/117',flush=True)
 results.sort(key=lambda x:x[0]);rows=[];summary=[];manifest=[];errors=[]
 for _,rs,s,ms,es in results:rows.extend(rs);summary.append(s);manifest.extend(ms);errors.extend(es)
 rows.sort(key=lambda r:(r['event_key'],r['token_label'],int(r['timestamp'])));manifest.sort(key=lambda r:(r['event_key'],r['token_label'],int(r['chunk_index'])))
 if errors:base.write_csv(out/'ic04_errors.csv',errors)
 base.write_csv(out/'ic04_event_summary.csv',summary);base.write_csv(out/'ic04_raw_manifest.csv',manifest);base.write_csv(out/'ic04_dense_prices.csv',rows)
 with open(out/'ic04_dense_prices.csv','rb') as src,gzip.open(out/'ic04_dense_prices.csv.gz','wb') as dst:
  for b in iter(lambda:src.read(1<<20),b''):dst.write(b)
 yes=[r for r in rows if r['token_label']=='YES'];base.write_csv(out/'ic04_yes_probability_trajectory.csv',yes)
 with open(out/'ic04_yes_probability_trajectory.csv','rb') as src,gzip.open(out/'ic04_yes_probability_trajectory.csv.gz','wb') as dst:
  for b in iter(lambda:src.read(1<<20),b''):dst.write(b)
 yes_events=sum(int(r['yes_rows'])>0 for r in summary);no_events=sum(int(r['no_rows'])>0 for r in summary);unavail=[r['event_key'] for r in summary if r['structurally_unavailable']];zero_yes=[r['event_key'] for r in summary if not r['structurally_unavailable'] and int(r['yes_rows'])==0];ages=[float(r['yes_last_age_min']) for r in summary if r['yes_last_age_min'] not in (None,'')];gaps=[float(r['yes_median_gap_min']) for r in summary if r['yes_median_gap_min'] not in (None,'')];conflicts=sum(int(r['yes_conflicting_duplicates'])+int(r['no_conflicting_duplicates']) for r in summary);bad=sum(int(r['yes_bad_rows'])+int(r['no_bad_rows']) for r in summary)
 decision='PASS_DENSE_PRICE_HISTORY_WITH_DISCLOSED_GAPS' if not errors and not conflicts and not bad and yes_events>=115 else 'REVIEW_DENSE_PRICE_HISTORY'
 s={'decision':decision,'events':117,'structurally_unavailable_events':unavail,'yes_events_with_history':yes_events,'no_events_with_history':no_events,'zero_yes_history_despite_open_market':zero_yes,'api_errors':len(errors),'conflicting_chunk_duplicates':conflicts,'bad_price_or_timestamp_rows':bad,'total_price_rows_both_tokens':len(rows),'total_yes_rows':len(yes),'median_yes_rows_per_available_event':statistics.median([int(r['yes_rows']) for r in summary if int(r['yes_rows'])>0]) if yes_events else None,'median_yes_gap_minutes_across_events':statistics.median(gaps) if gaps else None,'median_last_yes_point_age_minutes_at_cutoff':statistics.median(ages) if ages else None,'max_last_yes_point_age_minutes_at_cutoff':max(ages) if ages else None,'chunk_seconds':CHUNK_SECONDS,'raw_chunk_files':len(manifest),'dense_prices_sha256':base.sha(out/'ic04_dense_prices.csv.gz'),'yes_trajectory_sha256':base.sha(out/'ic04_yes_probability_trajectory.csv.gz'),'raw_manifest_sha256':base.sha(out/'ic04_raw_manifest.csv'),'retrieval_workers':WORKERS}
 (out/'ic04_summary.json').write_text(json.dumps(s,indent=2,sort_keys=True),encoding='utf-8');(out/'ic04_report.md').write_text(f'''# ARGOS — IC-04 Dense Price-History Data Gate\n\n**Decision:** `{decision}`\n\nThe full frozen panel was queried using absolute `startTs/endTs` windows split uniformly into fixed 5-day chunks at `fidelity=1`. Chunking is a retrieval strategy only; duplicated boundary timestamps are deduplicated and any conflicting price at the same timestamp is a hard review condition. No outcome, equity return or feature performance is used.\n\n- frozen events: 117\n- YES history available: {yes_events}/117\n- NO history available: {no_events}/117\n- structurally unavailable before cutoff: {len(unavail)} — {', '.join(unavail) if unavail else 'none'}\n- open-market events with zero YES history: {len(zero_yes)}\n- API errors: {len(errors)}\n- conflicting boundary duplicates: {conflicts}\n- invalid/post-cutoff rows: {bad}\n- total YES observations: {len(yes):,}\n- total YES+NO observations: {len(rows):,}\n- median YES observations per available event: {s['median_yes_rows_per_available_event']}\n- median within-event YES gap: {s['median_yes_gap_minutes_across_events']} minutes\n- median age of last YES observation at safe cutoff: {s['median_last_yes_point_age_minutes_at_cutoff']} minutes\n- maximum age of last YES observation at safe cutoff: {s['max_last_yes_point_age_minutes_at_cutoff']} minutes\n\n`fidelity=1` is not assumed to imply a regular grid. Actual gaps are measured. Canonical trajectory for the later implementation audit is `data/ic04_yes_probability_trajectory.csv.gz`; raw chunk responses and hashes are retained separately.\n''',encoding='utf-8')
 print(json.dumps(s,indent=2),flush=True)
 if decision=='REVIEW_DENSE_PRICE_HISTORY':raise SystemExit(2)
if __name__=='__main__':main()

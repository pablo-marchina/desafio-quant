#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,statistics,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path

BASE='https://clob.polymarket.com/prices-history'

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def parse_dt(v):return int(datetime.fromisoformat(str(v).replace('Z','+00:00')).timestamp())
def jlist(v):
 if isinstance(v,list):return v
 if isinstance(v,str):return json.loads(v)
 raise TypeError(type(v))
def fetch(url,attempts=8):
 err=None
 for a in range(attempts):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'ARGOS-IC04/1.0'})
   with urllib.request.urlopen(req,timeout=45) as r:return r.read()
  except Exception as e:err=e;time.sleep(min(.4*2**a,8))
 raise RuntimeError(f'{url}: {err}')
def percentile(x,q):
 if not x:return None
 y=sorted(x);k=(len(y)-1)*q;lo=math.floor(k);hi=math.ceil(k)
 return y[lo] if lo==hi else y[lo]*(hi-k)+y[hi]*(k-lo)
def write_csv(p,rows,fields=None):
 p.parent.mkdir(parents=True,exist_ok=True);fields=fields or list(rows[0])
 with open(p,'w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--ic02-dir',required=True);ap.add_argument('--input',required=True);ap.add_argument('--output-dir',required=True);a=ap.parse_args()
 ic02=Path(a.ic02_dir);out=Path(a.output_dir);rawdir=out/'raw';rawdir.mkdir(parents=True,exist_ok=True)
 events=list(csv.DictReader(open(a.input,encoding='utf-8')))
 if len(events)!=117:raise RuntimeError(f'expected 117 events got {len(events)}')
 rows=[];summary=[];manifest=[];errors=[]
 for i,e in enumerate(events,1):
  mid=e['market_id'];gpath=ic02/'raw/gamma'/f'{mid}.json';g=json.load(open(gpath,encoding='utf-8'))
  labels=jlist(g['outcomes']);tokens=[str(x) for x in jlist(g['clobTokenIds'])]
  if len(labels)!=2 or len(tokens)!=2:raise RuntimeError(f'nonbinary {e["event_key"]}')
  mapping={str(lbl).strip().lower():tok for lbl,tok in zip(labels,tokens)}
  if 'yes' not in mapping or 'no' not in mapping:raise RuntimeError(f'no yes/no mapping {e["event_key"]}: {labels}')
  cutoff=parse_dt(e['safe_cutoff_utc']);start=parse_dt(g['startDate']) if g.get('startDate') else None
  event_rows=[];token_stats={}
  structurally_unavailable=bool(start is not None and start>cutoff)
  for label in ('yes','no'):
   tok=mapping[label]
   history=[];status='MARKET_NOT_YET_OPEN' if structurally_unavailable else 'OK'
   url=''
   if not structurally_unavailable:
    start_ts=max(0,(start or cutoff-31*86400)-3600)
    q=urllib.parse.urlencode({'market':tok,'startTs':start_ts,'endTs':cutoff,'fidelity':1})
    url=BASE+'?'+q
    try:
     body=fetch(url);rpath=rawdir/f'{mid}_{label}.json';rpath.write_bytes(body);manifest.append({'path':str(rpath.relative_to(out)),'bytes':rpath.stat().st_size,'sha256':sha(rpath),'market_id':mid,'event_key':e['event_key'],'token_label':label,'token_id':tok,'request_url':url})
     obj=json.loads(body);history=obj.get('history',[])
     if not isinstance(history,list):raise RuntimeError('history not list')
    except Exception as ex:
     status='ERROR';errors.append({'market_id':mid,'event_key':e['event_key'],'token_label':label,'token_id':tok,'error':repr(ex),'request_url':url});history=[]
   seen=set();bad=0;dup=0;ordered=True;last=None
   for pt in history:
    t=int(pt['t']);p=float(pt['p'])
    if t in seen:dup+=1
    seen.add(t)
    if last is not None and t<last:ordered=False
    last=t
    if t>cutoff or p<0 or p>1:bad+=1
    event_rows.append({'market_id':mid,'event_key':e['event_key'],'ticker':e['ticker'],'company_event_date':e['company_event_date'],'safe_cutoff_utc':e['safe_cutoff_utc'],'token_label':label.upper(),'token_id':tok,'timestamp':t,'timestamp_utc':datetime.fromtimestamp(t,timezone.utc).isoformat().replace('+00:00','Z'),'price':format(p,'.12g')})
   ts=sorted(set(int(pt['t']) for pt in history));gaps=[(b-a)/60 for a,b in zip(ts,ts[1:])]
   token_stats[label]={'status':status,'rows':len(history),'unique_timestamps':len(ts),'duplicate_timestamps':dup,'bad_rows':bad,'raw_ordered':ordered,'first_t':ts[0] if ts else None,'last_t':ts[-1] if ts else None,'last_age_min':(cutoff-ts[-1])/60 if ts else None,'first_delay_min':(ts[0]-start)/60 if ts and start else None,'median_gap_min':statistics.median(gaps) if gaps else None,'p95_gap_min':percentile(gaps,.95),'max_gap_min':max(gaps) if gaps else None,'unique_prices':len({float(pt['p']) for pt in history})}
  rows.extend(event_rows)
  y=token_stats['yes'];n=token_stats['no']
  summary.append({'market_id':mid,'event_key':e['event_key'],'ticker':e['ticker'],'safe_cutoff_utc':e['safe_cutoff_utc'],'gamma_start_utc':g.get('startDate',''),'structurally_unavailable':structurally_unavailable,'yes_rows':y['rows'],'no_rows':n['rows'],'yes_unique_timestamps':y['unique_timestamps'],'no_unique_timestamps':n['unique_timestamps'],'yes_duplicate_timestamps':y['duplicate_timestamps'],'no_duplicate_timestamps':n['duplicate_timestamps'],'yes_bad_rows':y['bad_rows'],'no_bad_rows':n['bad_rows'],'yes_last_age_min':y['last_age_min'],'no_last_age_min':n['last_age_min'],'yes_first_delay_min':y['first_delay_min'],'yes_median_gap_min':y['median_gap_min'],'yes_p95_gap_min':y['p95_gap_min'],'yes_max_gap_min':y['max_gap_min'],'yes_unique_prices':y['unique_prices'],'yes_status':y['status'],'no_status':n['status']})
  print(f'[{i}/117] {e["event_key"]} yes={token_stats["yes"]["rows"]} no={token_stats["no"]["rows"]}',flush=True)
 if errors:write_csv(out/'ic04_errors.csv',errors)
 write_csv(out/'ic04_event_summary.csv',summary)
 write_csv(out/'ic04_raw_manifest.csv',manifest)
 write_csv(out/'ic04_dense_prices.csv',rows)
 with open(out/'ic04_dense_prices.csv','rb') as src,gzip.open(out/'ic04_dense_prices.csv.gz','wb') as dst:
  for b in iter(lambda:src.read(1<<20),b''):dst.write(b)
 yes=[r for r in rows if r['token_label']=='YES'];write_csv(out/'ic04_yes_probability_trajectory.csv',yes)
 with open(out/'ic04_yes_probability_trajectory.csv','rb') as src,gzip.open(out/'ic04_yes_probability_trajectory.csv.gz','wb') as dst:
  for b in iter(lambda:src.read(1<<20),b''):dst.write(b)
 yes_events=sum(int(r['yes_rows'])>0 for r in summary);no_events=sum(int(r['no_rows'])>0 for r in summary);unavail=[r['event_key'] for r in summary if r['structurally_unavailable']]
 zero_yes=[r['event_key'] for r in summary if not r['structurally_unavailable'] and int(r['yes_rows'])==0];api_errors=len(errors)
 ages=[float(r['yes_last_age_min']) for r in summary if r['yes_last_age_min'] not in (None,'')]
 gaps=[float(r['yes_median_gap_min']) for r in summary if r['yes_median_gap_min'] not in (None,'')]
 total_yes=len(yes);total_all=len(rows)
 decision='PASS_DENSE_PRICE_HISTORY_WITH_DISCLOSED_GAPS' if api_errors==0 and yes_events>=115 and all(int(r['yes_bad_rows'])==0 and int(r['no_bad_rows'])==0 for r in summary) else 'REVIEW_DENSE_PRICE_HISTORY'
 s={'decision':decision,'events':117,'structurally_unavailable_events':unavail,'yes_events_with_history':yes_events,'no_events_with_history':no_events,'zero_yes_history_despite_open_market':zero_yes,'api_errors':api_errors,'total_price_rows_both_tokens':total_all,'total_yes_rows':total_yes,'median_yes_rows_per_available_event':statistics.median([int(r['yes_rows']) for r in summary if int(r['yes_rows'])>0]) if yes_events else None,'median_yes_gap_minutes_across_events':statistics.median(gaps) if gaps else None,'median_last_yes_point_age_minutes_at_cutoff':statistics.median(ages) if ages else None,'max_last_yes_point_age_minutes_at_cutoff':max(ages) if ages else None,'dense_prices_sha256':sha(out/'ic04_dense_prices.csv.gz'),'yes_trajectory_sha256':sha(out/'ic04_yes_probability_trajectory.csv.gz'),'raw_files':len(manifest),'raw_manifest_sha256':sha(out/'ic04_raw_manifest.csv')}
 (out/'ic04_summary.json').write_text(json.dumps(s,indent=2,sort_keys=True),encoding='utf-8')
 (out/'ic04_report.md').write_text(f'''# ARGOS — IC-04 Dense Price-History Data Gate\n\n**Decision:** `{decision}`\n\nThis gate prepares historical Polymarket price trajectories for the later implementation audit. It does not compute anomaly features and does not inspect event outcomes or equity returns.\n\n- frozen events: 117\n- YES history available: {yes_events}/117\n- NO history available: {no_events}/117\n- structurally unavailable before cutoff: {len(unavail)} — {', '.join(unavail) if unavail else 'none'}\n- open-market events with zero YES history: {len(zero_yes)}\n- API errors: {api_errors}\n- total YES observations: {total_yes:,}\n- total YES+NO observations: {total_all:,}\n- median YES observations per available event: {s['median_yes_rows_per_available_event']}\n- median within-event YES gap: {s['median_yes_gap_minutes_across_events']} minutes\n- median age of last YES observation at safe cutoff: {s['median_last_yes_point_age_minutes_at_cutoff']} minutes\n- maximum age of last YES observation at safe cutoff: {s['max_last_yes_point_age_minutes_at_cutoff']} minutes\n\n`fidelity=1` is treated as a request parameter, not as proof of a regular one-minute grid. Actual gaps are measured event by event in `registry/ic04_event_summary.csv`.\n\nCanonical trajectory for later audit: `data/ic04_yes_probability_trajectory.csv.gz`. Raw YES and NO responses remain hashed separately for provenance.\n''',encoding='utf-8')
 print(json.dumps(s,indent=2),flush=True)
 if decision=='REVIEW_DENSE_PRICE_HISTORY':raise SystemExit(2)
if __name__=='__main__':main()

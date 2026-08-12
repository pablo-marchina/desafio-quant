#!/usr/bin/env python3
"""W2C PIT-v2 Layer A: public Polymarket historical platform evidence.

Reads only the allowlisted semantic population + PIT-v2 protocol. Does not read
performance, linked-asset prices/returns, F1-F9 results, IAS or W3 outputs.
"""
from __future__ import annotations
import csv, gzip, hashlib, io, json, time, urllib.error, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROTOCOL=Path('registry/w2c_pit_protocol_v2_0.json')
INPUT=Path('registry/w2c_semantic_v2_accepted_clusters_v1_1.csv')
OUT=Path('registry/w2c_pit_v2_platform_events.csv.gz')
RAW=Path('registry/w2c_pit_v2_platform_request_manifest.jsonl.gz')
SUMMARY=Path('registry/w2c_pit_v2_platform_summary.json')
VERSION='W2C-PIT-PLATFORM-RUN-v2.0'
UA='ARGOS-W2C-PIT-v2/2.0 public-research contact=pablo-marchina/desafio-quant'
RETRYABLE={429,500,502,503,504}


def sha256(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def utcnow(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def parse_tokens(v):
    if isinstance(v,list): return [str(x) for x in v if str(x)]
    if not v: return []
    try:
        z=json.loads(str(v))
        if isinstance(z,list): return [str(x) for x in z if str(x)]
    except Exception: pass
    return [x.strip().strip('"\'') for x in str(v).strip('[]').split(',') if x.strip().strip('"\'')]

def request_json(url, attempts=5, timeout=30):
    errors=[]
    for i in range(attempts):
        fetched=utcnow()
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=timeout) as resp:
                body=resp.read(); code=getattr(resp,'status',200)
            obj=json.loads(body.decode('utf-8'))
            time.sleep(.06)
            return obj, {'url':url,'fetched_utc':fetched,'http_status':code,'bytes':len(body),'sha256':sha256(body),'state':'PASS','errors':errors}
        except urllib.error.HTTPError as e:
            errors.append(f'HTTPError:{e.code}')
            if e.code not in RETRYABLE or i==attempts-1: break
        except (urllib.error.URLError,TimeoutError,json.JSONDecodeError,UnicodeDecodeError) as e:
            errors.append(type(e).__name__)
            if i==attempts-1: break
        time.sleep(.8*(2**i))
    return None, {'url':url,'fetched_utc':utcnow(),'http_status':None,'bytes':0,'sha256':'','state':'UNRESOLVED','errors':errors}

def epoch_to_iso(x):
    try: return datetime.fromtimestamp(float(x),timezone.utc).isoformat().replace('+00:00','Z')
    except Exception: return ''

def load_population(p):
    expected=p['population']['required_counts']; allowed=set(expected)
    rows=list(csv.DictReader(INPUT.open(encoding='utf-8',newline='')))
    out=[r for r in rows if r['resolved_family'] in allowed]
    counts=Counter(r['resolved_family'] for r in out)
    assert dict(counts)==expected and len(out)==260 and len({r['event_id'] for r in out})==260
    return out

def write_gz_csv(path, rows, fields):
    sio=io.StringIO(newline=''); w=csv.DictWriter(sio,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    with path.open('wb') as fh:
        with gzip.GzipFile(filename='',mode='wb',fileobj=fh,mtime=0) as gz: gz.write(sio.getvalue().encode())

def write_jsonl_gz(path, rows):
    with path.open('wb') as fh:
        with gzip.GzipFile(filename='',mode='wb',fileobj=fh,mtime=0) as gz:
            for r in rows: gz.write((json.dumps(r,sort_keys=True,separators=(',',':'))+'\n').encode())

def main():
    p=json.loads(PROTOCOL.read_text())
    assert p['performance_blind'] is True and p['version']=='W2C-PIT-v2.0'
    pop=load_population(p); events=[]; raw=[]
    for i,r in enumerate(pop,1):
        eid=str(r['event_id']); gamma_url=f"https://gamma-api.polymarket.com/events/{urllib.parse.quote(eid)}"
        gamma,meta=request_json(gamma_url); raw.append({'event_id':eid,'endpoint':'gamma_event',**meta})
        markets=(gamma or {}).get('markets',[]) if isinstance(gamma,dict) else []
        conds=[]; toks=[]
        for m in markets:
            if m.get('conditionId'): conds.append(str(m['conditionId']))
            toks.extend(parse_tokens(m.get('clobTokenIds')))
        conds=sorted(set(conds)); toks=sorted(set(toks))
        token_mins=[]; token_maxs=[]; histories=0; price_unresolved=0
        for tok in toks:
            q=urllib.parse.urlencode({'market':tok,'interval':'all','fidelity':1})
            url='https://clob.polymarket.com/prices-history?'+q
            hist,hm=request_json(url); raw.append({'event_id':eid,'token_id':tok,'endpoint':'clob_prices_history',**hm})
            if hist is None:
                price_unresolved+=1; continue
            pts=(hist or {}).get('history') if isinstance(hist,dict) else None
            ts=[]
            if isinstance(pts,list):
                for z in pts:
                    try: ts.append(float(z.get('t')))
                    except Exception: pass
            if ts:
                histories+=1; token_mins.append(min(ts)); token_maxs.append(max(ts))
        mapping_conflict = len(conds)==0 or len(toks)==0
        if meta['state']!='PASS': state='UNRESOLVED'
        elif mapping_conflict: state='UNRESOLVED'
        elif histories>0: state='PASS_HISTORY_OBSERVED'
        elif price_unresolved>0: state='UNRESOLVED'
        else: state='NO_PRICE_HISTORY_OBSERVED'
        events.append({
          'event_id':eid,'resolved_family':r['resolved_family'],'independence_cluster_id':r['independence_cluster_id'],'title':r['title'],'slug':r['slug'],'semantic_end_utc':r['end_utc'],
          'gamma_state':meta['state'],'nested_market_count':len(markets),'pm_condition_ids':'|'.join(conds),'pm_token_ids':'|'.join(toks),
          'pm_mapping_conflict':'true' if mapping_conflict else 'false','tokens_with_price_history':histories,'tokens_unresolved':price_unresolved,
          'pm_earliest_verified_history_utc':epoch_to_iso(min(token_mins)) if token_mins else '',
          'pm_latest_verified_history_utc':epoch_to_iso(max(token_maxs)) if token_maxs else '',
          'pm_platform_collection_state':state
        })
        if i%20==0: print(f'platform {i}/{len(pop)}',flush=True)
    fields=list(events[0])
    write_gz_csv(OUT,events,fields); write_jsonl_gz(RAW,raw)
    fam=defaultdict(Counter)
    for x in events:
        f=x['resolved_family']; fam[f]['n']+=1; fam[f][x['pm_platform_collection_state']]+=1
        if x['pm_mapping_conflict']=='true': fam[f]['mapping_conflict_or_unresolved']+=1
    summary={'artifact':'W2C_PIT_V2_PLATFORM_MATERIALIZATION','version':VERSION,'protocol_version':p['version'],'performance_blind':True,'science_reopened':False,'rows':len(events),'family_summary':{k:dict(v) for k,v in sorted(fam.items())},'f1_f9_scored':False,'ias_computed':False,'w3_selected':False,'linked_asset_realized_returns_read':False}
    SUMMARY.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()

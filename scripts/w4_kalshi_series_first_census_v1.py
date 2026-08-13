#!/usr/bin/env python3
from __future__ import annotations

import json, re, time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'registry'
P=json.loads((REG/'w4_backtest_expansion_research_protocol_v1.json').read_text())
FAMS=P['frozen_family_dictionary']
BASE='https://external-api.kalshi.com/trade-api/v2'
UA='ARGOS-W4-series-first/1.0'

def get(url,retries=4):
    err=None
    for i in range(retries):
        try:
            with urlopen(Request(url,headers={'User-Agent':UA,'Accept':'application/json'}),timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            err=e; time.sleep(1.2*(i+1))
    raise RuntimeError(f'{url}: {err}')

def norm(s):
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9%+.-]+',' ',(s or '').lower())).strip()

def classify(text):
    t=norm(text); out=[]
    for fam,kws in FAMS.items():
        if any(norm(k) in t for k in kws): out.append(fam)
    return out

def historical_markets(series_ticker,max_pages=500):
    cursor=''; page=0; markets=[]
    while page<max_pages:
        q={'limit':1000,'series_ticker':series_ticker,'mve_filter':'exclude'}
        if cursor: q['cursor']=cursor
        obj=get(BASE+'/historical/markets?'+urlencode(q))
        batch=obj.get('markets',[]); markets.extend(batch); page+=1
        cursor=obj.get('cursor') or ''
        if not cursor or not batch: break
    return markets, page, bool(cursor)

def live_settled_markets(series_ticker,max_pages=100):
    cursor=''; page=0; markets=[]
    while page<max_pages:
        q={'limit':1000,'series_ticker':series_ticker,'status':'settled','mve_filter':'exclude'}
        if cursor: q['cursor']=cursor
        obj=get(BASE+'/markets?'+urlencode(q))
        batch=obj.get('markets',[]); markets.extend(batch); page+=1
        cursor=obj.get('cursor') or ''
        if not cursor or not batch: break
    return markets,page,bool(cursor)

def main():
    series=get(BASE+'/series').get('series',[])
    selected=[]
    for s in series:
        text=' '.join([str(s.get('title') or ''),str(s.get('category') or ''),' '.join(s.get('tags') or [])])
        hits=classify(text)
        for fam in hits:
            selected.append({'family':fam,'series_ticker':s.get('ticker'),'series_title':s.get('title') or '', 'frequency':s.get('frequency') or '', 'category':s.get('category') or ''})
    # fetch each unique series once, then assign event set to every frozen family hit
    series_hits=defaultdict(list)
    for r in selected: series_hits[r['series_ticker']].append(r['family'])
    event_sets=defaultdict(set); market_counts=Counter(); telemetry=[]
    for st,fams in sorted(series_hits.items()):
        hist,hp,ht=historical_markets(st)
        live,lp,lt=live_settled_markets(st)
        mk={m.get('ticker'):m for m in hist+live if m.get('ticker')}
        ev={m.get('event_ticker') for m in mk.values() if m.get('event_ticker')}
        for fam in fams:
            event_sets[fam].update(ev); market_counts[fam]+=len(mk)
        telemetry.append({'series_ticker':st,'families':sorted(set(fams)),'historical_pages':hp,'live_pages':lp,'historical_truncated':ht,'live_truncated':lt,'unique_markets':len(mk),'unique_events':len(ev)})
    out={
      'artifact':'W4_KALSHI_SERIES_FIRST_CAPACITY',
      'version':'W4-KSF-v1.0',
      'performance_blind':True,
      'realized_linked_asset_returns_read':False,
      'series_total_returned':len(series),
      'classified_series_rows':len(selected),
      'classified_unique_series':len(series_hits),
      'family_capacity':{fam:{'unique_events':len(event_sets[fam]),'unique_markets':market_counts[fam]} for fam in sorted(event_sets)},
      'selected_series':selected,
      'telemetry':telemetry,
      'interpretation':'Discovery capacity only. Series classification uses the already-frozen W4-BER-v1.0 dictionary. Event counts are not semantic-valid or cross-venue-deduplicated backtest N.'
    }
    (REG/'w4_kalshi_series_first_capacity_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:out[k] for k in ['series_total_returned','classified_unique_series','family_capacity']},indent=2,sort_keys=True))
if __name__=='__main__': main()

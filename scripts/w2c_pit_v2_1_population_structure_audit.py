#!/usr/bin/env python3
"""Pre-v2.1 outcome/performance-blind population structure audit.

Quantifies right-censoring and explicit macro jurisdictions from the already-frozen
semantic population. It does not access network, outcomes, prices, PnL, or PIT results.
"""
from __future__ import annotations
import csv, json, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SRC=Path('registry/w2c_semantic_v2_accepted_clusters_v1_1.csv')
ASOF=datetime.fromisoformat('2026-08-12T20:00:00+00:00')
FAMS={'EARNINGS_EPS','FDA_FINAL_PDUFA_DECISION','MACRO_STATISTICAL_RELEASE'}

def dt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
def macro_jurisdiction(title,slug):
    s=(title+' '+slug).lower()
    rules=[
      ('BRAZIL',[r'\bbrazil\b',r'\bbrasil\b']),
      ('UNITED_KINGDOM',[r'\bu\.k\.\b',r'\buk\b',r'united kingdom']),
      ('EURO_AREA',[r'eurozone',r'euro area']),
      ('GERMANY',[r'\bgermany\b']),
      ('JAPAN',[r'\bjapan\b']),
      ('SOUTH_KOREA',[r'south korea',r'korea gdp']),
      ('CHINA',[r'\bchina\b']),
      ('MEXICO',[r'\bmexico\b']),
      ('INDIA',[r'\bindia\b',r'\bindian\b']),
      ('UNITED_STATES',[r'\bu\.s\.\b',r'\bus\b',r'united states',r'jobs added',r'jobs report',r'\bunemployment rate\b',r'\bcpi\b',r'\bppi\b',r'\binflation\b']),
    ]
    hits=[]
    for j,pats in rules:
        if any(re.search(p,s,re.I) for p in pats): hits.append(j)
    # Explicit non-US geography dominates generic macro terminology such as CPI/unemployment.
    non_us=[x for x in hits if x!='UNITED_STATES']
    if len(set(non_us))==1: return non_us[0]
    if len(set(non_us))>1: return 'AMBIGUOUS_EXPLICIT'
    return 'UNITED_STATES' if 'UNITED_STATES' in hits else 'UNRESOLVED'

def main():
    rows=[r for r in csv.DictReader(SRC.open(encoding='utf-8',newline='')) if r['resolved_family'] in FAMS]
    assert len(rows)==260
    fam=Counter(r['resolved_family'] for r in rows)
    future=Counter(); past=Counter(); macro=Counter(); macro_future=Counter()
    samples={}
    for r in rows:
        is_future=dt(r['end_utc'])>ASOF
        (future if is_future else past)[r['resolved_family']]+=1
        if r['resolved_family']=='MACRO_STATISTICAL_RELEASE':
            j=macro_jurisdiction(r['title'],r['slug']); macro[j]+=1
            if is_future: macro_future[j]+=1
            samples.setdefault(j,[])
            if len(samples[j])<3: samples[j].append({'event_id':r['event_id'],'title':r['title'],'end_utc':r['end_utc']})
    out={'artifact':'W2C_PIT_V2_1_POPULATION_STRUCTURE_AUDIT','asof_utc':ASOF.isoformat().replace('+00:00','Z'),'performance_blind':True,'science_reopened':False,'total':len(rows),'family_counts':dict(fam),'past_or_due_by_semantic_end':dict(past),'future_by_semantic_end':dict(future),'macro_jurisdiction_counts':dict(macro),'macro_future_counts':dict(macro_future),'macro_examples':samples}
    Path('registry/w2c_pit_v2_1_population_structure_audit.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
if __name__=='__main__': main()

#!/usr/bin/env python3
"""Deterministically materialize PIT-v2 primary-source adjudication queue."""
from __future__ import annotations
import csv, json, re
from collections import Counter
from pathlib import Path
P=Path('registry/w2c_pit_protocol_v2_0.json'); SRC=Path('registry/w2c_semantic_v2_accepted_clusters_v1_1.csv'); OUT=Path('registry/w2c_pit_v2_primary_source_queue.csv')

def ticker_hint(title,slug):
    m=re.search(r'\(([A-Z][A-Z0-9.\-]{0,7})\)',title or '')
    if m: return m.group(1)
    x=(slug or '').split('-')[0].upper()
    return x if re.fullmatch(r'[A-Z][A-Z0-9.]{0,7}',x or '') else ''
def macro_agency_hint(text):
    s=text.lower()
    if any(x in s for x in ['cpi','consumer price','employment','unemployment','payroll','jobs report','ppi']): return 'BLS'
    if any(x in s for x in ['gdp','personal income','pce','personal consumption']): return 'BEA'
    if any(x in s for x in ['retail sales','housing starts','new home sales','durable goods','trade deficit','factory orders']): return 'CENSUS'
    return 'UNRESOLVED'
def main():
    p=json.loads(P.read_text()); allowed=set(p['population']['include_families'])
    rows=[r for r in csv.DictReader(SRC.open(encoding='utf-8',newline='')) if r['resolved_family'] in allowed]
    assert len(rows)==260
    fields=['event_id','resolved_family','independence_cluster_id','title','slug','semantic_end_utc','ticker_hint','macro_agency_hint','revelation_state','revelation_precision','public_revelation_utc','revelation_source_type','revelation_source_url','revelation_response_sha256','resolution_state','resolution_source_type','resolution_source_url','resolution_response_sha256','resolution_ambiguous','linked_asset','linked_asset_mapping_state','linked_asset_mapping_basis','linked_asset_mapping_source_url','adjudication_notes']
    out=[]
    for r in rows:
        f=r['resolved_family']; th=ticker_hint(r['title'],r['slug']) if f=='EARNINGS_EPS' else ''
        ah=macro_agency_hint(r['title']+' '+r['slug']) if f=='MACRO_STATISTICAL_RELEASE' else ''
        out.append({**{k:r.get(k,'') for k in ['event_id','resolved_family','independence_cluster_id','title','slug']},'semantic_end_utc':r['end_utc'],'ticker_hint':th,'macro_agency_hint':ah,'revelation_state':'PENDING_PRIMARY_REVIEW','revelation_precision':'','public_revelation_utc':'','revelation_source_type':'','revelation_source_url':'','revelation_response_sha256':'','resolution_state':'PENDING_PRIMARY_REVIEW','resolution_source_type':'','resolution_source_url':'','resolution_response_sha256':'','resolution_ambiguous':'','linked_asset':'SPY' if f=='MACRO_STATISTICAL_RELEASE' else th,'linked_asset_mapping_state':'PASS_STRUCTURAL_FIXED' if f=='MACRO_STATISTICAL_RELEASE' else 'PENDING_PRIMARY_REVIEW','linked_asset_mapping_basis':'Frozen broad U.S. equity-risk proxy' if f=='MACRO_STATISTICAL_RELEASE' else '','linked_asset_mapping_source_url':'','adjudication_notes':''})
    with OUT.open('w',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader(); w.writerows(out)
    print(json.dumps({'status':'PASS','rows':len(out),'families':dict(Counter(x['resolved_family'] for x in out))},indent=2))
if __name__=='__main__': main()

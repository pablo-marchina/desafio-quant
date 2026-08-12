#!/usr/bin/env python3
"""Deterministic jurisdiction/right-censor/structural-proxy routing for PIT-v2.1.
No network, outcomes, prices, returns, F1-F9, IAS or performance inputs.
"""
from __future__ import annotations
import csv, json, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROTOCOL=Path('registry/w2c_pit_protocol_v2_1.json')
SRC=Path('registry/w2c_semantic_v2_accepted_clusters_v1_1.csv')
OUT=Path('registry/w2c_pit_v2_1_primary_source_queue.csv')
ASOF=datetime.fromisoformat('2026-08-12T20:00:00+00:00')

PROXY={'UNITED_STATES':'SPY','UNITED_KINGDOM':'EWU','EURO_AREA':'EZU','GERMANY':'EWG','BRAZIL':'EWZ','JAPAN':'EWJ','SOUTH_KOREA':'EWY','CHINA':'MCHI','MEXICO':'EWW','INDIA':'INDA','UNRESOLVED':''}

def dt(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
def ticker_hint(title,slug):
    m=re.search(r'\(([A-Z][A-Z0-9.\-]{0,7})\)',title or '')
    if m: return m.group(1)
    x=(slug or '').split('-')[0].upper()
    return x if re.fullmatch(r'[A-Z][A-Z0-9.]{0,7}',x or '') else ''
def macro_jurisdiction(title,slug):
    s=(title+' '+slug).lower()
    rules=[
      ('BRAZIL',[r'\bbrazil\b',r'\bbrasil\b']),('UNITED_KINGDOM',[r'\bu\.k\.\b',r'\buk\b',r'united kingdom']),
      ('EURO_AREA',[r'eurozone',r'euro area']),('GERMANY',[r'\bgermany\b']),('JAPAN',[r'\bjapan\b']),
      ('SOUTH_KOREA',[r'south korea',r'korea gdp']),('CHINA',[r'\bchina\b']),('MEXICO',[r'\bmexico\b']),
      ('INDIA',[r'\bindia\b',r'\bindian\b']),
      ('UNITED_STATES',[r'\bu\.s\.\b',r'\bus\b',r'united states',r'jobs added',r'jobs report',r'\bunemployment rate\b',r'\bcpi\b',r'\bppi\b',r'\binflation\b'])]
    hits=[j for j,pats in rules if any(re.search(p,s,re.I) for p in pats)]
    non_us=list(dict.fromkeys(x for x in hits if x!='UNITED_STATES'))
    if len(non_us)==1: return non_us[0]
    if len(non_us)>1: return 'UNRESOLVED'
    return 'UNITED_STATES' if 'UNITED_STATES' in hits else 'UNRESOLVED'
def source_route(j,title):
    s=title.lower()
    if j=='UNITED_STATES':
        if any(x in s for x in ['gdp','pce','personal income','personal consumption']): return 'BEA'
        if any(x in s for x in ['cpi','ppi','unemployment','payroll','jobs','employment']): return 'BLS'
        return 'UNRESOLVED_US_AGENCY'
    return {'UNITED_KINGDOM':'ONS','EURO_AREA':'EUROSTAT','GERMANY':'DESTATIS','BRAZIL':'IBGE','JAPAN':'JAPAN_OFFICIAL_SERIES_ROUTER','SOUTH_KOREA':'KOREA_OFFICIAL_SERIES_ROUTER','CHINA':'NBS_CHINA','MEXICO':'INEGI','INDIA':'MOSPI_EXACT_SERIES_ONLY','UNRESOLVED':'UNRESOLVED'}[j]
def main():
    p=json.loads(PROTOCOL.read_text()); allowed=set(p['population']['counts'])
    rows=[r for r in csv.DictReader(SRC.open(encoding='utf-8',newline='')) if r['resolved_family'] in allowed]
    assert len(rows)==260 and len({r['event_id'] for r in rows})==260
    out=[]
    for r in rows:
        fam=r['resolved_family']; due=dt(r['end_utc'])<=ASOF
        j=macro_jurisdiction(r['title'],r['slug']) if fam=='MACRO_STATISTICAL_RELEASE' else ('UNITED_STATES' if fam=='EARNINGS_EPS' else 'FDA_US_REGULATORY_PROCESS')
        th=ticker_hint(r['title'],r['slug']) if fam=='EARNINGS_EPS' else ''
        if fam=='MACRO_STATISTICAL_RELEASE': asset=PROXY[j]; asset_state='PASS' if asset else 'UNRESOLVED'; route=source_route(j,r['title'])
        elif fam=='EARNINGS_EPS': asset=th; asset_state='PASS' if th else 'UNRESOLVED'; route='ISSUER_IR_AND_SEC_EDGAR'
        else: asset=''; asset_state='PENDING_PRIMARY_SPONSOR_MAPPING'; route='FDA_AND_ISSUER_PRIMARY'
        out.append({
          'event_id':r['event_id'],'resolved_family':fam,'independence_cluster_id':r['independence_cluster_id'],'title':r['title'],'slug':r['slug'],'semantic_end_utc':r['end_utc'],
          'asof_state':'DUE_ASOF' if due else 'RIGHT_CENSORED_ASOF','jurisdiction':j,'primary_source_route':route,
          'linked_asset':asset,'linked_asset_mapping_state':asset_state,'linked_asset_mapping_basis':'FROZEN_V2_1_STRUCTURAL_ROUTE' if asset else '',
          'revelation_state':'PENDING_PRIMARY_REVIEW' if due else 'RIGHT_CENSORED_ASOF','revelation_precision':'','public_revelation_utc':'','safe_cutoff_utc':'',
          'revelation_source_type':'','revelation_source_url':'','revelation_response_sha256':'',
          'resolution_state':'PENDING_PRIMARY_REVIEW' if due else 'RIGHT_CENSORED_ASOF','resolution_source_type':'','resolution_source_url':'','resolution_response_sha256':'','resolution_ambiguous':'false',
          'asset_data_state':'PENDING_AVAILABILITY_PROBE' if due else 'RIGHT_CENSORED_ASOF','asset_data_first_date':'','asset_data_last_date':'','asset_data_rows':'','asset_data_response_sha256':'',
          'mandatory_account_gated_dependency':'false','mandatory_field_state':'PASS','adjudication_notes':''})
    fields=list(out[0])
    with OUT.open('w',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader(); w.writerows(out)
    c=Counter(x['resolved_family'] for x in out); rc=Counter(x['resolved_family'] for x in out if x['asof_state']=='RIGHT_CENSORED_ASOF'); macro=Counter(x['jurisdiction'] for x in out if x['resolved_family']=='MACRO_STATISTICAL_RELEASE')
    summary={'artifact':'W2C_PIT_V2_1_ROUTE_SUMMARY','status':'PASS','total':len(out),'family_counts':dict(c),'right_censored':dict(rc),'macro_jurisdictions':dict(macro),'performance_blind':True,'network_called':False,'returns_read':False}
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()

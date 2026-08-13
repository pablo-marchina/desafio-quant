#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,json
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from w4b_official_macro_parse_common_v1 import fetch,html_lines,nearby_date,occurrence
ROOT=Path(__file__).resolve().parents[1]; REG=ROOT/'registry'
rows=[]; manifest=[]
census={2023:'https://www.census.gov/economic-indicators/calendar-listview-2023.html',2024:'https://www.census.gov/economic-indicators/calendar-listview-2024.html',2025:'https://www.census.gov/economic-indicators/calendar-listview-2025.html',2026:'https://www.census.gov/economic-indicators/calendar-listview.html'}
for year,url in census.items():
    meta,body=fetch(f'CENSUS_{year}',url); manifest.append(meta)
    if meta['http_status']!=200: continue
    lines=html_lines(body)
    for i,text in enumerate(lines):
        if text.lower().startswith('advance monthly sales for retail and food services'):
            r=occurrence('RETAIL_SALES_RELEASE','US_RETAIL_SALES',nearby_date(lines,i,year),'CENSUS',meta,'Census official calendar: Advance Monthly Sales for Retail and Food Services')
            if r: rows.append(r)
def load_page(page): return page,fetch(f'DOL_ETA_{page}',f'https://www.dol.gov/newsroom/releases/eta?page={page}')
got={}
with ThreadPoolExecutor(max_workers=4) as ex:
    fut=[ex.submit(load_page,p) for p in range(36)]
    for f in as_completed(fut): p,x=f.result();got[p]=x
for page in range(36):
    meta,body=got[page]; manifest.append(meta)
    if meta['http_status']!=200: continue
    lines=html_lines(body)
    for i,text in enumerate(lines):
        if 'Unemployment Insurance Weekly Claims Report' in text:
            r=occurrence('UNEMPLOYMENT_RELEASE','US_INITIAL_JOBLESS_CLAIMS',nearby_date(lines,i,None),'DOL_ETA',meta,'DOL ETA official newsroom listing: Unemployment Insurance Weekly Claims Report')
            if r: rows.append(r)
ded={(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date']):r for r in rows}; rows=sorted(ded.values(),key=lambda r:(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date']))
fields=['resolved_family','normalized_subject_key','official_event_reference_date','source_authority','source_url','retrieved_at_utc','source_body_sha256','structured_release_date_reference']
with gzip.open(REG/'w4b_official_macro_occurrences_census_dol_v1.csv.gz','wt',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
mf=['label','url','http_status','content_type','response_bytes','sha256','retrieved_at_utc','error']
with gzip.open(REG/'w4b_official_macro_source_manifest_census_dol_v1.csv.gz','wt',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=mf);w.writeheader();w.writerows(manifest)
counts={}
for r in rows:k=r['resolved_family']+'|'+r['normalized_subject_key'];counts[k]=counts.get(k,0)+1
mins={'RETAIL_SALES_RELEASE|US_RETAIL_SALES':30,'UNEMPLOYMENT_RELEASE|US_INITIAL_JOBLESS_CLAIMS':180}; low={k:[counts.get(k,0),v] for k,v in mins.items() if counts.get(k,0)<v}
out={'artifact':'W4B_OFFICIAL_MACRO_CENSUS_DOL_OCCURRENCES','version':'v1.0','counts':counts,'source_failures':[m['label'] for m in manifest if m['http_status']!=200],'coverage_failures':low,'release_values_read_or_persisted':False,'gate_decision':'PASS' if not low else 'FAIL'}
(REG/'w4b_official_macro_occurrences_census_dol_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True))
if low: raise SystemExit(2)

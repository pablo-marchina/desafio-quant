#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,json,re
from pathlib import Path
from w4b_official_macro_parse_common_v1 import fetch,html_lines,nearby_date,occurrence
ROOT=Path(__file__).resolve().parents[1]; REG=ROOT/'registry'
rows=[]; manifest=[]
for year in range(2021,2027):
    meta,body=fetch(f'BLS_{year}',f'https://www.bls.gov/schedule/{year}/home.htm'); manifest.append(meta)
    if meta['http_status']!=200: continue
    lines=html_lines(body)
    for i,text in enumerate(lines):
        if re.search(r'^Consumer Price Index for\b',text,re.I):
            r=occurrence('CPI_INFLATION_RELEASE','US_CPI',nearby_date(lines,i,year),'BLS',meta,'BLS annual schedule: '+text)
            if r: rows.append(r)
        if re.search(r'^Employment Situation for\b',text,re.I):
            d=nearby_date(lines,i,year)
            for fam,sub in [('PAYROLLS_JOBS_RELEASE','US_PAYROLLS'),('UNEMPLOYMENT_RELEASE','US_UNEMPLOYMENT_RATE')]:
                r=occurrence(fam,sub,d,'BLS',meta,'BLS annual schedule: '+text)
                if r: rows.append(r)
ded={(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date']):r for r in rows}; rows=sorted(ded.values(),key=lambda r:(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date']))
fields=['resolved_family','normalized_subject_key','official_event_reference_date','source_authority','source_url','retrieved_at_utc','source_body_sha256','structured_release_date_reference']
with gzip.open(REG/'w4b_official_macro_occurrences_bls_v1.csv.gz','wt',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
mf=['label','url','http_status','content_type','response_bytes','sha256','retrieved_at_utc','error']
with gzip.open(REG/'w4b_official_macro_source_manifest_bls_v1.csv.gz','wt',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=mf);w.writeheader();w.writerows(manifest)
counts={}
for r in rows:k=r['resolved_family']+'|'+r['normalized_subject_key'];counts[k]=counts.get(k,0)+1
mins={'CPI_INFLATION_RELEASE|US_CPI':60,'PAYROLLS_JOBS_RELEASE|US_PAYROLLS':60,'UNEMPLOYMENT_RELEASE|US_UNEMPLOYMENT_RATE':60}; low={k:[counts.get(k,0),v] for k,v in mins.items() if counts.get(k,0)<v}
out={'artifact':'W4B_OFFICIAL_MACRO_BLS_OCCURRENCES','version':'v1.0','counts':counts,'source_failures':[m['label'] for m in manifest if m['http_status']!=200],'coverage_failures':low,'release_values_read_or_persisted':False,'gate_decision':'PASS' if not low else 'FAIL'}
(REG/'w4b_official_macro_occurrences_bls_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True))
if low: raise SystemExit(2)

#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,html,json,re
from pathlib import Path
from w4b_official_macro_parse_common_v1 import fetch,full_date,occurrence
ROOT=Path(__file__).resolve().parents[1]; REG=ROOT/'registry'
rows=[]; manifest=[]
def table_rows(body):
    raw=body.decode('utf-8','ignore')
    out=[]
    for block in re.findall(r'<tr\b[^>]*>(.*?)</tr>',raw,re.I|re.S):
        text=re.sub(r'<[^>]+>',' ',block); text=html.unescape(text); text=' '.join(text.split())
        if text: out.append(text)
    return out
for year in range(2021,2027):
    meta,body=fetch(f'BLS_{year}',f'https://www.bls.gov/schedule/{year}/home.htm'); manifest.append(meta)
    if meta['http_status']!=200: continue
    for text in table_rows(body):
        d=full_date(text)
        if not d: continue
        if re.search(r'\bConsumer Price Index for\b',text,re.I):
            r=occurrence('CPI_INFLATION_RELEASE','US_CPI',d,'BLS',meta,'BLS annual schedule table row: '+text)
            if r: rows.append(r)
        if re.search(r'\bEmployment Situation for\b',text,re.I):
            for fam,sub in [('PAYROLLS_JOBS_RELEASE','US_PAYROLLS'),('UNEMPLOYMENT_RELEASE','US_UNEMPLOYMENT_RATE')]:
                r=occurrence(fam,sub,d,'BLS',meta,'BLS annual schedule table row: '+text)
                if r: rows.append(r)
ded={(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date']):r for r in rows}; rows=sorted(ded.values(),key=lambda r:(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date']))
fields=['resolved_family','normalized_subject_key','official_event_reference_date','source_authority','source_url','retrieved_at_utc','source_body_sha256','structured_release_date_reference']
with gzip.open(REG/'w4b_official_macro_occurrences_bls_v1.csv.gz','wt',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
mf=['label','url','http_status','content_type','response_bytes','sha256','retrieved_at_utc','error']
with gzip.open(REG/'w4b_official_macro_source_manifest_bls_v1.csv.gz','wt',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=mf);w.writeheader();w.writerows(manifest)
counts={}
for r in rows:k=r['resolved_family']+'|'+r['normalized_subject_key'];counts[k]=counts.get(k,0)+1
mins={'CPI_INFLATION_RELEASE|US_CPI':60,'PAYROLLS_JOBS_RELEASE|US_PAYROLLS':60,'UNEMPLOYMENT_RELEASE|US_UNEMPLOYMENT_RATE':60}; low={k:[counts.get(k,0),v] for k,v in mins.items() if counts.get(k,0)<v}
out={'artifact':'W4B_OFFICIAL_MACRO_BLS_OCCURRENCES','version':'v1.0.2','parser_mode':'BLS_TABLE_ROW_DATE_AND_RELEASE_SAME_ROW','counts':counts,'source_failures':[m['label'] for m in manifest if m['http_status']!=200],'coverage_failures':low,'release_values_read_or_persisted':False,'gate_decision':'PASS' if not low else 'FAIL'}
(REG/'w4b_official_macro_occurrences_bls_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True))
if low: raise SystemExit(2)

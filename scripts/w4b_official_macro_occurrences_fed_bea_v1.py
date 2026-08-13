#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,html,json,re
from datetime import datetime
from pathlib import Path
from w4b_official_macro_parse_common_v1 import fetch,full_date,month_day,occurrence
ROOT=Path(__file__).resolve().parents[1]; REG=ROOT/'registry'
rows=[]; manifest=[]
def trs(body):
    raw=body.decode('utf-8','ignore'); out=[]
    for block in re.findall(r'<tr\b[^>]*>(.*?)</tr>',raw,re.I|re.S):
        text=' '.join(html.unescape(re.sub(r'<[^>]+>',' ',block)).split())
        if text:out.append(text)
    return out
meta,body=fetch('FED_FOMC','https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'); manifest.append(meta)
if meta['http_status']==200:
    raw=body.decode('utf-8','ignore')
    for m in re.finditer(r'href=["\']([^"\']*monetary(20\d{6})a\.htm)["\']',raw,re.I):
        rows.append(occurrence('FOMC_DECISION','US_FOMC',datetime.strptime(m.group(2),'%Y%m%d').date(),'FEDERAL_RESERVE',meta,'FOMC calendar statement href='+m.group(1)))
bea={2021:'https://apps.bea.gov/scb/issues/2020/12-december/1220-news-releases-2021.htm',2022:'https://apps.bea.gov/scb/issues/2021/12-december/1221-news-releases-2022.htm',2023:'https://apps.bea.gov/scb/issues/2022/12-december/1222-news-releases-2023.htm',2024:'https://apps.bea.gov/scb/issues/2023/12-december/1223-news-releases-2024.htm',2025:'https://www.bea.gov/news/schedule/full-2025',2026:'https://www.bea.gov/news/schedule/full'}
for year,url in bea.items():
    meta,body=fetch(f'BEA_{year}',url); manifest.append(meta)
    if meta['http_status']!=200:continue
    for text in trs(body):
        d=full_date(text) or month_day(text,year)
        if not d:continue
        low=text.lower(); national=('gross domestic product' in low and 'gross domestic product by ' not in low and 'gross domestic product for ' not in low and 'gross domestic product by state' not in low and 'gross domestic product by county' not in low) or bool(re.search(r'\bgdp \(',low))
        if national:
            r=occurrence('GDP_RELEASE','US_GDP',d,'BEA',meta,'BEA official schedule table row: '+text)
            if r:rows.append(r)
        if 'personal income and outlays' in low:
            r=occurrence('PCE_RELEASE','US_PCE',d,'BEA',meta,'BEA official schedule table row: '+text)
            if r:rows.append(r)
ded={(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date']):r for r in rows if r}; rows=sorted(ded.values(),key=lambda r:(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date']))
fields=['resolved_family','normalized_subject_key','official_event_reference_date','source_authority','source_url','retrieved_at_utc','source_body_sha256','structured_release_date_reference']
with gzip.open(REG/'w4b_official_macro_occurrences_fed_bea_v1.csv.gz','wt',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
mf=['label','url','http_status','content_type','response_bytes','sha256','retrieved_at_utc','error']
with gzip.open(REG/'w4b_official_macro_source_manifest_fed_bea_v1.csv.gz','wt',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=mf);w.writeheader();w.writerows(manifest)
counts={}
for r in rows:k=r['resolved_family']+'|'+r['normalized_subject_key'];counts[k]=counts.get(k,0)+1
mins={'FOMC_DECISION|US_FOMC':35,'GDP_RELEASE|US_GDP':55,'PCE_RELEASE|US_PCE':55}; low={k:[counts.get(k,0),v] for k,v in mins.items() if counts.get(k,0)<v}
out={'artifact':'W4B_OFFICIAL_MACRO_FED_BEA_OCCURRENCES','version':'v1.0.1','bea_parser_mode':'BEA_TABLE_ROW_RELEASE_AND_DATE_SAME_ROW','counts':counts,'source_failures':[m['label'] for m in manifest if m['http_status']!=200],'coverage_failures':low,'release_values_read_or_persisted':False,'gate_decision':'PASS' if not low else 'FAIL'}
(REG/'w4b_official_macro_occurrences_fed_bea_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out,indent=2,sort_keys=True))
if low:raise SystemExit(2)

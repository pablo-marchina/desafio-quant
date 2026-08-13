#!/usr/bin/env python3
import csv,gzip,json
from collections import Counter
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'registry'
occ=['w4b_official_macro_occurrences_bls_v1.csv.gz','w4b_official_macro_occurrences_fed_bea_v1.csv.gz','w4b_official_macro_occurrences_census_dol_v1.csv.gz']
man=['w4b_official_macro_source_manifest_bls_v1.csv.gz','w4b_official_macro_source_manifest_fed_bea_v1.csv.gz','w4b_official_macro_source_manifest_census_dol_v1.csv.gz']
rows=[]
for n in occ:
    with gzip.open(R/n,'rt',encoding='utf-8',newline='') as f: rows += list(csv.DictReader(f))
d={}
for r in rows:
    k=(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date'])
    if k not in d or r['source_url']<d[k]['source_url']: d[k]=r
rows=sorted(d.values(),key=lambda r:(r['resolved_family'],r['normalized_subject_key'],r['official_event_reference_date']))
flds=['resolved_family','normalized_subject_key','official_event_reference_date','source_authority','source_url','retrieved_at_utc','source_body_sha256','structured_release_date_reference']
with gzip.open(R/'w4b_official_macro_occurrences_v1.csv.gz','wt',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=flds); w.writeheader(); w.writerows(rows)
manifest=[]
for n in man:
    with gzip.open(R/n,'rt',encoding='utf-8',newline='') as f: manifest += list(csv.DictReader(f))
mf=['label','url','http_status','content_type','response_bytes','sha256','retrieved_at_utc','error']
with gzip.open(R/'w4b_official_macro_source_manifest_v1.csv.gz','wt',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=mf); w.writeheader(); w.writerows(manifest)
c=Counter(r['resolved_family']+'|'+r['normalized_subject_key'] for r in rows); rng={}
for r in rows:
    k=r['resolved_family']+'|'+r['normalized_subject_key']; x=r['official_event_reference_date']; rng.setdefault(k,[x,x]); rng[k]=[min(rng[k][0],x),max(rng[k][1],x)]
mins={'CPI_INFLATION_RELEASE|US_CPI':60,'PAYROLLS_JOBS_RELEASE|US_PAYROLLS':60,'UNEMPLOYMENT_RELEASE|US_UNEMPLOYMENT_RATE':60,'UNEMPLOYMENT_RELEASE|US_INITIAL_JOBLESS_CLAIMS':180,'GDP_RELEASE|US_GDP':55,'PCE_RELEASE|US_PCE':55,'RETAIL_SALES_RELEASE|US_RETAIL_SALES':30,'FOMC_DECISION|US_FOMC':35}
low={k:{'observed':c.get(k,0),'minimum':v} for k,v in mins.items() if c.get(k,0)<v}
out={'artifact':'W4B_OFFICIAL_MACRO_OCCURRENCE_SUMMARY','version':'W4B-OET-MACRO-OCC-RESULT-v1.0','date':'2026-08-13','occurrence_rows':len(rows),'occurrence_counts':dict(sorted(c.items())),'occurrence_ranges':{k:{'min':v[0],'max':v[1]} for k,v in sorted(rng.items())},'source_manifest_rows':len(manifest),'source_failures':[m['label'] for m in manifest if str(m['http_status'])!='200'],'parser_coverage_failures':low,'release_values_read_or_persisted':False,'prediction_market_outcomes_read':False,'linked_asset_realized_returns_read':False,'performance_blind':True,'gate_decision':'PASS_OFFICIAL_MACRO_OCCURRENCES_MATERIALIZED' if not low else 'FAIL_OFFICIAL_MACRO_OCCURRENCE_COVERAGE'}
(R/'w4b_official_macro_occurrence_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps(out,indent=2,sort_keys=True))
if low: raise SystemExit(2)

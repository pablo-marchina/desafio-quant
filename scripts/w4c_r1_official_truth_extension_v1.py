#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import subprocess
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'registry'
PROTO_PATH = REG / 'w4c_r1_official_truth_extension_protocol_v1.json'
FREEZE_PATH = REG / 'w4c_r1_official_truth_extension_freeze_v1.json'
PROFILE_PATH = REG / 'w4c_r1_official_truth_unresolved_profile_v1.json'
UNRES_PATH = REG / 'w4b_official_event_truth_unresolved_v1.csv.gz'
MACRO_INPUT = REG / '_r1_input_w4b_official_macro_occurrences_v1.csv.gz'
SEC_UA = 'ARGOS-W4C-R1/1.0 contact=research@users.noreply.github.com'
SEC_TICKERS = 'https://www.sec.gov/files/company_tickers.json'
SEC_SUBMISSIONS = 'https://data.sec.gov/submissions/CIK{cik10}.json'

MACRO_WINDOWS = {
    ('CPI_INFLATION_RELEASE', 'US_CPI'): 14,
    ('PAYROLLS_JOBS_RELEASE', 'US_PAYROLLS'): 14,
    ('UNEMPLOYMENT_RELEASE', 'US_UNEMPLOYMENT_RATE'): 14,
    ('UNEMPLOYMENT_RELEASE', 'US_INITIAL_JOBLESS_CLAIMS'): 3,
    ('GDP_RELEASE', 'US_GDP'): 21,
    ('PCE_RELEASE', 'US_PCE'): 14,
    ('RETAIL_SALES_RELEASE', 'US_RETAIL_SALES'): 14,
    ('FOMC_DECISION', 'US_FOMC'): 21,
}
NONMACRO_FAMILIES = {
    'EARNINGS_EPS', 'CORPORATE_LITIGATION_BINARY', 'FDA_FINAL_PDUFA_DECISION',
    'MA_PRE_ANNOUNCEMENT_OR_RUMOR', 'MA_PENDING_COMPLETION', 'MA_REGULATORY_CLEARANCE',
    'ANTITRUST_ENFORCEMENT_SINGLE_NAME',
}
STOPWORDS = {
    'will','the','a','an','of','for','in','on','by','to','and','or','beat','miss','eps','earnings','quarterly','quarter',
    'q1','q2','q3','q4','2021','2022','2023','2024','2025','2026','2027','report','reports','revenue','per','share',
    'above','below','than','more','less','over','under','between','before','after','this','next','its','fiscal','fy',
    'inc','corp','corporation','company','co','ltd','limited','plc','holdings','group','class','common','stock'
}


def git_blob(path: Path) -> str:
    return subprocess.check_output(['git','hash-object',str(path)], text=True).strip()


def read_gz(path: Path) -> list[dict]:
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def write_gz(path: Path, rows: list[dict], fields: list[str]):
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{k:r.get(k,'') for k in fields} for r in rows])


def parse_date(s: str) -> date | None:
    try: return datetime.strptime((s or '').strip(), '%Y-%m-%d').date()
    except Exception: return None


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def official_id(fam: str, dt: str, subject: str) -> str:
    return 'W4OT1-' + hashlib.sha256(f'{fam}|{dt}|{subject}'.encode()).hexdigest()[:20]


def norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()


def tokens(s: str) -> list[str]:
    return [x for x in norm(s).split() if len(x) >= 2 and x not in STOPWORDS]


def http_get(url: str, accept='application/json', retries=5) -> tuple[bytes, int, str]:
    last = ''
    for i in range(retries):
        try:
            req = Request(url, headers={'User-Agent': SEC_UA, 'Accept': accept, 'Accept-Encoding':'identity'})
            with urlopen(req, timeout=45) as r:
                return r.read(), getattr(r,'status',200), r.headers.get('Content-Type','')
        except HTTPError as e:
            last = f'HTTP {e.code}'
            if 400 <= e.code < 500 and e.code != 429:
                return b'', e.code, ''
        except (URLError, TimeoutError, OSError) as e:
            last = str(e)
        if i + 1 < retries: time.sleep(min(10, 1.0 * (2 ** i)))
    raise RuntimeError(f'HTTP_UNRESOLVED:{url}:{last}')


def validate_freeze() -> tuple[dict,dict,dict,list[dict]]:
    proto = json.loads(PROTO_PATH.read_text())
    freeze = json.loads(FREEZE_PATH.read_text())
    profile = json.loads(PROFILE_PATH.read_text())
    assert proto['version'] == 'W4C-R1-OTE-v1.0'
    assert freeze['status'] == 'FROZEN_BEFORE_ANY_R1_OFFICIAL_SOURCE_LOOKUP_OR_RECLASSIFICATION'
    assert profile['technical_gate_decision'] == 'PASS_W4C_R1_DESCRIPTIVE_PROFILE_FROZEN'
    assert git_blob(PROTO_PATH) == freeze['frozen_protocol']['git_blob_sha'] == 'add5c0251d13ee001227de13860d37851faa7919'
    assert git_blob(PROFILE_PATH) == freeze['frozen_eligibility']['profile_git_blob_sha'] == '12c19e9596429884e20e5ef7ceacde399dc2760b'
    assert git_blob(UNRES_PATH) == freeze['frozen_eligibility']['unresolved_source_git_blob_sha'] == 'ba1a8ca49ce7befdbffec9715fda34dcbfb295cd'
    rows = read_gz(UNRES_PATH)
    eligible = [r for r in rows if (r.get('verification_state') or '').strip() == 'UNRESOLVED_OFFICIAL_TRUTH']
    ids = sorted((r.get('exact_group_id') or '').strip() for r in eligible)
    assert len(eligible) == len(set(ids)) == freeze['frozen_eligibility']['eligible_exact_groups'] == 1743
    digest = hashlib.sha256(('\n'.join(ids)+'\n').encode()).hexdigest()
    assert digest == freeze['frozen_eligibility']['sorted_group_ids_sha256'] == '4e008fddf2d24373272213810a595fcc4949731da592c28057c77e19ed0d2dfe'
    assert not any(not x for x in ids)
    assert freeze['pre_freeze_observation_declarations']['linked_asset_realized_returns_read'] is False
    assert freeze['pre_freeze_observation_declarations']['prediction_market_performance_read'] is False
    print(json.dumps({'gate':'PASS_R1_PRE_REQUEST_BYTE_FREEZE','eligible':len(eligible),'digest':digest}, sort_keys=True), flush=True)
    return proto, freeze, profile, eligible


def load_context() -> dict[str,str]:
    out = defaultdict(list)
    pm = REG / 'w4b_polymarket_recensus_events_v1.csv.gz'
    if pm.exists():
        for r in read_gz(pm):
            cid=(r.get('canonical_event_id') or '').strip()
            if cid:
                out[cid].extend([(r.get('normalized_subject_key') or ''), (r.get('slugs') or '')])
    kal = REG / 'w4b_kalshi_semantic_events_v1_1.csv.gz'
    if kal.exists():
        for r in read_gz(kal):
            cid=(r.get('canonical_event_id') or '').strip()
            if cid:
                out[cid].extend([(r.get('normalized_subject_key') or ''), (r.get('series_title') or ''), (r.get('event_ticker') or '')])
    fx_contracts = REG / 'w4b_forecastex_contracts_v1.csv.gz'
    if fx_contracts.exists():
        for r in read_gz(fx_contracts):
            cid=(r.get('canonical_event_id') or '').strip()
            if cid:
                out[cid].extend([(r.get('normalized_subject_key') or ''), (r.get('product_name') or ''), (r.get('event_contract') or '')])
    return {k:' | '.join(dict.fromkeys(x for x in v if x)) for k,v in out.items()}


def macro_decisions(eligible: list[dict]) -> dict[str,dict]:
    if not MACRO_INPUT.exists():
        raise SystemExit('R1_MACRO_EVIDENCE_BUNDLE_MISSING')
    occ = read_gz(MACRO_INPUT)
    by_key = defaultdict(list)
    for r in occ:
        by_key[((r.get('resolved_family') or '').strip(), (r.get('normalized_subject_key') or '').strip())].append(r)
    out={}
    for r in eligible:
        gid=r['exact_group_id']; fam=r['resolved_family']; subj=r['pretruth_subject_key']; pre=parse_date(r['pretruth_event_reference_date'])
        key=(fam,subj)
        if key not in MACRO_WINDOWS: continue
        window=MACRO_WINDOWS[key]
        candidates=[]
        if pre:
            for o in by_key.get(key,[]):
                od=parse_date(o.get('official_event_reference_date',''))
                if od and abs((od-pre).days) <= window:
                    candidates.append(o)
        if len(candidates)==1:
            o=candidates[0]; od=o['official_event_reference_date']; auth=o['source_authority']; osub=o['normalized_subject_key']
            out[gid]={
              'r1_verification_state':'VERIFIED_R1_OFFICIAL_TRUTH','official_event_reference_date':od,
              'official_event_timestamp_utc_if_published':'','official_subject_key':osub,
              'source_authority':auth,'source_url':o['source_url'],'retrieved_at_utc':o['retrieved_at_utc'],
              'source_body_sha256_or_document_hash':o.get('source_body_sha256',''),
              'evidence_excerpt_hash_or_structured_field_reference':o.get('structured_release_date_reference','') or 'W4B_OFFICIAL_MACRO_OCCURRENCE_REGISTRY',
              'verification_reason':f'unique frozen official macro occurrence within +/-{window} calendar days',
              'review_mode':'R1_REUSE_FROZEN_W4B_PRIMARY_SOURCE_OCCURRENCE','match_rule_used':f'R1_MACRO_UNIQUE_WINDOW_{window}D'
            }
        else:
            out[gid]={
              'r1_verification_state':'UNRESOLVED_R1_OFFICIAL_TRUTH','verification_reason':f'R1 macro unique-match requirement failed: candidates={len(candidates)} within +/-{window}d',
              'review_mode':'R1_REUSE_FROZEN_W4B_PRIMARY_SOURCE_OCCURRENCE','match_rule_used':f'R1_MACRO_UNIQUE_WINDOW_{window}D'
            }
    return out


def sec_company_index(manifest: list[dict]) -> tuple[list[dict],str]:
    body,status,ct=http_get(SEC_TICKERS)
    if status != 200: raise SystemExit(f'SEC_TICKER_MAP_HTTP_{status}')
    retrieved=datetime.now(timezone.utc).isoformat(); h=sha256_bytes(body)
    manifest.append({'source_authority':'SEC_EDGAR','source_url':SEC_TICKERS,'retrieved_at_utc':retrieved,'http_status':status,'content_type':ct,'response_bytes':len(body),'source_body_sha256_or_document_hash':h,'purpose':'SEC_COMPANY_IDENTITY_MAP'})
    obj=json.loads(body.decode())
    companies=[]
    for _,x in obj.items():
        cik=str(x.get('cik_str') or '').zfill(10); ticker=str(x.get('ticker') or '').upper().strip(); title=str(x.get('title') or '').strip()
        if not cik or not ticker or not title: continue
        nt=norm(title)
        stripped=' '.join(t for t in nt.split() if t not in {'inc','corp','corporation','company','co','ltd','limited','plc','holdings','group','nv','sa','ag'})
        companies.append({'cik10':cik,'ticker':ticker,'title':title,'norm_title':nt,'core_title':stripped})
    return companies,h


def resolve_issuer(text: str, companies: list[dict]) -> tuple[dict|None,str]:
    upper_tokens=set(re.findall(r'(?<![A-Za-z0-9])([A-Z]{1,5})(?![A-Za-z0-9])', text or ''))
    ticker_hits=[c for c in companies if c['ticker'] in upper_tokens]
    if len(ticker_hits)==1: return ticker_hits[0], 'EXACT_TICKER_TOKEN'
    nt=' '+norm(text)+' '
    name_hits=[]
    for c in companies:
        core=c['core_title']
        if len(core) >= 4 and (' '+core+' ') in nt:
            name_hits.append(c)
    if name_hits:
        maxlen=max(len(x['core_title']) for x in name_hits)
        top=[x for x in name_hits if len(x['core_title'])==maxlen]
        if len(top)==1: return top[0], 'LONGEST_EXACT_SEC_COMPANY_NAME_PHRASE'
    return None, 'UNRESOLVED_ISSUER_IDENTITY'


def parse_period(text: str) -> tuple[int|None,int|None]:
    t=(text or '').upper()
    pats=[r'Q([1-4])[^0-9]{0,8}(20\d{2})', r'(20\d{2})[^A-Z0-9]{0,8}Q([1-4])']
    m=re.search(pats[0],t)
    if m: return int(m.group(2)),int(m.group(1))
    m=re.search(pats[1],t)
    if m: return int(m.group(1)),int(m.group(2))
    return None,None


def quarter_of(dt: date) -> int:
    return (dt.month-1)//3+1


def sec_submissions(company: dict, cache: dict, manifest: list[dict]) -> tuple[dict,str,str]:
    cik=company['cik10']
    if cik in cache: return cache[cik]
    url=SEC_SUBMISSIONS.format(cik10=cik)
    body,status,ct=http_get(url)
    retrieved=datetime.now(timezone.utc).isoformat(); h=sha256_bytes(body)
    manifest.append({'source_authority':'SEC_EDGAR','source_url':url,'retrieved_at_utc':retrieved,'http_status':status,'content_type':ct,'response_bytes':len(body),'source_body_sha256_or_document_hash':h,'purpose':'SEC_SUBMISSIONS_METADATA'})
    if status != 200:
        cache[cik]=({},h,retrieved); return cache[cik]
    cache[cik]=(json.loads(body.decode()),h,retrieved); return cache[cik]


def filing_rows(obj: dict) -> list[dict]:
    recent=((obj.get('filings') or {}).get('recent') or {})
    keys=['accessionNumber','filingDate','reportDate','acceptanceDateTime','form','items','primaryDocument']
    n=max((len(recent.get(k) or []) for k in keys), default=0)
    rows=[]
    for i in range(n):
        rows.append({k:(recent.get(k) or ['']*n)[i] if i < len(recent.get(k) or []) else '' for k in keys})
    return rows


def sec_filing_url(cik10: str, acc: str, primary: str) -> str:
    cik=str(int(cik10)); acc_clean=(acc or '').replace('-','')
    if acc_clean and primary:
        return f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{primary}'
    return SEC_SUBMISSIONS.format(cik10=cik10)


def earnings_decisions(eligible: list[dict], contexts: dict[str,str]) -> tuple[dict[str,dict],list[dict]]:
    manifest=[]; companies,_=sec_company_index(manifest); cache={}; out={}
    for idx,r in enumerate([x for x in eligible if x['resolved_family']=='EARNINGS_EPS'],1):
        gid=r['exact_group_id']; pre=parse_date(r['pretruth_event_reference_date']); text=' | '.join([r.get('pretruth_subject_key',''), contexts.get(gid,'')])
        company,issuer_rule=resolve_issuer(text,companies)
        if company is None or pre is None:
            out[gid]={'r1_verification_state':'UNRESOLVED_R1_OFFICIAL_TRUTH','verification_reason':issuer_rule if company is None else 'INVALID_PRETRUTH_DATE','review_mode':'R1_SEC_IDENTITY_ONLY','match_rule_used':'R1_EARNINGS_SEC_ISSUER_PERIOD_DATE_V1'}
            continue
        obj,bodyhash,retrieved=sec_submissions(company,cache,manifest)
        rows=filing_rows(obj); year,q=parse_period(text)
        candidates=[]
        for f in rows:
            fd=parse_date(f.get('filingDate','')); rd=parse_date(f.get('reportDate',''))
            if not fd or abs((fd-pre).days)>14: continue
            form=(f.get('form') or '').upper(); items=f.get('items') or ''
            tier=None
            if form=='8-K' and '2.02' in items: tier=1
            elif form in {'6-K','10-Q','10-K','20-F','40-F'}: tier=2
            if tier is None: continue
            if year and q and rd:
                if rd.year!=year or quarter_of(rd)!=q: continue
            candidates.append((tier,abs((fd-pre).days),fd,f))
        if candidates:
            best_tier=min(x[0] for x in candidates); candidates=[x for x in candidates if x[0]==best_tier]
            best_dist=min(x[1] for x in candidates); candidates=[x for x in candidates if x[1]==best_dist]
        if len(candidates)!=1:
            out[gid]={'r1_verification_state':'UNRESOLVED_R1_OFFICIAL_TRUTH','verification_reason':f'SEC identity resolved ({company["ticker"]}/{company["cik10"]}) but unique earnings filing match failed: candidates={len(candidates)}','review_mode':'R1_SEC_IDENTITY_ONLY','match_rule_used':'R1_EARNINGS_SEC_ISSUER_PERIOD_DATE_V1'}
            continue
        _,dist,fd,f=candidates[0]
        subject=f'SEC_CIK_{int(company["cik10"])}'
        url=sec_filing_url(company['cik10'],f.get('accessionNumber',''),f.get('primaryDocument',''))
        evref=f"SEC_SUBMISSIONS:{f.get('accessionNumber','')}|FORM={f.get('form','')}|ITEMS={f.get('items','')}|REPORT_DATE={f.get('reportDate','')}|ISSUER_RULE={issuer_rule}"
        out[gid]={
          'r1_verification_state':'VERIFIED_R1_OFFICIAL_TRUTH','official_event_reference_date':fd.isoformat(),
          'official_event_timestamp_utc_if_published':f.get('acceptanceDateTime',''),'official_subject_key':subject,
          'source_authority':'SEC_EDGAR','source_url':url,'retrieved_at_utc':retrieved,
          'source_body_sha256_or_document_hash':bodyhash,'evidence_excerpt_hash_or_structured_field_reference':evref,
          'verification_reason':f'unique SEC earnings filing metadata match within +/-14d; issuer={company["ticker"]}; distance_days={dist}',
          'review_mode':'R1_SEC_IDENTITY_ONLY','match_rule_used':'R1_EARNINGS_SEC_ISSUER_PERIOD_DATE_V1'
        }
        if idx % 100 == 0: print(f'R1_SEC_EARNINGS_PROGRESS={idx}', flush=True)
    return out,manifest


def main():
    proto,freeze,profile,eligible=validate_freeze()
    # This print is the boundary: no external request has occurred before the byte/digest gate above.
    print('R1_EXTERNAL_REQUESTS_NOW_AUTHORIZED_BY_VALIDATED_FREEZE', flush=True)
    contexts=load_context()
    decisions=macro_decisions(eligible)
    sec_decisions,sec_manifest=earnings_decisions(eligible,contexts)
    decisions.update(sec_decisions)

    existing_groups=read_gz(REG/'w4b_official_event_truth_groups_v1.csv.gz')
    existing_oids={r['official_event_id'] for r in existing_groups if r.get('official_event_id')}
    records=[]; source_manifest={}
    for r in sorted(eligible,key=lambda x:x['exact_group_id']):
        gid=r['exact_group_id']; d=decisions.get(gid)
        if d is None:
            d={'r1_verification_state':'UNRESOLVED_R1_OFFICIAL_TRUTH','verification_reason':'No deterministic primary-source identity match implemented under frozen R1 v1 executor; retained fail-closed','review_mode':'R1_FAIL_CLOSED_NON_EARNINGS_NONMACRO','match_rule_used':'R1_NONMACRO_PRIMARY_EVIDENCE_REQUIRED'}
        state=d['r1_verification_state']; fam=r['resolved_family']; oid=''; alias=False
        if state=='VERIFIED_R1_OFFICIAL_TRUTH':
            od=d['official_event_reference_date']; osub=d['official_subject_key']; oid=official_id(fam,od,osub); alias=oid in existing_oids
            parsed=urlparse(d.get('source_url',''))
            assert parsed.scheme=='https' and parsed.netloc
            assert d.get('source_authority') and d.get('retrieved_at_utc') and d.get('evidence_excerpt_hash_or_structured_field_reference')
            sk=(d['source_authority'],d['source_url'],d.get('source_body_sha256_or_document_hash',''))
            source_manifest[sk]={
              'source_authority':d['source_authority'],'source_url':d['source_url'],'retrieved_at_utc':d['retrieved_at_utc'],
              'source_body_sha256_or_document_hash':d.get('source_body_sha256_or_document_hash',''),
              'evidence_excerpt_hash_or_structured_field_reference':d.get('evidence_excerpt_hash_or_structured_field_reference','')
            }
        pre=r['pretruth_event_reference_date']; od=d.get('official_event_reference_date','')
        pdate=parse_date(pre); odate=parse_date(od)
        records.append({
          'exact_group_id':gid,'resolved_family':fam,'pretruth_event_reference_date':pre,'pretruth_subject_key':r.get('pretruth_subject_key',''),
          'venues':r.get('venues',''),'r1_verification_state':state,'official_event_id':oid,'official_event_reference_date':od,
          'official_event_timestamp_utc_if_published':d.get('official_event_timestamp_utc_if_published',''),'official_subject_key':d.get('official_subject_key',''),
          'source_authority':d.get('source_authority',''),'source_url':d.get('source_url',''),'retrieved_at_utc':d.get('retrieved_at_utc',''),
          'source_body_sha256_or_document_hash':d.get('source_body_sha256_or_document_hash',''),
          'evidence_excerpt_hash_or_structured_field_reference':d.get('evidence_excerpt_hash_or_structured_field_reference',''),
          'verification_reason':d.get('verification_reason',''),'review_mode':d.get('review_mode',''),'match_rule_used':d.get('match_rule_used',''),
          'reference_date_delta_days':(odate-pdate).days if pdate and odate else '',
          'alias_to_existing_w4b_official_event':'YES' if alias else ('NO' if state=='VERIFIED_R1_OFFICIAL_TRUTH' else '')
        })

    assert len(records)==1743 and len({r['exact_group_id'] for r in records})==1743
    verified=[r for r in records if r['r1_verification_state']=='VERIFIED_R1_OFFICIAL_TRUTH']
    unresolved=[r for r in records if r['r1_verification_state']!='VERIFIED_R1_OFFICIAL_TRUTH']
    by_oid=defaultdict(list)
    for r in verified: by_oid[r['official_event_id']].append(r)
    groups=[]; contradictions=[]
    for oid,rs in sorted(by_oid.items()):
        sig={(x['resolved_family'],x['official_event_reference_date'],x['official_subject_key']) for x in rs}
        if len(sig)!=1: contradictions.append({'official_event_id':oid,'signatures':sorted('|'.join(x) for x in sig)}); continue
        fam,dt,sub=next(iter(sig)); groups.append({'official_event_id':oid,'resolved_family':fam,'official_event_reference_date':dt,'official_subject_key':sub,'exact_group_ids':'|'.join(sorted(x['exact_group_id'] for x in rs)),'exact_group_count':len(rs),'venues':'|'.join(sorted({v for x in rs for v in x['venues'].split('|') if v})),'alias_to_existing_w4b_official_event':'YES' if oid in existing_oids else 'NO'})
    new_groups=[g for g in groups if g['alias_to_existing_w4b_official_event']=='NO']
    alias_groups=[g for g in groups if g['alias_to_existing_w4b_official_event']=='YES']

    fields=['exact_group_id','resolved_family','pretruth_event_reference_date','pretruth_subject_key','venues','r1_verification_state','official_event_id','official_event_reference_date','official_event_timestamp_utc_if_published','official_subject_key','source_authority','source_url','retrieved_at_utc','source_body_sha256_or_document_hash','evidence_excerpt_hash_or_structured_field_reference','verification_reason','review_mode','match_rule_used','reference_date_delta_days','alias_to_existing_w4b_official_event']
    write_gz(REG/'w4c_r1_official_truth_extension_records_v1.csv.gz',records,fields)
    write_gz(REG/'w4c_r1_official_truth_extension_unresolved_v1.csv.gz',unresolved,fields)
    write_gz(REG/'w4c_r1_official_truth_extension_groups_v1.csv.gz',groups,['official_event_id','resolved_family','official_event_reference_date','official_subject_key','exact_group_ids','exact_group_count','venues','alias_to_existing_w4b_official_event'])
    write_gz(REG/'w4c_r1_official_truth_extension_source_manifest_v1.csv.gz',list(source_manifest.values()),['source_authority','source_url','retrieved_at_utc','source_body_sha256_or_document_hash','evidence_excerpt_hash_or_structured_field_reference'])
    write_gz(REG/'w4c_r1_sec_transport_manifest_v1.csv.gz',sec_manifest,['source_authority','source_url','retrieved_at_utc','http_status','content_type','response_bytes','source_body_sha256_or_document_hash','purpose'])

    states=Counter(r['r1_verification_state'] for r in records); fam_verified=Counter(r['resolved_family'] for r in verified); review=Counter(r['review_mode'] for r in records)
    gate=(not contradictions and len(records)==1743 and all(r['exact_group_id'] for r in records))
    summary={
      'artifact':'W4C_R1_OFFICIAL_TRUTH_EXTENSION_SUMMARY','version':'W4C-R1-OTE-RESULT-v1.0','date_utc':datetime.now(timezone.utc).isoformat(),
      'protocol_version':proto['version'],'freeze_version':freeze['version'],'eligible_groups':1743,'decision_rows_accounted':len(records),
      'verification_state_counts':dict(sorted(states.items())),'verified_exact_groups_r1':len(verified),'r1_unique_official_events':len(groups),
      'r1_alias_groups_to_existing_w4b_official_events':len(alias_groups),'r1_new_unique_official_events':len(new_groups),
      'w4b_verified_unique_official_events_immutable':344,'combined_unique_official_events_after_r1':344+len(new_groups),
      'remaining_unresolved_r1':len(unresolved),'verified_family_counts':dict(sorted(fam_verified.items())),'review_mode_counts':dict(sorted(review.items())),
      'source_manifest_rows':len(source_manifest),'sec_transport_manifest_rows':len(sec_manifest),'identity_contradictions':contradictions,
      'performance_blind':True,'linked_asset_realized_returns_read':False,'prediction_market_performance_read':False,'prediction_market_settlement_results_read':False,'ARGOS_PnL_read':False,
      'release_values_used_for_identity':False,'w4b_artifacts_modified':False,'n_final_backtestable_authorized':False,'outcome_reveal_authorized':False,
      'gate_decision':'PASS_W4C_R1_OFFICIAL_TRUTH_EXTENSION_MATERIALIZED' if gate else 'FAIL_W4C_R1_OFFICIAL_TRUTH_EXTENSION_MATERIALIZATION',
      'interpretation':'R1 is separate W4-C extension evidence. W4-B remains immutable. New unique official-event gain is measured only from R1 W4OT1 identities not already present in frozen W4-B truth.'
    }
    (REG/'w4c_r1_official_truth_extension_summary_v1.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True),flush=True)
    if not gate: raise SystemExit(2)

if __name__=='__main__':
    main()

#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import io
import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'registry'
PROTO = json.loads((REG / 'w4b_forecastex_census_protocol_v1.json').read_text())
BASE = 'https://forecastex.com'
UA = 'ARGOS-W4B-ForecastEx-census/1.0'

# Reuse the already-frozen W4-B semantic and canonical-signature implementation.
SEM_PATH = ROOT / 'scripts' / 'w4b_kalshi_semantic_canonicalize_v1.py'
spec = importlib.util.spec_from_file_location('w4b_semantic_frozen', SEM_PATH)
SEM = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(SEM)


def get_bytes(url: str, retries: int = 6, max_bytes: int | None = None):
    last = None
    for i in range(retries):
        try:
            req = Request(url, headers={'User-Agent': UA, 'Accept': 'text/csv,text/html,*/*'})
            with urlopen(req, timeout=60) as r:
                body = r.read() if max_bytes is None else r.read(max_bytes)
                return {
                    'ok': True, 'status': getattr(r, 'status', 200), 'url': r.geturl(),
                    'content_type': r.headers.get('content-type', ''),
                    'content_disposition': r.headers.get('content-disposition', ''),
                    'body': body, 'error': None,
                }
        except HTTPError as e:
            b = b''
            try: b = e.read(2000)
            except Exception: pass
            last = {'ok': False, 'status': e.code, 'url': url, 'content_type': e.headers.get('content-type','') if e.headers else '', 'content_disposition': '', 'body': b, 'error': b.decode(errors='replace')[:1000] or str(e)}
            if e.code == 404:
                return last
            if 400 <= e.code < 500 and e.code != 429:
                return last
        except (URLError, TimeoutError, OSError) as e:
            last = {'ok': False, 'status': None, 'url': url, 'content_type': '', 'content_disposition': '', 'body': b'', 'error': str(e)}
        if i + 1 < retries:
            time.sleep(min(12.0, 0.8 * (2 ** i)))
    return last or {'ok': False, 'status': None, 'url': url, 'content_type': '', 'content_disposition': '', 'body': b'', 'error': 'unknown'}


def csv_rows(body: bytes):
    text = body.decode('utf-8-sig', errors='replace')
    return list(csv.DictReader(io.StringIO(text)))


def parse_date_value(v: str) -> str | None:
    s = (v or '').strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%Y%m%d', '%m/%d/%Y', '%m/%d/%y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00')).date().isoformat()
    except Exception:
        return None


def iter_dates(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def url_for(kind: str, d: date) -> str:
    return f"{BASE}/api/download?" + urlencode({'type': kind, 'date': d.strftime('%Y%m%d')})


def manifest_rec(kind: str, d: date, r: dict) -> dict:
    body = r.get('body') or b''
    return {
        'archive_date': d.isoformat(), 'file_type': kind, 'http_status': r.get('status') if r.get('status') is not None else '',
        'content_type': r.get('content_type') or '', 'content_disposition': r.get('content_disposition') or '',
        'byte_size': len(body), 'sha256': hashlib.sha256(body).hexdigest() if body else '',
        'resolved': 'YES' if r.get('ok') else ('NO_FILE_404' if r.get('status') == 404 else 'API_UNRESOLVED'),
    }


def write_gz(path: Path, rows: list[dict], fields: list[str]):
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows([{k:r.get(k,'') for k in fields} for r in rows])


def main():
    # Sequence firewall: an explicit authoritative history closeout must be on main checkout.
    closeout_path = REG / 'w4b_kalshi_history_closeout_v1_0_2.json'
    if not closeout_path.exists():
        raise SystemExit('SEQUENCE_GATE_MISSING_KALSHI_HISTORY_CLOSEOUT')
    h = json.loads(closeout_path.read_text())
    if h.get('history_version') != PROTO['sequence_prerequisite']['required_history_version'] or h.get('technical_gate_decision') != PROTO['sequence_prerequisite']['required_history_decision'] or int(h.get('api_unresolved_count', -1)) != 0:
        raise SystemExit('SEQUENCE_GATE_KALSHI_HISTORY_NOT_PASSED')

    page = get_bytes(PROTO['source_contract']['official_data_page'])
    if not page['ok']:
        raise SystemExit('FORECASTEX_DATA_PAGE_UNRESOLVED')
    html = page['body'].decode(errors='replace')
    displayed = sorted({datetime.strptime(x, '%Y-%m-%d').date() for x in re.findall(r'\b20\d{2}-\d{2}-\d{2}\b', html)})
    if not displayed:
        raise SystemExit('FORECASTEX_DATA_PAGE_NO_DATES')
    latest = max(displayed)
    start = datetime.strptime(PROTO['archive_enumeration']['start_date_inclusive'], '%Y-%m-%d').date()
    calendar = list(iter_dates(start, latest))

    # First pass: account for every date using the small summary file.
    summary_results = {}
    unresolved = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(get_bytes, url_for('summary', d)): d for d in calendar}
        for fut in as_completed(futs):
            d = futs[fut]
            try: r = fut.result()
            except Exception as e: r = {'ok':False,'status':None,'content_type':'','content_disposition':'','body':b'','error':repr(e)}
            summary_results[d] = r
            if not r.get('ok') and r.get('status') != 404:
                unresolved.append({'archive_date': d.isoformat(), 'file_type':'summary', 'status':r.get('status'), 'error':r.get('error')})
    if unresolved:
        raise SystemExit(f'FORECASTEX_SUMMARY_ENUMERATION_UNRESOLVED:{unresolved[:10]}')

    existing_dates = sorted(d for d,r in summary_results.items() if r.get('ok'))
    if not existing_dates:
        raise SystemExit('FORECASTEX_NO_ARCHIVE_DATES')

    manifest = []
    product_obs = defaultdict(lambda: {'names':set(), 'categories':set(), 'dates':set()})
    for d in calendar:
        r = summary_results[d]
        manifest.append(manifest_rec('summary', d, r))
        if not r.get('ok'):
            continue
        rows = csv_rows(r['body'])
        hdr = set(rows[0].keys()) if rows else set()
        need = set(PROTO['source_contract']['verified_headers']['summary'])
        if rows and not need.issubset(hdr):
            raise SystemExit(f'FORECASTEX_SUMMARY_SCHEMA_DRIFT:{d}:{sorted(hdr)}')
        for x in rows:
            pid = (x.get('product_id') or '').strip()
            if not pid: continue
            product_obs[pid]['names'].add((x.get('product_name') or '').strip())
            product_obs[pid]['categories'].add((x.get('product_category') or '').strip())
            product_obs[pid]['dates'].add(d.isoformat())

    # Second pass: prices files are used only for identifiers and expiry. Economic fields are never persisted/voted.
    price_results = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(get_bytes, url_for('prices', d)): d for d in existing_dates}
        for fut in as_completed(futs):
            d = futs[fut]
            try: r = fut.result()
            except Exception as e: r = {'ok':False,'status':None,'content_type':'','content_disposition':'','body':b'','error':repr(e)}
            price_results[d] = r

    products = []
    product_meta = {}
    for pid,obs in sorted(product_obs.items()):
        names = sorted(x for x in obs['names'] if x); cats = sorted(x for x in obs['categories'] if x); ds=sorted(obs['dates'])
        rec={'product_id':pid,'product_name':' | '.join(names),'product_category':' | '.join(cats),'first_archive_date':ds[0] if ds else '','last_archive_date':ds[-1] if ds else '','archive_days_seen':len(ds)}
        products.append(rec); product_meta[pid]=rec
    product_ids = sorted(product_meta, key=lambda x:(-len(x),x))

    contract_seen = {}
    rejected_count = 0; ambiguous = []; schema_errors=[]; price_unresolved=[]
    for d in existing_dates:
        r = price_results[d]
        manifest.append(manifest_rec('prices', d, r))
        if not r.get('ok'):
            price_unresolved.append({'archive_date':d.isoformat(),'status':r.get('status'),'error':r.get('error')})
            continue
        rows = csv_rows(r['body'])
        hdr = set(rows[0].keys()) if rows else set()
        required = {'event_contract','subtype','expiration_date','date'}
        if rows and not required.issubset(hdr):
            schema_errors.append({'archive_date':d.isoformat(),'header':sorted(hdr)})
            continue
        for x in rows:
            contract=(x.get('event_contract') or '').strip(); subtype=(x.get('subtype') or '').strip(); exp_raw=(x.get('expiration_date') or '').strip()
            if not contract: continue
            exp=parse_date_value(exp_raw)
            # Longest known product-id prefix; no activity/price fields participate.
            pid=next((p for p in product_ids if contract.upper().startswith(p.upper())), '')
            meta=product_meta.get(pid, {'product_name':'','product_category':''})
            text=' '.join([pid, meta.get('product_name',''), meta.get('product_category',''), contract])
            passes=SEM.strict_families(text)
            fam,status=SEM.resolve_family(passes)
            subject=SEM.subject_key(fam,text) if fam else ''
            cstatus='PASS' if fam and exp and subject else ('CANONICALIZATION_AMBIGUOUS' if fam else 'NOT_APPLICABLE')
            cid=SEM.canonical_id(fam,exp,subject) if cstatus=='PASS' else ''
            key=(contract,subtype,exp_raw)
            rec=contract_seen.setdefault(key,{
                'event_contract':contract,'subtype':subtype,'expiration_date':exp or exp_raw,'product_id':pid,
                'product_name':meta.get('product_name',''),'product_category':meta.get('product_category',''),
                'strict_family_hits':'|'.join(passes),'resolved_family':fam or '', 'semantic_status':status,
                'normalized_subject_key':subject,'canonicalization_status':cstatus,'canonical_event_id':cid,
                'first_archive_date':d.isoformat(),'last_archive_date':d.isoformat(),'archive_days_seen':0,
            })
            rec['first_archive_date']=min(rec['first_archive_date'],d.isoformat()); rec['last_archive_date']=max(rec['last_archive_date'],d.isoformat()); rec['archive_days_seen']+=1

    if price_unresolved or schema_errors:
        # Diagnostics are still materialized below; final gate fails.
        pass

    contracts=sorted(contract_seen.values(), key=lambda x:(x['event_contract'],x['subtype'],x['expiration_date']))
    event_groups=defaultdict(list)
    for r in contracts:
        if r['semantic_status'].startswith('ACCEPT') and r['canonicalization_status']=='PASS':
            event_groups[r['canonical_event_id']].append(r)
        elif r['semantic_status'].startswith('AMBIGUOUS') or r['canonicalization_status']=='CANONICALIZATION_AMBIGUOUS':
            ambiguous.append(r)
        else:
            rejected_count += 1

    events=[]; collision=[]; family_counts=defaultdict(int)
    for cid,rows in sorted(event_groups.items()):
        sigs={(r['resolved_family'],r['expiration_date'],r['normalized_subject_key']) for r in rows}
        if len(sigs)!=1:
            collision.append({'canonical_event_id':cid,'signatures':sorted(sigs)})
            continue
        fam,exp,subject=next(iter(sigs)); family_counts[fam]+=1
        events.append({
            'canonical_event_id':cid,'resolved_family':fam,'event_reference_date':exp,'normalized_subject_key':subject,
            'product_ids':'|'.join(sorted({r['product_id'] for r in rows if r['product_id']})),
            'venue_contracts':len(rows),'first_archive_date':min(r['first_archive_date'] for r in rows),
            'last_archive_date':max(r['last_archive_date'] for r in rows),
        })

    manifest=sorted(manifest,key=lambda x:(x['archive_date'],x['file_type']))
    write_gz(REG/'w4b_forecastex_file_manifest_v1.csv.gz',manifest,['archive_date','file_type','http_status','content_type','content_disposition','byte_size','sha256','resolved'])
    with (REG/'w4b_forecastex_products_v1.csv').open('w',encoding='utf-8',newline='') as f:
        fields=['product_id','product_name','product_category','first_archive_date','last_archive_date','archive_days_seen']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(products)
    write_gz(REG/'w4b_forecastex_contracts_v1.csv.gz',contracts,['event_contract','subtype','expiration_date','product_id','product_name','product_category','strict_family_hits','resolved_family','semantic_status','normalized_subject_key','canonicalization_status','canonical_event_id','first_archive_date','last_archive_date','archive_days_seen'])
    write_gz(REG/'w4b_forecastex_events_v1.csv.gz',events,['canonical_event_id','resolved_family','event_reference_date','normalized_subject_key','product_ids','venue_contracts','first_archive_date','last_archive_date'])
    write_gz(REG/'w4b_forecastex_ambiguous_v1.csv.gz',ambiguous,['event_contract','subtype','expiration_date','product_id','product_name','product_category','strict_family_hits','resolved_family','semantic_status','normalized_subject_key','canonicalization_status','canonical_event_id','first_archive_date','last_archive_date','archive_days_seen'])

    gate = not unresolved and not price_unresolved and not schema_errors and not collision and len(existing_dates)>0
    out={
        'artifact':'W4B_FORECASTEX_CENSUS_SUMMARY','version':'W4B-FX-C-RESULT-v1.0','date_utc':datetime.now(timezone.utc).isoformat(),
        'protocol_version':PROTO['version'],'performance_blind':True,'linked_asset_realized_returns_read':False,
        'price_volume_oi_settlement_used_for_selection':False,'calendar_start':start.isoformat(),'calendar_end':latest.isoformat(),
        'calendar_days_accounted':len(calendar),'archive_dates_with_summary':len(existing_dates),'summary_404_dates':sum(1 for d in calendar if summary_results[d].get('status')==404),
        'products_observed':len(products),'unique_contract_identifier_rows':len(contracts),'accepted_unique_canonical_events':len(events),
        'accepted_family_counts':dict(sorted(family_counts.items())),'ambiguous_contract_rows':len(ambiguous),'rejected_contract_rows':rejected_count,
        'summary_transport_unresolved':unresolved,'prices_transport_unresolved':price_unresolved,'schema_errors':schema_errors,'canonical_collisions':collision,
        'gate_decision':'PASS_FORECASTEX_CENSUS_MATERIALIZED' if gate else 'FAIL_FORECASTEX_CENSUS_MATERIALIZATION',
        'interpretation':'Performance-blind official ForecastEx archive census. Accepted canonical counts are venue capacity only; not yet cross-venue deduplicated, official-event-truth certified, PIT-history qualified or N_final_backtestable.'
    }
    (REG/'w4b_forecastex_census_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:out[k] for k in ['calendar_days_accounted','archive_dates_with_summary','products_observed','unique_contract_identifier_rows','accepted_unique_canonical_events','accepted_family_counts','ambiguous_contract_rows','gate_decision']},indent=2,sort_keys=True))
    if not gate: raise SystemExit(2)

if __name__=='__main__': main()

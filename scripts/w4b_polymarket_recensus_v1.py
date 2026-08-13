#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'registry'
PROTO = json.loads((REG / 'w4b_polymarket_recensus_protocol_v1.json').read_text())
BASE = PROTO['source_contract']['official_gamma_base']
UA = 'ARGOS-W4B-Polymarket-recensus/1.0'

SEM_PATH = ROOT / 'scripts' / 'w4b_kalshi_semantic_canonicalize_v1.py'
spec = importlib.util.spec_from_file_location('w4b_semantic_frozen_pm', SEM_PATH)
SEM = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(SEM)

W2_PATH = REG / 'w2c_semantic_v2_accepted_clusters_v1_1.csv'


def get_json_bytes(url: str, retries: int = 7):
    last = None
    for i in range(retries):
        try:
            req = Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urlopen(req, timeout=60) as r:
                body = r.read()
                return json.loads(body.decode()), body, getattr(r, 'status', 200), None
        except HTTPError as e:
            b = b''
            try: b = e.read(3000)
            except Exception: pass
            last = {'status': e.code, 'error': b.decode(errors='replace')[:2000] or str(e), 'url': url}
            if 400 <= e.code < 500 and e.code != 429:
                return None, b, e.code, last
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            last = {'status': None, 'error': str(e), 'url': url}
        if i + 1 < retries:
            time.sleep(min(16.0, 0.8 * (2 ** i)))
    return None, b'', (last or {}).get('status'), last or {'status': None, 'error': 'unknown', 'url': url}


def parse_utc_date(v: str) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date().isoformat()
    except Exception:
        for fmt in ('%Y-%m-%d', '%Y%m%d'):
            try: return datetime.strptime(s[:10], fmt).date().isoformat()
            except Exception: pass
    return None


def scalar_text(v) -> str:
    if v is None: return ''
    if isinstance(v, (str, int, float)): return str(v)
    return ''


def semantic_text(ev: dict) -> str:
    parts = [scalar_text(ev.get('title')), scalar_text(ev.get('subtitle')), scalar_text(ev.get('slug'))]
    markets = ev.get('markets') or []
    if isinstance(markets, list):
        for m in markets:
            if not isinstance(m, dict): continue
            parts.append(scalar_text(m.get('question')))
            parts.append(scalar_text(m.get('groupItemTitle')))
    return ' '.join(x for x in parts if x)


def write_gz(path: Path, rows: list[dict], fields: list[str]):
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows([{k:r.get(k,'') for k in fields} for r in rows])


def load_w2():
    by_id = defaultdict(list); by_slug = defaultdict(list); rows=[]
    with W2_PATH.open('r', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            rows.append(r)
            eid=(r.get('event_id') or '').strip(); slug=(r.get('slug') or '').strip().lower()
            if eid: by_id[eid].append(r)
            if slug: by_slug[slug].append(r)
    return rows, by_id, by_slug


def main():
    closeout_path = REG / 'w4b_forecastex_census_closeout_v1.json'
    if not closeout_path.exists():
        raise SystemExit('SEQUENCE_GATE_MISSING_FORECASTEX_CLOSEOUT')
    fx = json.loads(closeout_path.read_text())
    if fx.get('technical_gate_decision') != PROTO['sequence_prerequisite']['required_decision']:
        raise SystemExit('SEQUENCE_GATE_FORECASTEX_NOT_PASSED')

    all_events = {}
    duplicate_api_rows = 0
    pages = []
    unresolved = []
    cursor = ''
    seen_cursors = set()
    page_no = 0
    raw_event_rows = 0

    while True:
        q = {'closed': 'true', 'limit': 500}
        if cursor:
            q['after_cursor'] = cursor
        url = BASE + PROTO['source_contract']['endpoint'] + '?' + urlencode(q)
        obj, body, status, err = get_json_bytes(url)
        if err or status != 200 or not isinstance(obj, dict):
            unresolved.append({'page_number': page_no + 1, 'status': status if status is not None else '', 'error': (err or {}).get('error',''), 'cursor_sha256': hashlib.sha256(cursor.encode()).hexdigest() if cursor else ''})
            break
        batch = obj.get('events')
        if not isinstance(batch, list):
            unresolved.append({'page_number': page_no + 1, 'status': status, 'error': 'invalid_events_wrapper', 'cursor_sha256': hashlib.sha256(cursor.encode()).hexdigest() if cursor else ''})
            break
        page_no += 1
        raw_event_rows += len(batch)
        next_cursor = obj.get('next_cursor') or ''
        pages.append({
            'page_number': page_no,
            'input_cursor_sha256': hashlib.sha256(cursor.encode()).hexdigest() if cursor else '',
            'output_cursor_sha256': hashlib.sha256(next_cursor.encode()).hexdigest() if next_cursor else '',
            'event_rows_returned': len(batch),
            'http_status': status,
            'response_bytes': len(body),
            'response_sha256': hashlib.sha256(body).hexdigest(),
            'terminal_page': 'YES' if not next_cursor else 'NO',
        })
        for ev in batch:
            if not isinstance(ev, dict): continue
            eid = str(ev.get('id') or '').strip()
            if not eid: continue
            if eid in all_events:
                duplicate_api_rows += 1
                continue
            all_events[eid] = ev
        if not next_cursor:
            break
        if next_cursor in seen_cursors:
            unresolved.append({'page_number': page_no, 'status': 200, 'error': 'cursor_cycle_detected', 'cursor_sha256': hashlib.sha256(next_cursor.encode()).hexdigest()})
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        if page_no % 20 == 0:
            print(f'polymarket_pages={page_no} unique_events={len(all_events)}', flush=True)

    if unresolved:
        # Do not silently treat partial pagination as the population.
        raise SystemExit(f'POLYMARKET_PAGINATION_UNRESOLVED:{unresolved[:5]}')

    w2_rows, w2_by_id, w2_by_slug = load_w2()
    venue_rows=[]; ambiguous=[]; overlap=[]; rejected=0
    canonical_groups=defaultdict(list)
    w2_seen=set()
    for eid,ev in sorted(all_events.items(), key=lambda kv: (int(kv[0]) if kv[0].isdigit() else 10**30, kv[0])):
        text = semantic_text(ev)
        passes = SEM.strict_families(text)
        fam,status = SEM.resolve_family(passes)
        ref_date = parse_utc_date(ev.get('endDate') or '')
        subject = SEM.subject_key(fam,text) if fam else ''
        cstatus = 'PASS' if fam and ref_date and subject else ('CANONICALIZATION_AMBIGUOUS' if fam else 'NOT_APPLICABLE')
        cid = SEM.canonical_id(fam,ref_date,subject) if cstatus == 'PASS' else ''
        markets = ev.get('markets') or []
        market_ids=[]
        if isinstance(markets,list):
            for m in markets:
                if isinstance(m,dict) and m.get('id') is not None: market_ids.append(str(m.get('id')))
        row={
            'gamma_event_id':eid,
            'title':scalar_text(ev.get('title')),
            'slug':scalar_text(ev.get('slug')),
            'end_date':scalar_text(ev.get('endDate')),
            'event_reference_date':ref_date or '',
            'associated_market_count':len(markets) if isinstance(markets,list) else 0,
            'market_ids':'|'.join(sorted(set(market_ids))),
            'strict_family_hits':'|'.join(passes),
            'resolved_family':fam or '',
            'semantic_status':status,
            'normalized_subject_key':subject,
            'canonicalization_status':cstatus,
            'canonical_event_id':cid,
            'semantic_text_sha256':hashlib.sha256(SEM.norm(text).encode()).hexdigest(),
        }
        venue_rows.append(row)
        if status.startswith('ACCEPT') and cstatus=='PASS':
            canonical_groups[cid].append(row)
        elif status.startswith('AMBIGUOUS') or cstatus=='CANONICALIZATION_AMBIGUOUS':
            ambiguous.append(row)
        else:
            rejected += 1

        slug=(row['slug'] or '').strip().lower()
        matches=[]; match_type='NEW_TO_W4_RECENSUS'
        if eid in w2_by_id:
            matches=w2_by_id[eid]; match_type='MATCH_EVENT_ID'
        elif slug and slug in w2_by_slug:
            matches=w2_by_slug[slug]; match_type='MATCH_SLUG'
        if matches:
            for m in matches:
                w2_seen.add((m.get('event_id',''),m.get('independence_cluster_id','')))
        overlap.append({
            'gamma_event_id':eid,'slug':row['slug'],'w4_semantic_status':status,'w4_resolved_family':fam or '',
            'w4_canonical_event_id':cid,'w2_overlap_type':match_type,
            'w2_event_ids':'|'.join(sorted({m.get('event_id','') for m in matches if m.get('event_id')})),
            'w2_cluster_ids':'|'.join(sorted({m.get('independence_cluster_id','') for m in matches if m.get('independence_cluster_id')})),
            'w2_families_audit_only':'|'.join(sorted({m.get('resolved_family','') for m in matches if m.get('resolved_family')})),
        })

    events=[]; collisions=[]; family_counts=Counter(); aliases_collapsed=0
    for cid,rows in sorted(canonical_groups.items()):
        sigs={(r['resolved_family'],r['event_reference_date'],r['normalized_subject_key']) for r in rows}
        if len(sigs)!=1:
            collisions.append({'canonical_event_id':cid,'signatures':['|'.join(x) for x in sorted(sigs)]})
            continue
        fam,ref_date,subject=next(iter(sigs)); family_counts[fam]+=1; aliases_collapsed += max(0,len(rows)-1)
        events.append({
            'canonical_event_id':cid,'resolved_family':fam,'event_reference_date':ref_date,'normalized_subject_key':subject,
            'gamma_event_ids':'|'.join(sorted(r['gamma_event_id'] for r in rows)),
            'gamma_event_alias_count':len(rows),
            'slugs':'|'.join(sorted({r['slug'] for r in rows if r['slug']})),
            'associated_market_count':sum(int(r['associated_market_count']) for r in rows),
        })

    w2_total_keys={(r.get('event_id',''),r.get('independence_cluster_id','')) for r in w2_rows}
    w2_not_rediscovered=len(w2_total_keys-w2_seen)

    write_gz(REG/'w4b_polymarket_recensus_page_manifest_v1.csv.gz',pages,['page_number','input_cursor_sha256','output_cursor_sha256','event_rows_returned','http_status','response_bytes','response_sha256','terminal_page'])
    write_gz(REG/'w4b_polymarket_recensus_venue_events_v1.csv.gz',venue_rows,['gamma_event_id','title','slug','end_date','event_reference_date','associated_market_count','market_ids','strict_family_hits','resolved_family','semantic_status','normalized_subject_key','canonicalization_status','canonical_event_id','semantic_text_sha256'])
    write_gz(REG/'w4b_polymarket_recensus_events_v1.csv.gz',events,['canonical_event_id','resolved_family','event_reference_date','normalized_subject_key','gamma_event_ids','gamma_event_alias_count','slugs','associated_market_count'])
    write_gz(REG/'w4b_polymarket_recensus_ambiguous_v1.csv.gz',ambiguous,['gamma_event_id','title','slug','end_date','event_reference_date','associated_market_count','market_ids','strict_family_hits','resolved_family','semantic_status','normalized_subject_key','canonicalization_status','canonical_event_id','semantic_text_sha256'])
    write_gz(REG/'w4b_polymarket_w2_overlap_v1.csv.gz',overlap,['gamma_event_id','slug','w4_semantic_status','w4_resolved_family','w4_canonical_event_id','w2_overlap_type','w2_event_ids','w2_cluster_ids','w2_families_audit_only'])

    gate = not unresolved and not collisions and bool(pages) and pages[-1]['terminal_page']=='YES'
    out={
        'artifact':'W4B_POLYMARKET_RECENSUS_SUMMARY','version':'W4B-PM-R-RESULT-v1.0','date_utc':datetime.now(timezone.utc).isoformat(),
        'protocol_version':PROTO['version'],'performance_blind':True,'linked_asset_realized_returns_read':False,
        'clob_price_history_read':False,'selection_by_volume_liquidity_or_price':False,
        'pages_fetched':len(pages),'raw_event_rows':raw_event_rows,'unique_gamma_event_ids':len(all_events),'duplicate_api_event_rows':duplicate_api_rows,
        'venue_event_rows_classified':len(venue_rows),'accepted_unique_canonical_events':len(events),'canonical_alias_rows_collapsed':aliases_collapsed,
        'accepted_family_counts':dict(sorted(family_counts.items())),'ambiguous_venue_event_rows':len(ambiguous),'rejected_venue_event_rows':rejected,
        'w2_accepted_rows':len(w2_rows),'w2_overlap_event_id':sum(r['w2_overlap_type']=='MATCH_EVENT_ID' for r in overlap),'w2_overlap_slug_only':sum(r['w2_overlap_type']=='MATCH_SLUG' for r in overlap),
        'w2_new_gamma_events':sum(r['w2_overlap_type']=='NEW_TO_W4_RECENSUS' for r in overlap),'w2_accepted_keys_not_rediscovered':w2_not_rediscovered,
        'pagination_unresolved':unresolved,'canonical_collisions':collisions,
        'gate_decision':'PASS_POLYMARKET_RECENSUS_MATERIALIZED' if gate else 'FAIL_POLYMARKET_RECENSUS_MATERIALIZATION',
        'interpretation':'Exhaustive performance-blind closed-event Gamma recensus. Counts are venue semantic/canonical capacity only; no price history was read and counts are not yet cross-venue deduplicated, official-truth-certified or N_final_backtestable.'
    }
    (REG/'w4b_polymarket_recensus_summary_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:out[k] for k in ['pages_fetched','raw_event_rows','unique_gamma_event_ids','accepted_unique_canonical_events','accepted_family_counts','ambiguous_venue_event_rows','w2_overlap_event_id','w2_overlap_slug_only','w2_new_gamma_events','gate_decision']},indent=2,sort_keys=True))
    if not gate: raise SystemExit(2)

if __name__=='__main__': main()

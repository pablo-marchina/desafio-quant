#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / 'registry'
BASE = 'https://forecastex.com'
DATA_PAGE = BASE + '/data'
UA = 'ARGOS-W4B-ForecastEx-access-probe/1.0'


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.scripts=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=='a' and d.get('href'): self.links.append(d['href'])
        if tag=='script' and d.get('src'): self.scripts.append(d['src'])


def fetch(url: str, retries: int = 4, max_bytes: int = 8_000_000):
    last=None
    for i in range(retries):
        try:
            req=Request(url,headers={'User-Agent':UA,'Accept':'*/*'})
            with urlopen(req,timeout=45) as r:
                body=r.read(max_bytes)
                return {'ok':True,'status':getattr(r,'status',200),'url':r.geturl(),'content_type':r.headers.get('content-type',''),'content_disposition':r.headers.get('content-disposition',''),'body':body,'error':None}
        except HTTPError as e:
            body=b''
            try: body=e.read(2000)
            except Exception: pass
            last={'ok':False,'status':e.code,'url':url,'content_type':e.headers.get('content-type','') if e.headers else '', 'content_disposition':'','body':body,'error':body.decode(errors='replace')[:1000] or str(e)}
            if 400 <= e.code < 500 and e.code != 429: return last
        except (URLError,TimeoutError,OSError) as e:
            last={'ok':False,'status':None,'url':url,'content_type':'','content_disposition':'','body':b'','error':str(e)}
        if i+1<retries: time.sleep(1.0*(i+1))
    return last


def csv_header(body: bytes):
    try:
        text=body.decode('utf-8-sig',errors='replace')
        row=next(csv.reader(io.StringIO(text)))
        return [x.strip() for x in row]
    except Exception:
        return []


def main():
    page=fetch(DATA_PAGE)
    if not page['ok']:
        raise SystemExit('FORECASTEX_DATA_PAGE_UNAVAILABLE')
    html=page['body'].decode(errors='replace')
    p=LinkParser(); p.feed(html)
    same_links=sorted({urljoin(BASE,x) for x in p.links if urlparse(urljoin(BASE,x)).netloc.endswith('forecastex.com')})
    scripts=sorted({urljoin(BASE,x) for x in p.scripts if urlparse(urljoin(BASE,x)).netloc.endswith('forecastex.com')})

    literal_candidates=set()
    for u in same_links:
        if '.csv' in u.lower() or '/api/download' in u.lower(): literal_candidates.add(u)

    js_hits=[]
    for u in scripts[:80]:
        r=fetch(u,max_bytes=6_000_000)
        if not r['ok']: continue
        text=r['body'].decode(errors='replace')
        if 'api/download' in text.lower() or ('pairs' in text.lower() and 'summary' in text.lower() and 'prices' in text.lower()):
            snippets=[]
            for m in re.finditer(r'api/download',text,re.I):
                snippets.append(text[max(0,m.start()-350):min(len(text),m.end()+650)])
            for s in snippets[:10]:
                for m in re.finditer(r'[/A-Za-z0-9_.?=&${}:\-]{1,300}api/download[/A-Za-z0-9_.?=&${}:\-]{0,400}',s,re.I):
                    literal_candidates.add(urljoin(BASE,m.group(0)))
            js_hits.append({'script_url':u,'sha256':hashlib.sha256(r['body']).hexdigest(),'download_snippets':[re.sub(r'\s+',' ',x)[:1000] for x in snippets[:5]]})

    # Known public-path lead is validated only against the official ForecastEx host.
    # No row counts, prices, settlement values or trading statistics are persisted.
    probe_date='2026-07-17'
    variants=[]
    for kind in ('pairs','prices','summary'):
        for url in (
            f'{BASE}/api/download?date={probe_date}&type={kind}',
            f'{BASE}/api/download?date={probe_date}&file={kind}',
            f'{BASE}/api/download?date={probe_date}&fileType={kind}',
            f'{BASE}/api/download?date={probe_date}&dataType={kind}',
            f'{BASE}/api/download?type={kind}&date={probe_date}',
            f'{BASE}/api/download?file={kind}&date={probe_date}',
        ):
            variants.append((kind,url))

    # Also probe any literal href that already carries both endpoint and query.
    for u in sorted(literal_candidates):
        if '/api/download' in u and '?' in u:
            variants.append(('literal',u))

    seen=set(); probes=[]; successful=[]
    for kind,url in variants:
        if url in seen: continue
        seen.add(url)
        r=fetch(url,max_bytes=512_000)
        body=r.get('body') or b''
        header=csv_header(body) if r.get('ok') else []
        looks_csv=bool(header) and len(header)>=2 and ('csv' in (r.get('content_type') or '').lower() or ',' in body[:500].decode(errors='ignore'))
        rec={
            'kind_hint':kind,'request_url':url,'ok':bool(r.get('ok')),'status':r.get('status'),
            'final_url':r.get('url'),'content_type':r.get('content_type'),'content_disposition':r.get('content_disposition'),
            'looks_csv':looks_csv,'header':header[:80],
            'body_sha256':hashlib.sha256(body).hexdigest() if body else '',
            'body_bytes_observed':len(body),
            'error':r.get('error') if not r.get('ok') else None,
        }
        probes.append(rec)
        if looks_csv: successful.append(rec)

    out={
        'artifact':'W4B_FORECASTEX_PUBLIC_DATA_ACCESS_PROBE',
        'version':'W4B-FX-AP-v1.0',
        'performance_blind':True,
        'linked_asset_realized_returns_read':False,
        'forecast_ex_prices_persisted':False,
        'census_executed':False,
        'data_page_url':DATA_PAGE,
        'data_page_sha256':hashlib.sha256(page['body']).hexdigest(),
        'same_domain_link_count':len(same_links),
        'script_count':len(scripts),
        'literal_download_candidates':sorted(literal_candidates),
        'js_hits':js_hits,
        'probes':probes,
        'successful_csv_access_patterns':successful,
        'gate_decision':'PASS_PUBLIC_CSV_ACCESS_IDENTIFIED' if successful else 'FAIL_PUBLIC_CSV_ACCESS_NOT_IDENTIFIED',
        'interpretation':'Access/schema probe only. It does not enumerate the ForecastEx archive, count contracts/events, classify families, read linked-asset outcomes, or produce W4-B census N.'
    }
    (REG/'w4b_forecastex_access_probe_v1.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'successful_csv_patterns':len(successful),'gate_decision':out['gate_decision'],'headers':[x['header'] for x in successful[:6]]},indent=2))
    if not successful: raise SystemExit(2)

if __name__=='__main__': main()

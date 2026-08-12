#!/usr/bin/env python3
"""W2C PIT-v2.1 Layer B/C collector.

Performance-blind collector for authoritative public revelation/resolution
evidence and linked-asset data availability. It never computes or persists
linked-asset returns, PnL, model metrics, or family scores.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PROTOCOL = Path("registry/w2c_pit_protocol_v2_1.json")
QUEUE = Path("registry/w2c_pit_v2_1_primary_source_queue.csv")
OUT = Path("registry/w2c_pit_v2_1_primary_asset_events.csv.gz")
RAW = Path("registry/w2c_pit_v2_1_primary_asset_request_manifest.jsonl.gz")
SUMMARY = Path("registry/w2c_pit_v2_1_primary_asset_summary.json")

VERSION = "W2C-PIT-PRIMARY-ASSET-RUN-v2.1"
UA = "ARGOS-W2C-PIT-v2.1 public-research contact=pablo-marchina/desafio-quant"
ASOF = datetime.fromisoformat("2026-08-12T20:00:00+00:00")
ET = ZoneInfo("America/New_York")
RETRYABLE = {429, 500, 502, 503, 504}
SEC_FORMS = {"8-K", "6-K", "10-Q", "10-K", "20-F", "40-F"}

SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUB = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_ARCH = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{name}"
SEC_INDEX = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/index.json"
FDA_ZIP = "https://www.fda.gov/media/89850/download?attachment="
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
BLS_PATTERNS = {
    "BLS_CPI": ("cpi", ("cpi", "consumer price index")),
    "BLS_PPI": ("ppi", ("ppi", "producer price index")),
    "BLS_EMPSIT": ("empsit", ("employment situation", "unemployment", "payroll", "jobs")),
}

# Run-local byte cache. The key contains the exact URL and Accept header, so the
# cache cannot broaden source scope or alter PIT semantics. Only successful
# responses and deterministic 404/410 absence are cached; network/rate failures
# remain retryable and therefore remain UNRESOLVED rather than evidence of absence.
HTTP_CACHE: dict[tuple[str, str], tuple[bytes | None, dict]] = {}

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def parse_dt(v: str) -> datetime:
    return datetime.fromisoformat(v.replace("Z", "+00:00"))

def norm(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("’", "'").replace("–", "-").replace("—", "-")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())

def tokens(s: str) -> set[str]:
    stop = {"the","a","an","and","or","of","for","to","in","on","with","will","fda","approve","approves","approval","by"}
    return {x for x in norm(s).split() if len(x) >= 3 and x not in stop}

def request_bytes(url: str, *, timeout: int = 35, attempts: int = 4, accept: str = "*/*"):
    key = (url, accept)
    if key in HTTP_CACHE:
        body, cached = HTTP_CACHE[key]
        meta = dict(cached)
        meta["cache_hit"] = True
        return body, meta

    errors = []
    last_status = None
    for i in range(attempts):
        fetched = utcnow()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                code = getattr(resp, "status", 200)
            time.sleep(0.11)
            meta = {"url": url, "fetched_utc": fetched, "http_status": code, "bytes": len(body), "sha256": sha256(body), "state": "PASS", "errors": errors, "cache_hit": False}
            HTTP_CACHE[key] = (body, dict(meta))
            return body, meta
        except urllib.error.HTTPError as e:
            last_status = e.code
            errors.append(f"HTTPError:{e.code}")
            if e.code in {404, 410}:
                meta = {"url": url, "fetched_utc": fetched, "http_status": e.code, "bytes": 0, "sha256": "", "state": "HTTP_NOT_FOUND", "errors": errors, "cache_hit": False}
                HTTP_CACHE[key] = (None, dict(meta))
                return None, meta
            if e.code not in RETRYABLE or i == attempts - 1:
                break
        except (urllib.error.URLError, TimeoutError) as e:
            errors.append(type(e).__name__)
            if i == attempts - 1:
                break
        time.sleep(min(0.7 * (2 ** i), 5))
    return None, {"url": url, "fetched_utc": utcnow(), "http_status": last_status, "bytes": 0, "sha256": "", "state": "UNRESOLVED", "errors": errors, "cache_hit": False}

def request_json(url: str):
    b, meta = request_bytes(url, accept="application/json")
    if b is None:
        return None, meta
    try:
        return json.loads(b.decode("utf-8")), meta
    except Exception as e:
        meta = dict(meta); meta["state"] = "UNRESOLVED"; meta["errors"] = list(meta.get("errors", [])) + [f"JSON:{type(e).__name__}"]
        return None, meta

def html_text(b: bytes) -> str:
    s = b.decode("utf-8", "replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&#39;", "'").replace("&amp;", "&")
    return re.sub(r"\s+", " ", s).strip()

def write_gz_csv(path: Path, rows: list[dict]):
    fields = []
    for r in rows:
        for k in r:
            if k not in fields: fields.append(k)
    sio = io.StringIO(newline=""); w = csv.DictWriter(sio, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    with path.open("wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz: gz.write(sio.getvalue().encode())

def write_jsonl_gz(path: Path, rows: list[dict]):
    with path.open("wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
            for r in rows: gz.write((json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode())

def date_conservative(date_text: str, tz: ZoneInfo = ET) -> tuple[str, str]:
    d = datetime.strptime(date_text[:10], "%Y-%m-%d").date(); reveal = datetime(d.year, d.month, d.day, tzinfo=tz)
    return iso(reveal), iso(reveal - timedelta(seconds=1))

def sec_acceptance_to_utc(v: str) -> str:
    x = datetime.fromisoformat(v)
    if x.tzinfo is None: x = x.replace(tzinfo=ET)
    return iso(x)

def load_queue() -> list[dict]:
    rows = list(csv.DictReader(QUEUE.open(encoding="utf-8", newline="")))
    assert len(rows) == 260 and len({r["event_id"] for r in rows}) == 260
    return rows

def sec_ticker_map(raw_manifest: list[dict]):
    js, meta = request_json(SEC_TICKERS); raw_manifest.append({"scope": "GLOBAL", "endpoint": "sec_company_tickers", **meta})
    if not isinstance(js, dict): return {}, []
    by_ticker, companies = {}, []
    for r in js.values():
        ticker = str(r.get("ticker", "")).upper().strip()
        if not ticker: continue
        cik = int(r.get("cik_str")); title = str(r.get("title", "")); by_ticker[ticker] = {"cik": cik, "title": title, "ticker": ticker}
        companies.append({"cik": cik, "title": title, "ticker": ticker, "norm_title": norm(title), "title_tokens": tokens(title)})
    return by_ticker, companies

def recent_filings(js: dict) -> list[dict]:
    rec = (js or {}).get("filings", {}).get("recent", {}); keys = ["accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "primaryDocument", "primaryDocDescription"]
    n = len(rec.get("accessionNumber", [])); out = []
    for i in range(n): out.append({k: (rec.get(k, [""] * n)[i] if i < len(rec.get(k, [])) else "") for k in keys})
    return out

def choose_earnings_filing(rows: list[dict], target: datetime):
    cand = []
    for r in rows:
        if r.get("form") not in SEC_FORMS: continue
        try: fd = datetime.strptime(r.get("filingDate", ""), "%Y-%m-%d").date()
        except Exception: continue
        delta = (fd - target.date()).days
        if -3 <= delta <= 8: cand.append((abs(delta), 0 if r.get("form") in {"8-K", "6-K"} else 1, fd, r))
    cand.sort(key=lambda x: (x[0], x[1], x[2])); return [x[-1] for x in cand[:6]]

def sec_doc_candidates(cik: int, filing: dict, raw_manifest: list[dict], event_id: str):
    acc_dash = filing.get("accessionNumber", ""); acc = acc_dash.replace("-", "")
    if not acc: return []
    idx_url = SEC_INDEX.format(cik=cik, acc=acc); idx, meta = request_json(idx_url); raw_manifest.append({"event_id": event_id, "endpoint": "sec_filing_index", **meta}); names = []
    if isinstance(idx, dict):
        for item in idx.get("directory", {}).get("item", []):
            name = str(item.get("name", ""))
            if name.lower().endswith((".htm", ".html", ".txt")): names.append(name)
    primary = filing.get("primaryDocument", "")
    if primary: names.append(primary)
    def rank(name):
        low=name.lower(); return (0 if re.search(r"(ex(?:hibit)?[-_]?99|99[-_.]?1|earnings|press|release|results)", low) else 1, 0 if name == primary else 1, name)
    return [(name, SEC_ARCH.format(cik=cik, acc=acc, name=name)) for name in sorted(set(names), key=rank)[:7]]

def earnings_evidence(q: dict, ticker_map: dict, raw_manifest: list[dict]) -> dict:
    out = {}; ticker = q.get("linked_asset", "").upper(); sec = ticker_map.get(ticker)
    if not sec: return {"linked_asset_mapping_state": "UNRESOLVED", "linked_asset_mapping_source_url": SEC_TICKERS, "revelation_state": "UNRESOLVED", "resolution_state": "UNRESOLVED", "adjudication_notes": "No exact SEC ticker mapping."}
    out.update({"linked_asset": ticker, "linked_asset_mapping_state": "PASS", "linked_asset_mapping_basis": "EXACT_SEC_TICKER_TO_CIK", "linked_asset_mapping_source_url": SEC_TICKERS})
    url = SEC_SUB.format(cik=sec["cik"]); js, meta = request_json(url); raw_manifest.append({"event_id": q["event_id"], "endpoint": "sec_submissions", **meta})
    if not isinstance(js, dict): out.update({"revelation_state": "UNRESOLVED", "resolution_state": "UNRESOLVED", "adjudication_notes": "SEC submissions unavailable."}); return out
    target = parse_dt(q["semantic_end_utc"]); filings = choose_earnings_filing(recent_filings(js), target)
    if not filings: out.update({"revelation_state": "UNRESOLVED", "resolution_state": "UNRESOLVED", "adjudication_notes": "No SEC earnings-window filing candidate."}); return out
    slug = q.get("slug", "").lower(); wants_non_gaap = "nongaap" in slug or "non-gaap" in slug; wants_gaap = ("gaap" in slug and not wants_non_gaap); valid=[]
    for filing in filings:
        for name, doc_url in sec_doc_candidates(sec["cik"], filing, raw_manifest, q["event_id"]):
            b, dm = request_bytes(doc_url); raw_manifest.append({"event_id": q["event_id"], "endpoint": "sec_filing_document", "document_name": name, **dm})
            if b is None: continue
            low = html_text(b).lower()
            if not re.search(r"\b(eps|earnings per (?:diluted )?(?:common )?share|loss per (?:diluted )?(?:common )?share)\b", low): continue
            if not re.search(r"\b(quarter|three months|quarterly results)\b", low): continue
            if wants_non_gaap and not re.search(r"\b(non[- ]?gaap|adjusted|core)\b.{0,120}\b(eps|per share)\b|\b(eps|per share)\b.{0,120}\b(non[- ]?gaap|adjusted|core)\b", low): continue
            if wants_gaap and "gaap" not in low and not re.search(r"\bdiluted (?:earnings|loss) per (?:common )?share\b", low): continue
            if not re.search(r"\b(?:eps|earnings per (?:diluted )?(?:common )?share|loss per (?:diluted )?(?:common )?share)\b.{0,100}?\(?\s*-?\$?\d+(?:\.\d+)?", low): continue
            valid.append((filing, doc_url, dm.get("sha256", ""), filing.get("acceptanceDateTime", ""))); break
        if valid: break
    if not valid: out.update({"revelation_state": "UNRESOLVED", "resolution_state": "UNRESOLVED", "adjudication_notes": "SEC candidate found but metric/period/value evidence did not clear frozen objective checks."}); return out
    filing, doc_url, doc_sha, acc_time = valid[0]
    out.update({"resolution_state": "PASS", "resolution_source_type": f"SEC_EDGAR_{filing.get('form','')}", "resolution_source_url": doc_url, "resolution_response_sha256": doc_sha, "resolution_ambiguous": "false"})
    if acc_time:
        out.update({"revelation_state": "UNRESOLVED", "revelation_precision": "UNRESOLVED", "revelation_source_type": "SEC_ACCEPTANCE_CORROBORATION_ONLY", "revelation_source_url": doc_url, "revelation_response_sha256": doc_sha, "adjudication_notes": f"SEC acceptance corroborated at {sec_acceptance_to_utc(acc_time)}; earlier issuer-IR timestamp not independently resolved."})
    else: out.update({"revelation_state": "UNRESOLVED", "adjudication_notes": "SEC filing resolves EPS evidence; acceptance timestamp missing."})
    return out

def read_tsv_from_zip(z: zipfile.ZipFile, stem: str) -> list[dict]:
    names = {Path(n).name.lower(): n for n in z.namelist()}; candidates = [n for low,n in names.items() if low.startswith(stem.lower()) and low.endswith((".txt", ".tsv"))]
    if not candidates: return []
    return list(csv.DictReader(io.StringIO(z.read(sorted(candidates)[0]).decode("latin-1", "replace")), delimiter="\t"))

def load_fda(raw_manifest: list[dict]):
    b, meta = request_bytes(FDA_ZIP, attempts=5); raw_manifest.append({"scope": "GLOBAL", "endpoint": "drugs_at_fda_zip", **meta})
    if b is None: return None
    try:
        z=zipfile.ZipFile(io.BytesIO(b)); return {"products":read_tsv_from_zip(z,"Products"),"applications":read_tsv_from_zip(z,"Applications"),"submissions":read_tsv_from_zip(z,"Submissions"),"docs":read_tsv_from_zip(z,"ApplicationDocs"),"zip_sha256":sha256(b)}
    except Exception: return None

def extract_fda_subject(title: str) -> str:
    s=re.sub(r"^\s*FDA\s+approves?\s+", "", title or "", flags=re.I); s=re.sub(r"\?$", "", s).strip(); m=re.match(r"^.+?[’']s\s+(.+)$", s)
    return m.group(1) if m else s

def fda_match_products(title: str, fda: dict) -> list[dict]:
    subject=extract_fda_subject(title); st=tokens(subject)
    if not st: return []
    scored=[]
    for r in fda["products"]:
        tt=tokens(f"{r.get('DrugName','')} {r.get('ActiveIngredient','')}")
        if not tt: continue
        inter=len(st & tt); coverage=inter/max(1,min(len(st),len(tt))); exact=norm(subject) in {norm(r.get("DrugName","")),norm(r.get("ActiveIngredient",""))}
        if exact or (inter>=1 and coverage>=0.67): scored.append((1 if exact else 0,coverage,inter,r))
    scored.sort(key=lambda x:(-x[0],-x[1],-x[2],x[3].get("ApplNo",""))); return [x[-1] for x in scored[:8]]

def company_match(sponsor: str, companies: list[dict]):
    st=tokens(sponsor)
    if not st: return None
    cand=[]
    for c in companies:
        ct=c["title_tokens"]
        if not ct: continue
        inter=len(st&ct); union=len(st|ct); jac=inter/union if union else 0.0; coverage=inter/max(1,len(st))
        if inter>=1 and (jac>=0.62 or coverage>=0.8): cand.append((jac,coverage,inter,c))
    cand.sort(key=lambda x:(-x[0],-x[1],-x[2],x[3]["ticker"]))
    if not cand: return None
    best=cand[0]
    if len(cand)>1 and (best[0],best[1],best[2])==(cand[1][0],cand[1][1],cand[1][2]): return None
    return best[-1]

def fda_evidence(q: dict, fda: dict | None, companies: list[dict]) -> dict:
    if not fda: return {"revelation_state":"UNRESOLVED","resolution_state":"UNRESOLVED","linked_asset_mapping_state":"UNRESOLVED","adjudication_notes":"Drugs@FDA dataset unavailable."}
    matches=fda_match_products(q["title"],fda)
    if not matches: return {"revelation_state":"UNRESOLVED","resolution_state":"UNRESOLVED","linked_asset_mapping_state":"UNRESOLVED","adjudication_notes":"No deterministic Drugs@FDA product match; non-approval is not inferred."}
    applnos={str(r.get("ApplNo","")).strip() for r in matches}; target=parse_dt(q["semantic_end_utc"]).date(); apps={str(r.get("ApplNo","")).strip():r for r in fda["applications"] if str(r.get("ApplNo","")).strip() in applnos}; docs=[]
    for d in fda["docs"]:
        if str(d.get("ApplNo","")).strip() not in applnos or "approval" not in str(d.get("ApplicationDocsTitle","")).lower(): continue
        ds=str(d.get("ApplicationDocsDate",""))
        try: dd=datetime.fromisoformat(ds.replace("Z","+00:00")).date()
        except Exception:
            try: dd=datetime.strptime(ds[:10],"%Y-%m-%d").date()
            except Exception: continue
        delta=abs((dd-target).days)
        if delta<=45: docs.append((delta,dd,d))
    docs.sort(key=lambda x:(x[0],x[1],x[2].get("ApplNo","")))
    sponsors=sorted({str(apps[a].get("SponsorName","")).strip() for a in applnos if a in apps and str(apps[a].get("SponsorName","")).strip()}); mapped=[company_match(s,companies) for s in sponsors]; mapped=[x for x in mapped if x]; unique=sorted({x["ticker"] for x in mapped})
    asset={"linked_asset_mapping_state":"UNRESOLVED","linked_asset_mapping_source_url":FDA_ZIP}
    if len(unique)==1: asset={"linked_asset":unique[0],"linked_asset_mapping_state":"PASS","linked_asset_mapping_basis":"DRUGSATFDA_SPONSOR_TO_UNIQUE_SEC_ISSUER","linked_asset_mapping_source_url":FDA_ZIP}
    if not docs: return {**asset,"revelation_state":"UNRESOLVED","resolution_state":"UNRESOLVED","adjudication_notes":"Drug/sponsor match exists, but no nearby official approval document; no CRL/non-approval inference."}
    _,dd,d=docs[0]; reveal,cutoff=date_conservative(dd.isoformat(),ET); url=str(d.get("ApplicationDocsURL","")) or FDA_ZIP
    return {**asset,"revelation_state":"PASS","public_revelation_utc":reveal,"safe_cutoff_utc":cutoff,"revelation_precision":"DATE_CONSERVATIVE","revelation_source_type":"FDA_DRUGSATFDA_APPROVAL_DOCUMENT","revelation_source_url":url,"revelation_response_sha256":fda["zip_sha256"],"resolution_state":"PASS","resolution_source_type":"FDA_DRUGSATFDA_APPROVAL_DOCUMENT","resolution_source_url":url,"resolution_response_sha256":fda["zip_sha256"],"resolution_ambiguous":"false","adjudication_notes":"Positive FDA approval supported by Drugs@FDA approval document; date-conservative cutoff."}

def macro_kind(q: dict) -> str:
    s=norm(q.get("title",""))
    if q.get("primary_source_route")=="BLS":
        if "producer price" in s or re.search(r"\bppi\b",s): return "BLS_PPI"
        if "unemployment" in s or "jobs" in s or "payroll" in s or "employment" in s: return "BLS_EMPSIT"
        return "BLS_CPI"
    if q.get("primary_source_route")=="BEA": return "BEA_GDP"
    return q.get("primary_source_route","UNRESOLVED")

def parse_bls_release_timestamp(text: str, fallback_date) -> tuple[str,str,str]:
    m=re.search(r"(?:embargoed until|for release)\s+(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?).{0,80}?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})",text,re.I)
    if m:
        hour=int(m.group(1)); minute=int(m.group(2)); ap=m.group(3).lower()
        if "p" in ap and hour!=12: hour+=12
        if "a" in ap and hour==12: hour=0
        d=datetime.strptime(f"{m.group(4)} {m.group(5)} {m.group(6)}","%B %d %Y").date(); reveal=datetime(d.year,d.month,d.day,hour,minute,tzinfo=ET)
        return iso(reveal),iso(reveal-timedelta(seconds=1)),"MINUTE"
    reveal,cutoff=date_conservative(fallback_date.isoformat(),ET); return reveal,cutoff,"DATE_CONSERVATIVE"

def bls_evidence(q: dict, raw_manifest: list[dict]) -> dict:
    kind=macro_kind(q)
    if kind not in BLS_PATTERNS: return {"revelation_state":"UNRESOLVED","resolution_state":"UNRESOLVED","adjudication_notes":"Not a frozen BLS series route."}
    prefix,cues=BLS_PATTERNS[kind]; target=parse_dt(q["semantic_end_utc"]).date(); found=[]
    for delta in range(-10,11):
        d=target+timedelta(days=delta); url=f"https://www.bls.gov/news.release/archives/{prefix}_{d.strftime('%m%d%Y')}.htm"; b,meta=request_bytes(url,attempts=2); raw_manifest.append({"event_id":q["event_id"],"endpoint":f"bls_{prefix}_archive",**meta})
        if b is None: continue
        text=html_text(b); low=text.lower()
        if any(cue in low for cue in cues): found.append((abs(delta),d,url,b,text,meta))
    if not found: return {"revelation_state":"UNRESOLVED","resolution_state":"UNRESOLVED","adjudication_notes":"No exact BLS archive page found within frozen ±10-day window."}
    found.sort(key=lambda x:(x[0],x[1])); _,d,url,b,text,meta=found[0]; reveal,cutoff,precision=parse_bls_release_timestamp(text,d)
    return {"revelation_state":"PASS","public_revelation_utc":reveal,"safe_cutoff_utc":cutoff,"revelation_precision":precision,"revelation_source_type":kind,"revelation_source_url":url,"revelation_response_sha256":meta.get("sha256",""),"resolution_state":"PASS","resolution_source_type":kind,"resolution_source_url":url,"resolution_response_sha256":meta.get("sha256",""),"resolution_ambiguous":"false","adjudication_notes":"Official BLS archived release matched frozen series route."}

def bea_evidence(q: dict, raw_manifest: list[dict]) -> dict:
    target=parse_dt(q["semantic_end_utc"]); year=target.year; m=re.search(r"Q([1-4])\s*(20\d{2})",q.get("title",""),re.I)
    if not m: return {"revelation_state":"UNRESOLVED","resolution_state":"UNRESOLVED","adjudication_notes":"BEA quarter/year could not be parsed exactly."}
    quarter,ref_year=m.group(1),m.group(2); url="https://www.bea.gov/news/archive?"+urllib.parse.urlencode({"created_1":str(year),"field_related_product_target_id":"456","page":"0","title":""}); b,meta=request_bytes(url); raw_manifest.append({"event_id":q["event_id"],"endpoint":"bea_gdp_archive",**meta})
    if b is None: return {"revelation_state":"UNRESOLVED","resolution_state":"UNRESOLVED","adjudication_notes":"BEA archive unavailable."}
    text=html_text(b)
    if not (re.search(rf"{quarter}(?:st|nd|rd|th)?\s+Quarter\s+{ref_year}",text,re.I) or re.search(rf"{quarter}\s*Quarter\s+{ref_year}",text,re.I)): return {"revelation_state":"UNRESOLVED","resolution_state":"UNRESOLVED","adjudication_notes":"BEA archive did not verify exact quarter/year."}
    return {"revelation_state":"UNRESOLVED","resolution_state":"PASS","resolution_source_type":"BEA_GDP_ARCHIVE","resolution_source_url":url,"resolution_response_sha256":meta.get("sha256",""),"resolution_ambiguous":"false","adjudication_notes":"BEA archive verifies exact GDP release family/period; exact authoritative timestamp unresolved in automated pass."}

def macro_evidence(q: dict, raw_manifest: list[dict]) -> dict:
    route=q.get("primary_source_route","")
    if route=="BLS": return bls_evidence(q,raw_manifest)
    if route=="BEA": return bea_evidence(q,raw_manifest)
    return {"revelation_state":"UNRESOLVED","resolution_state":"UNRESOLVED","adjudication_notes":f"Frozen official route {route or 'UNRESOLVED'} has no exact-series automated resolver in v2.1; no U.S./nearby-series fallback."}

def yahoo_availability(symbol: str, event_dt: datetime, event_id: str, raw_manifest: list[dict]) -> dict:
    if not symbol: return {"asset_data_state":"UNRESOLVED"}
    start=event_dt-timedelta(days=75); end=min(ASOF,event_dt+timedelta(days=35))
    if end<=start: return {"asset_data_state":"UNRESOLVED"}
    q=urllib.parse.urlencode({"period1":int(start.timestamp()),"period2":int((end+timedelta(days=1)).timestamp()),"interval":"1d","events":"history","includeAdjustedClose":"true"}); url=YAHOO_CHART.format(symbol=urllib.parse.quote(symbol))+"?"+q; js,meta=request_json(url); raw_manifest.append({"event_id":event_id,"endpoint":"yahoo_chart_v8_availability","symbol":symbol,**meta})
    if not isinstance(js,dict): return {"asset_data_state":"UNRESOLVED"}
    try: ts=[int(x) for x in (js["chart"]["result"][0].get("timestamp") or [])]
    except Exception: ts=[]
    if not ts: return {"asset_data_state":"FAIL","asset_data_response_sha256":meta.get("sha256",""),"asset_data_rows":"0"}
    dates=[datetime.fromtimestamp(x,timezone.utc).date().isoformat() for x in ts]
    return {"asset_data_state":"PASS","asset_data_first_date":min(dates),"asset_data_last_date":max(dates),"asset_data_rows":str(len(ts)),"asset_data_response_sha256":meta.get("sha256","")}

def main():
    p=json.loads(PROTOCOL.read_text()); assert p["version"]=="W2C-PIT-v2.1" and p["performance_blind"] is True; rows=load_queue(); raw_manifest=[]; ticker_map,companies=sec_ticker_map(raw_manifest); fda=load_fda(raw_manifest); out=[]
    for i,q in enumerate(rows,1):
        r=dict(q); due=q["asof_state"]=="DUE_ASOF"
        if not due:
            r.update({"revelation_state":"RIGHT_CENSORED_ASOF","resolution_state":"RIGHT_CENSORED_ASOF","asset_data_state":"RIGHT_CENSORED_ASOF"}); out.append(r); continue
        fam=q["resolved_family"]
        if fam=="EARNINGS_EPS": ev=earnings_evidence(q,ticker_map,raw_manifest)
        elif fam=="FDA_FINAL_PDUFA_DECISION": ev=fda_evidence(q,fda,companies)
        else: ev=macro_evidence(q,raw_manifest)
        r.update(ev)
        if not (r.get("revelation_state")=="PASS" and r.get("safe_cutoff_utc")):
            r["safe_cutoff_utc"]=""
            if r.get("revelation_state")!="RIGHT_CENSORED_ASOF": r["revelation_state"]="UNRESOLVED"
        symbol=r.get("linked_asset","")
        if r.get("linked_asset_mapping_state")=="PASS" and symbol: r.update(yahoo_availability(symbol,parse_dt(q["semantic_end_utc"]),q["event_id"],raw_manifest))
        else: r["asset_data_state"]="UNRESOLVED"
        out.append(r)
        if i%20==0: print(f"primary-asset {i}/{len(rows)}",flush=True)
    write_gz_csv(OUT,out); write_jsonl_gz(RAW,raw_manifest); fam=defaultdict(Counter)
    for r in out:
        f=r["resolved_family"]; fam[f]["n"]+=1; fam[f][f"revelation_{r.get('revelation_state','')}"]+=1; fam[f][f"resolution_{r.get('resolution_state','')}"]+=1; fam[f][f"assetmap_{r.get('linked_asset_mapping_state','')}"]+=1; fam[f][f"assetdata_{r.get('asset_data_state','')}"]+=1
    summary={"artifact":"W2C_PIT_V2_1_PRIMARY_ASSET_MATERIALIZATION","version":VERSION,"protocol":p["version"],"rows":len(out),"family_summary":{k:dict(v) for k,v in sorted(fam.items())},"request_records":len(raw_manifest),"unique_request_keys":len(HTTP_CACHE),"cache_hits":sum(bool(r.get("cache_hit")) for r in raw_manifest),"performance_blind":True,"science_reopened":False,"f1_f9_scored":False,"ias_computed":False,"smaa_computed":False,"w3_selected":False,"linked_asset_movement_values_persisted":False}; SUMMARY.write_text(json.dumps(summary,indent=2)+"\n"); print(json.dumps(summary,indent=2))

if __name__=="__main__": main()

#!/usr/bin/env python3
"""W2-C performance-blind Polymarket discovery under W2C-DISC-v1.0.

Reads only the frozen discovery protocol and official public Polymarket Gamma
metadata. It MUST NOT read ARGOS model/economic performance, linked-asset
realized returns, Brier/log loss, or H2/R1/R3 performance.

Outputs are discovery candidates and a manual-validation queue. They are not
IAS scores and do not pass/fail feasibility gates.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, math, re, time
import urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://gamma-api.polymarket.com"
USER_AGENT = "ARGOS-W2C-Discovery/1.0 (+research; public Gamma API)"
EXPECTED_PROTOCOL_VERSION = "W2C-DISC-v1.0"
EXPECTED_PARENT_FREEZE = "W2PF-v1.0"

PATTERNS = {
"EARNINGS_EPS":[r"\bearnings\b",r"\beps\b",r"earnings per share"],
"FDA_ADVISORY_COMMITTEE":[r"\bfda\b.*\b(advisory|adcom|panel)\b",r"\b(advisory committee|adcom)\b.*\b(fda|drug|biologic)"],
"FDA_FINAL_PDUFA_DECISION":[r"\bpdufa\b",r"\bfda\b.*\b(approval|approve|decision|action date)\b",r"\bdrug approval\b"],
"MA_PRE_ANNOUNCEMENT_OR_RUMOR":[r"\b(merger|acquisition|acquire|takeover|buyout)\b.*\b(rumou?r|announce|announcement|bid|offer)\b",r"\b(rumou?r|announce|announcement)\b.*\b(merger|acquisition|takeover|buyout)\b"],
"MA_PENDING_COMPLETION":[r"\b(merger|acquisition|deal|takeover|buyout)\b.*\b(close|closing|completion|complete|shareholder vote|tender offer|outside date|terminate|termination)\b",r"\b(close|closing|completion|shareholder vote|tender offer|outside date)\b.*\b(merger|acquisition|deal)\b"],
"MA_REGULATORY_CLEARANCE":[r"\b(merger|acquisition|deal)\b.*\b(ftc|doj|cma|european commission|antitrust|regulatory|competition)\b.*\b(approve|approval|clearance|clear|block|challenge)\b",r"\b(ftc|doj|cma|european commission|antitrust|regulatory|competition)\b.*\b(merger|acquisition|deal)\b"],
"ANTITRUST_ENFORCEMENT_SINGLE_NAME":[r"\b(antitrust|ftc|doj|competition regulator|monopoly)\b.*\b(lawsuit|sue|trial|case|ruling|fine|settlement|investigation|enforcement)\b",r"\b(lawsuit|trial|ruling|settlement)\b.*\b(antitrust|ftc|doj|monopoly)\b"],
"FOMC_DECISION":[r"\bfomc\b",r"\bfederal reserve\b.*\b(rate|decision|cut|hike|hold)\b",r"\bfed\b.*\b(rate cut|rate hike|rate decision)\b"],
"MACRO_STATISTICAL_RELEASE":[r"\bcpi\b",r"consumer price index",r"\bnonfarm payrolls?\b",r"\bjobs report\b",r"\bgdp\b",r"\bppi\b",r"\bretail sales\b",r"\bunemployment rate\b"],
"CORPORATE_LITIGATION_BINARY":[r"\b(company|corporate|inc\.?|corp\.?|llc)\b.*\b(court|lawsuit|verdict|injunction|settlement|ruling)\b",r"\b(court ruling|lawsuit settlement|injunction|verdict)\b.*\b(company|corporate|inc\.?|corp\.?)\b"]
}
COMPILED = {k:[re.compile(x,re.I|re.S) for x in v] for k,v in PATTERNS.items()}

def fetch_json(path, params=None, retries=6):
    url=BASE+path
    if params: url += "?" + urllib.parse.urlencode(params, doseq=True)
    req=urllib.request.Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    for a in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=45) as r: return json.loads(r.read().decode("utf-8"))
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError):
            if a==retries-1: raise
            time.sleep(min(2**a,20))
    raise RuntimeError("unreachable")

def parse_dt(v):
    if not v:return None
    s=str(v).strip()
    try:
        if s.endswith("Z"):s=s[:-1]+"+00:00"
        d=datetime.fromisoformat(s)
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except ValueError:return None

def as_float(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def event_text(e):
    bits=[]
    for k in ("title","subtitle","description","slug","category","subcategory","resolutionSource"):
        if e.get(k):bits.append(str(e[k]))
    for t in e.get("tags") or []:
        if isinstance(t,dict):bits += [str(t.get("label") or ""),str(t.get("slug") or "")]
    for s in e.get("series") or []:
        if isinstance(s,dict):bits += [str(s.get("title") or ""),str(s.get("slug") or ""),str(s.get("description") or "")]
    for m in e.get("markets") or []:
        if isinstance(m,dict):
            for k in ("question","slug","description","category","resolutionSource"):
                if m.get(k):bits.append(str(m[k]))
    return " \n ".join(bits)

def classify(e):
    text=event_text(e)
    return {f for f,ps in COMPILED.items() if any(p.search(text) for p in ps)}

def deterministic_gzip(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("wb") as fh:
        with gzip.GzipFile(filename="",mode="wb",fileobj=fh,mtime=0) as gz: gz.write(payload)

def write_csv(path,rows,fields,gzip_out=False):
    sio=io.StringIO(newline=""); w=csv.DictWriter(sio,fieldnames=fields); w.writeheader(); w.writerows(rows)
    data=sio.getvalue().encode()
    if gzip_out: deterministic_gzip(path,data)
    else: path.write_bytes(data)

def keyset(params,max_pages):
    out=[]; seen=set(); cursor=None
    for _ in range(max_pages):
        q=dict(params)
        if cursor:q["after_cursor"]=cursor
        payload=fetch_json("/events/keyset",q); batch=payload.get("events") or []
        for e in batch:
            eid=str(e.get("id") or "")
            if eid and eid not in seen:seen.add(eid);out.append(e)
        nxt=payload.get("next_cursor")
        if not batch or not nxt:break
        if nxt==cursor: raise RuntimeError("non-advancing keyset cursor")
        cursor=nxt
    else: raise RuntimeError(f"keyset exceeded max_pages={max_pages}")
    return out

def list_series(limit,max_pages):
    out=[]
    for page in range(max_pages):
        batch=fetch_json("/series",{"limit":limit,"offset":page*limit}) or []
        if not isinstance(batch,list): raise RuntimeError("unexpected /series response")
        out.extend(batch)
        if len(batch)<limit:break
    else: raise RuntimeError("series pagination bound exceeded")
    return out

def public_search(q,limit,max_pages):
    events=[]; tags=[]; seen_e=set(); seen_t=set()
    for page in range(1,max_pages+1):
        payload=fetch_json("/public-search",{"q":q,"events_status":"closed","limit_per_type":limit,"page":page,"keep_closed_markets":1,"search_tags":"true","search_profiles":"false"})
        for e in payload.get("events") or []:
            eid=str(e.get("id") or "")
            if eid and eid not in seen_e:seen_e.add(eid);events.append(e)
        for t in payload.get("tags") or []:
            slug=str(t.get("slug") or "")
            if slug and slug not in seen_t:seen_t.add(slug);tags.append(t)
        if not (payload.get("pagination") or {}).get("hasMore"):break
    else: raise RuntimeError(f"public-search exceeded max pages for {q!r}")
    return events,tags

def norm(s): return re.sub(r"[^a-z0-9]+"," ",str(s).lower()).strip()
def series_matches(series,queries):
    blob=norm(" ".join(str(series.get(k) or "") for k in ("title","slug","subtitle","description")))
    return any(norm(q) in blob for q in queries if len(norm(q))>=3)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--protocol",default="registry/w2c_discovery_protocol.json"); ap.add_argument("--registry-dir",default="registry"); args=ap.parse_args()
    protocol=json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    assert protocol["version"]==EXPECTED_PROTOCOL_VERSION and protocol["parent_freeze"]==EXPECTED_PARENT_FREEZE and protocol["performance_blind"] is True
    registry=Path(args.registry_dir);registry.mkdir(parents=True,exist_ok=True); snap=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    pag=protocol["pagination"]; qmap=protocol["query_map"]
    event_by_id={}; channels=defaultdict(set); queries_by=defaultdict(set); targeted=defaultdict(set); audit=[]

    broad=keyset({"limit":pag["keyset_limit"],"closed":"true","order":"createdAt","ascending":"true"},pag["keyset_max_pages"])
    for e in broad:
        eid=str(e.get("id") or "")
        if not eid:continue
        event_by_id.setdefault(eid,e)
        for fam in classify(e): channels[(eid,fam)].add("FULL_CLOSED_EVENT_KEYSET_CRAWL")
    audit.append({"channel":"FULL_CLOSED_EVENT_KEYSET_CRAWL","family":"*","query":"*","returned_events":len(broad),"returned_tags":0})

    discovered_tag_slugs=defaultdict(set)
    for fam,queries in qmap.items():
        for q in queries:
            evs=keyset({"limit":pag["keyset_limit"],"closed":"true","order":"createdAt","ascending":"true","title_search":q},pag["keyset_max_pages"])
            for e in evs:
                eid=str(e.get("id") or "")
                if eid:event_by_id.setdefault(eid,e);channels[(eid,fam)].add("FROZEN_TITLE_SEARCH_KEYSET");queries_by[(eid,fam)].add(q);targeted[eid].add(fam)
            audit.append({"channel":"FROZEN_TITLE_SEARCH_KEYSET","family":fam,"query":q,"returned_events":len(evs),"returned_tags":0})
            sev,stags=public_search(q,pag["public_search_limit_per_type"],pag["public_search_max_pages"])
            for e in sev:
                eid=str(e.get("id") or "")
                if eid:event_by_id.setdefault(eid,e);channels[(eid,fam)].add("FROZEN_PUBLIC_SEARCH");queries_by[(eid,fam)].add(q);targeted[eid].add(fam)
            slugs=sorted({str(t.get("slug") or "") for t in stags if t.get("slug")})[:pag["tag_slugs_per_query_max"]]
            discovered_tag_slugs[fam].update(slugs)
            audit.append({"channel":"FROZEN_PUBLIC_SEARCH","family":fam,"query":q,"returned_events":len(sev),"returned_tags":len(stags)})

    for fam,slugs in discovered_tag_slugs.items():
        for slug in sorted(slugs):
            evs=keyset({"limit":pag["keyset_limit"],"closed":"true","tag_slug":slug,"related_tags":"true","order":"createdAt","ascending":"true"},pag["keyset_max_pages"])
            for e in evs:
                eid=str(e.get("id") or "")
                if eid:event_by_id.setdefault(eid,e);channels[(eid,fam)].add("PUBLIC_SEARCH_TAG_TO_RELATED_TAG_EVENT_EXPANSION");queries_by[(eid,fam)].add("tag:"+slug);targeted[eid].add(fam)
            audit.append({"channel":"PUBLIC_SEARCH_TAG_TO_RELATED_TAG_EVENT_EXPANSION","family":fam,"query":"tag:"+slug,"returned_events":len(evs),"returned_tags":0})

    all_series=list_series(pag["series_limit"],pag["series_max_pages"])
    for fam,queries in qmap.items():
        for s in [x for x in all_series if series_matches(x,queries)]:
            sid=str(s.get("id") or "")
            if not sid:continue
            evs=keyset({"limit":pag["keyset_limit"],"closed":"true","series_id":sid,"order":"createdAt","ascending":"true"},pag["keyset_max_pages"])
            for e in evs:
                eid=str(e.get("id") or "")
                if eid:event_by_id.setdefault(eid,e);channels[(eid,fam)].add("FROZEN_TERM_MATCHED_SERIES_TO_EVENT_EXPANSION");queries_by[(eid,fam)].add("series:"+sid);targeted[eid].add(fam)
            audit.append({"channel":"FROZEN_TERM_MATCHED_SERIES_TO_EVENT_EXPANSION","family":fam,"query":"series:"+sid,"returned_events":len(evs),"returned_tags":0})

    rows=[];byfam=defaultdict(list)
    for eid,e in event_by_id.items():
        classified=classify(e); fams=classified | targeted.get(eid,set())
        start=parse_dt(e.get("startDate") or e.get("creationDate") or e.get("createdAt")); end=parse_dt(e.get("endDate") or e.get("closedTime")); lead_h=(end-start).total_seconds()/3600 if start and end and end>=start else None
        vol=as_float(e.get("volume")); liq=as_float(e.get("liquidity")); tags=sorted({str(t.get("slug") or t.get("label") or "") for t in e.get("tags") or [] if isinstance(t,dict)}); series=sorted({str(s.get("id") or "") for s in e.get("series") or [] if isinstance(s,dict) and s.get("id")})
        for fam in sorted(fams):
            if fam not in qmap:continue
            r={"family":fam,"event_id":eid,"title":str(e.get("title") or ""),"slug":str(e.get("slug") or ""),"start_utc":start.isoformat().replace("+00:00","Z") if start else "","end_utc":end.isoformat().replace("+00:00","Z") if end else "","lead_hours":"" if lead_h is None else f"{lead_h:.6f}","lifetime_volume":"" if vol is None else f"{vol:.6f}","liquidity_snapshot":"" if liq is None else f"{liq:.6f}","market_count":len(e.get("markets") or []),"resolution_source":str(e.get("resolutionSource") or ""),"tags":"|".join(tags),"series_ids":"|".join(series),"discovery_channels":"|".join(sorted(channels.get((eid,fam),{"STRUCTURAL_CLASSIFIER_FROM_BROAD_CRAWL"}))),"queries_matched":"|".join(sorted(queries_by.get((eid,fam),set()))),"classifier_match":str(fam in classified).lower(),"manual_validation_status":"PENDING","ias_score_authorized":"false"}
            rows.append(r);byfam[fam].append(r)
    rows.sort(key=lambda r:(r["family"],r["start_utc"],r["event_id"])); fields=list(rows[0]) if rows else ["family","event_id"]
    events_path=registry/"w2c_discovery_events.csv.gz";write_csv(events_path,rows,fields,True); queue_path=registry/"w2c_discovery_validation_queue.csv.gz";write_csv(queue_path,rows,fields,True)
    summaries=[]
    for fam in qmap:
        rs=byfam.get(fam,[]); leads=[float(r["lead_hours"]) for r in rs if r["lead_hours"]]; vols=[float(r["lifetime_volume"]) for r in rs if r["lifetime_volume"]]
        summaries.append({"family":fam,"candidate_events":len({r["event_id"] for r in rs}),"events_with_lead_hours":len(leads),"lead_hours_median":sorted(leads)[len(leads)//2] if leads else "","lead_ge_24h_count":sum(x>=24 for x in leads),"lead_ge_24h_rate_unvalidated":(sum(x>=24 for x in leads)/len(leads)) if leads else "","events_with_volume":len(vols),"volume_ge_1k":sum(x>=1000 for x in vols),"volume_ge_10k":sum(x>=10000 for x in vols),"volume_ge_100k":sum(x>=100000 for x in vols),"manual_validation_required":"true","feasibility_gate_status":"NOT_SCORED"})
    summary_path=registry/"w2c_discovery_summary.csv";write_csv(summary_path,summaries,list(summaries[0])); audit.sort(key=lambda r:(r["family"],r["channel"],r["query"])); audit_path=registry/"w2c_discovery_query_audit.csv";write_csv(audit_path,audit,["channel","family","query","returned_events","returned_tags"])
    meta={"artifact":"W2C_PERFORMANCE_BLIND_DISCOVERY_RUN","version":"W2C-DISC-RUN-v1.0","snapshot_utc":snap,"protocol_version":protocol["version"],"protocol_sha256":hashlib.sha256(Path(args.protocol).read_bytes()).hexdigest(),"parent_freeze":EXPECTED_PARENT_FREEZE,"performance_blind":True,"science_reopened":False,"argos_performance_read":False,"realized_linked_asset_returns_read":False,"ias_scores_computed":False,"feasibility_gates_scored":False,"w3_family_selected":False,"source":"official Polymarket Gamma API","total_closed_events_broad_crawl":len(broad),"unique_events_seen_all_channels":len(event_by_id),"candidate_rows":len(rows),"families":summaries,"files":{"events":{"path":str(events_path),"sha256":hashlib.sha256(events_path.read_bytes()).hexdigest()},"validation_queue":{"path":str(queue_path),"sha256":hashlib.sha256(queue_path.read_bytes()).hexdigest()},"summary":{"path":str(summary_path),"sha256":hashlib.sha256(summary_path.read_bytes()).hexdigest()},"query_audit":{"path":str(audit_path),"sha256":hashlib.sha256(audit_path.read_bytes()).hexdigest()}},"interpretation":"Discovery candidates only. No family is validated, IAS-scored, feasibility-passed, or selected for W3.","limitations":["Current Gamma metadata can reflect post-close taxonomy/metadata edits.","start/creation-to-end lead is not proof of pre-material-news availability or first trade time.","lifetime volume and current liquidity metadata are not PIT liquidity at a frozen cutoff.","targeted search and regex nomination can create false positives/false negatives; manual validation is mandatory.","zero/low candidate counts are not evidence of zero asymmetry or family absence."]}
    (registry/"w2c_discovery_summary.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print(json.dumps(meta,indent=2,ensure_ascii=False))
if __name__=="__main__": main()

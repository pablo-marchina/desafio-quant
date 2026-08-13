#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
BASE = "https://external-api.kalshi.com/trade-api/v2"
UA = "ARGOS-W4B-semantic/1.1"
PROTO = json.loads((REG / "w4b_semantic_canonicalization_protocol_v1.json").read_text())
AMEND = json.loads((REG / "w4b_semantic_completeness_amendment_v1_1.json").read_text())
RAW = json.loads((REG / "w4_kalshi_series_first_capacity_v1.json").read_text())
BER = json.loads((REG / "w4_backtest_expansion_research_protocol_v1.json").read_text())
FROZEN = BER["frozen_family_dictionary"]
RULES = PROTO["family_rules"]

MACRO_SUBJECTS = {
    "CPI_INFLATION_RELEASE": "US_CPI",
    "PAYROLLS_JOBS_RELEASE": "US_PAYROLLS",
    "GDP_RELEASE": "US_GDP",
    "PCE_RELEASE": "US_PCE",
    "RETAIL_SALES_RELEASE": "US_RETAIL_SALES",
    "FOMC_DECISION": "US_FOMC",
}
GENERIC_WORDS = {
    "will","would","the","a","an","be","is","are","was","were","to","of","for","in","on","by",
    "above","below","at","least","more","less","than","between","before","after","during","this",
    "report","release","decision","market","yes","no","occur","happen","rate","value","number",
    "quarterly","results","result","probability","chance","reach","exceed","under","over"
}
FAMILY_DROP = {
    "EARNINGS_EPS":{"earnings","eps","share","quarterly","beat","miss","report","revenue"},
    "FDA_FINAL_PDUFA_DECISION":{"fda","food","drug","administration","pdufa","approve","approval","approved","decision","action","date","crl","response","letter"},
    "FDA_ADVISORY_COMMITTEE":{"fda","food","drug","administration","advisory","committee","adcom","panel","vote"},
    "MA_PRE_ANNOUNCEMENT_OR_RUMOR":{"merger","acquisition","acquire","takeover","buyout","announce","announcement","rumor","rumour","bid","offer"},
    "MA_PENDING_COMPLETION":{"merger","acquisition","takeover","transaction","deal","close","closing","complete","completion"},
    "MA_REGULATORY_CLEARANCE":{"merger","acquisition","takeover","transaction","deal","regulatory","approval","clearance","clear","approve","ftc","doj","antitrust"},
    "ANTITRUST_ENFORCEMENT_SINGLE_NAME":{"antitrust","ftc","doj","competition","authority","regulator","lawsuit","case","enforcement"},
    "CORPORATE_LITIGATION_BINARY":{"lawsuit","litigation","court","ruling","decision","verdict","injunction","settlement","appeal"},
}

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%+.-]+", " ", (s or "").lower())).strip()

def phrase_hit(text: str, phrase: str) -> bool:
    p = norm(phrase)
    if not p:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(p).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return re.search(pattern, norm(text)) is not None

def boundary_candidates(text: str) -> list[str]:
    return sorted(fam for fam, kws in FROZEN.items() if any(phrase_hit(text, kw) for kw in kws))

def rule_pass(text: str, rule: dict) -> bool:
    t = norm(text)
    if any(re.search(p, t, flags=re.I) for p in rule.get("hard_exclude", [])):
        return False
    req_all = rule.get("require_all", [])
    if req_all and not all(re.search(p, t, flags=re.I) for p in req_all):
        return False
    req_any = rule.get("require_any", [])
    if req_any and not any(re.search(p, t, flags=re.I) for p in req_any):
        return False
    return bool(req_all or req_any)

def strict_families(text: str) -> list[str]:
    return sorted(fam for fam, rule in RULES.items() if rule_pass(text, rule))

def resolve_family(passes: list[str]) -> tuple[str | None, str]:
    if len(passes) == 1:
        return passes[0], "ACCEPT_STRICT_FAMILY"
    if not passes:
        return None, "REJECT_FALSE_POSITIVE"
    ps = set(passes)
    for chain in PROTO["precedence"]["same_mechanism"]:
        chain_hits = [f for f in chain if f in ps]
        if len(chain_hits) == len(ps) and chain_hits:
            return chain_hits[0], "ACCEPT_STRICT_PRECEDENCE"
    return None, "AMBIGUOUS_MULTI_FAMILY"

def get_json(url: str, retries: int = 5):
    last = None
    for i in range(retries):
        try:
            with urlopen(Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=45) as r:
                return json.loads(r.read().decode()), None
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode(errors="replace")[:500]
            except Exception:
                pass
            last = {"status": e.code, "error": body or str(e), "url": url}
            if 400 <= e.code < 500 and e.code != 429:
                return None, last
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            last = {"status": None, "error": str(e), "url": url}
        if i + 1 < retries:
            time.sleep(1.0 * (i + 1))
    return None, last or {"status": None, "error": "unknown", "url": url}

def paged_markets(path: str, q: dict, max_pages: int = 500):
    cursor = ""
    rows = []
    pages = 0
    while pages < max_pages:
        qq = dict(q)
        if cursor:
            qq["cursor"] = cursor
        obj, err = get_json(BASE + path + "?" + urlencode(qq))
        if err:
            return rows, pages, False, err
        batch = obj.get("markets", [])
        rows.extend(batch)
        pages += 1
        cursor = obj.get("cursor") or ""
        if not cursor or not batch:
            return rows, pages, False, None
    return rows, pages, bool(cursor), None

def is_mve(m: dict) -> bool:
    return bool(m.get("mve_collection_ticker") or m.get("mve_selected_legs"))

def text_fields_for_event(series_row: dict, markets: list[dict]) -> str:
    parts = [series_row.get("series_title",""), series_row.get("category","")]
    for m in markets:
        for k in ("title","subtitle","yes_sub_title","no_sub_title"):
            if m.get(k):
                parts.append(str(m[k]))
    return " ".join(parts)

def event_reference_date(markets: list[dict]) -> tuple[str | None, str | None]:
    vals = []
    for m in markets:
        for k in ("occurrence_datetime","close_time"):
            v = m.get(k)
            if not v:
                continue
            try:
                dt = datetime.fromisoformat(str(v).replace("Z","+00:00"))
                vals.append((0 if k == "occurrence_datetime" else 1, dt, k))
            except Exception:
                pass
    if not vals:
        return None, None
    best_priority = min(x[0] for x in vals)
    eligible = sorted((dt,k) for p,dt,k in vals if p == best_priority)
    dt,k = eligible[0]
    return dt.astimezone(timezone.utc).date().isoformat(), k

def unemployment_subject(text: str) -> str:
    t = norm(text)
    if re.search(r"\b(initial jobless claims|jobless claims|initial claims)\b", t):
        return "US_INITIAL_JOBLESS_CLAIMS"
    return "US_UNEMPLOYMENT_RATE"

def subject_key(family: str, text: str) -> str:
    if family in MACRO_SUBJECTS:
        return MACRO_SUBJECTS[family]
    if family == "UNEMPLOYMENT_RELEASE":
        return unemployment_subject(text)
    t = norm(text)
    t = re.sub(r"\b\d+(?:\.\d+)?%?\b", " ", t)
    months = r"january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
    t = re.sub(rf"\b({months})\b", " ", t)
    drop = GENERIC_WORDS | FAMILY_DROP.get(family, set())
    toks = [x for x in re.findall(r"[a-z0-9]+", t) if x not in drop and len(x) > 1]
    seen = set(); kept = []
    for tok in toks:
        if tok not in seen:
            seen.add(tok); kept.append(tok)
    return "_".join(kept[:18])

def canonical_id(family: str, date_key: str, subject: str) -> str:
    raw = f"{family}|{date_key}|{subject}".encode()
    return "W4CE1-" + hashlib.sha256(raw).hexdigest()[:20]

def write_csv_gz(path: Path, rows: list[dict], fieldnames: list[str]):
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k:r.get(k,"") for k in fieldnames})

def main():
    raw_rows = RAW.get("selected_series", [])
    by_series = {}; raw_families = defaultdict(set)
    for r in raw_rows:
        st = r.get("series_ticker")
        if not st:
            continue
        by_series.setdefault(st, {
            "series_ticker":st,
            "series_title":r.get("series_title",""),
            "category":r.get("category",""),
            "frequency":r.get("frequency",""),
        })
        if r.get("family"):
            raw_families[st].add(r["family"])

    series_rows = []; event_rows = []; ambiguous = []; api_errors = []; route_truncations = []; candidate_series = []
    for st in sorted(by_series):
        s = by_series[st]
        b_hits = boundary_candidates(" ".join([s["series_title"], s["category"]]))
        candidate_series.append(st)
        series_rows.append({
            **s,
            "raw_family_hits":"|".join(sorted(raw_families[st])),
            "boundary_family_hits":"|".join(b_hits),
            "boundary_candidate":"YES" if b_hits else "NO",
        })

    for idx, st in enumerate(candidate_series, 1):
        s = by_series[st]
        hist, hp, ht, he = paged_markets("/historical/markets", {"limit":1000,"series_ticker":st})
        live, lp, lt, le = paged_markets("/markets", {"limit":1000,"series_ticker":st,"status":"settled"})
        for route, err in (("historical",he),("live",le)):
            if err:
                api_errors.append({"series_ticker":st,"route":route,**err})
        if ht:
            route_truncations.append({"series_ticker":st,"route":"historical","pages":hp})
        if lt:
            route_truncations.append({"series_ticker":st,"route":"live","pages":lp})
        market_map = {}; route_by_ticker = defaultdict(set)
        for route, rows in (("historical",hist),("live",live)):
            for m in rows:
                if is_mve(m) or not m.get("ticker") or not m.get("event_ticker"):
                    continue
                market_map[m["ticker"]] = m
                route_by_ticker[m["ticker"]].add(route)
        by_event = defaultdict(list)
        for m in market_map.values():
            by_event[m["event_ticker"]].append(m)

        for event_ticker, markets in sorted(by_event.items()):
            text = text_fields_for_event(s, markets)
            passes = strict_families(text)
            fam, semantic_status = resolve_family(passes)
            date_key, date_source = event_reference_date(markets)
            subject = subject_key(fam, text) if fam else ""
            cstatus = "PASS"; cid = ""
            if fam and date_key and subject:
                cid = canonical_id(fam, date_key, subject)
            elif fam:
                cstatus = "CANONICALIZATION_AMBIGUOUS"
            else:
                cstatus = "NOT_APPLICABLE"
            tickers = sorted(m["ticker"] for m in markets if m.get("ticker"))
            routes = sorted({r for t in tickers for r in route_by_ticker[t]})
            opens = sorted(m.get("open_time") for m in markets if m.get("open_time"))
            closes = sorted(m.get("close_time") for m in markets if m.get("close_time"))
            row = {
                "venue":"KALSHI","series_ticker":st,"series_title":s["series_title"],"event_ticker":event_ticker,
                "semantic_status":semantic_status,"strict_family_passes":"|".join(passes),"resolved_family":fam or "",
                "canonicalization_status":cstatus,"canonical_event_id":cid,"event_reference_date":date_key or "",
                "event_reference_date_source":date_source or "","normalized_subject_key":subject,"market_count":len(tickers),
                "market_tickers":"|".join(tickers),"routes":"|".join(routes),"earliest_open_time":opens[0] if opens else "",
                "latest_close_time":closes[-1] if closes else "","semantic_text_sha256":hashlib.sha256(norm(text).encode()).hexdigest(),
            }
            event_rows.append(row)
            if semantic_status.startswith("AMBIGUOUS") or cstatus == "CANONICALIZATION_AMBIGUOUS":
                ambiguous.append({**row, "semantic_text":norm(text)[:2000]})
        if idx % 25 == 0:
            print(f"processed_candidate_series={idx}/{len(candidate_series)}", flush=True)

    accepted = [r for r in event_rows if r["semantic_status"].startswith("ACCEPT") and r["canonicalization_status"]=="PASS"]
    unique_ids = {r["canonical_event_id"] for r in accepted}
    duplicate_alias_rows = len(accepted) - len(unique_ids)
    fam_counts = defaultdict(lambda: {"accepted_event_rows":0,"canonical_unique_events":set()})
    for r in accepted:
        fam_counts[r["resolved_family"]]["accepted_event_rows"] += 1
        fam_counts[r["resolved_family"]]["canonical_unique_events"].add(r["canonical_event_id"])

    fields = ["venue","series_ticker","series_title","event_ticker","semantic_status","strict_family_passes","resolved_family",
        "canonicalization_status","canonical_event_id","event_reference_date","event_reference_date_source","normalized_subject_key",
        "market_count","market_tickers","routes","earliest_open_time","latest_close_time","semantic_text_sha256"]
    with (REG / "w4b_kalshi_semantic_series_v1_1.csv").open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=list(series_rows[0].keys()) if series_rows else ["series_ticker"]); w.writeheader(); w.writerows(series_rows)
    write_csv_gz(REG / "w4b_kalshi_semantic_events_v1_1.csv.gz", event_rows, fields)
    write_csv_gz(REG / "w4b_kalshi_semantic_ambiguous_v1_1.csv.gz", ambiguous, fields + ["semantic_text"])

    summary = {
        "artifact":"W4B_KALSHI_SEMANTIC_SUMMARY","version":"W4B-KSS-v1.1","date_utc":datetime.now(timezone.utc).isoformat(),
        "protocol_version":PROTO["version"],"completeness_amendment_version":AMEND["version"],"performance_blind":True,"linked_asset_realized_returns_read":False,
        "raw_classified_unique_series":len(by_series),"retrieved_candidate_series":len(candidate_series),
        "boundary_candidate_series":sum(1 for r in series_rows if r["boundary_candidate"]=="YES"),
        "boundary_noncandidate_series_still_retrieved":sum(1 for r in series_rows if r["boundary_candidate"]=="NO"),
        "event_rows_examined":len(event_rows),"accepted_strict_event_rows":len(accepted),"accepted_unique_canonical_events":len(unique_ids),
        "canonical_alias_rows_collapsed":duplicate_alias_rows,"ambiguous_rows":len(ambiguous),"api_error_count":len(api_errors),
        "route_truncation_count":len(route_truncations),"api_errors":api_errors,"route_truncations":route_truncations,
        "family_counts":{fam:{"accepted_event_rows":v["accepted_event_rows"],"canonical_unique_events":len(v["canonical_unique_events"])} for fam,v in sorted(fam_counts.items())},
        "gate_decision":"PASS_SEMANTIC_MATERIALIZATION" if not api_errors and not route_truncations else "FAIL_INCOMPLETE_API_MATERIALIZATION",
        "interpretation":"Strict performance-blind semantic/canonical materialization. Counts are not PIT-history-certified, cross-venue-deduplicated, official-truth-certified, asset-mapped or N_final_backtestable."
    }
    (REG / "w4b_kalshi_semantic_summary_v1_1.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
    print(json.dumps({k:summary[k] for k in ["raw_classified_unique_series","retrieved_candidate_series","boundary_candidate_series","boundary_noncandidate_series_still_retrieved","event_rows_examined","accepted_strict_event_rows","accepted_unique_canonical_events","ambiguous_rows","api_error_count","route_truncation_count","gate_decision"]}, indent=2, sort_keys=True))
    if summary["gate_decision"].startswith("FAIL"):
        raise SystemExit(2)

if __name__ == "__main__":
    main()

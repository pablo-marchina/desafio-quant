#!/usr/bin/env python3
from __future__ import annotations

import csv, json, re, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
PROTO = json.loads((REG / "w4_backtest_expansion_research_protocol_v1.json").read_text())
FAMS = PROTO["frozen_family_dictionary"]
UA = "ARGOS-W4-backtest-expansion-research/1.0"


def get_json(url: str, retries: int = 4):
    err = None
    for i in range(retries):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            err = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET failed after {retries}: {url}: {err}")


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%+.-]+", " ", (s or "").lower())).strip()


def classify(text):
    t = norm(text)
    hits = []
    for fam, kws in FAMS.items():
        if any(norm(k) in t for k in kws):
            hits.append(fam)
    return hits


def year_from_ms(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).year
    except Exception:
        return None


def year_from_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).year
    except Exception:
        return None


def census_kalshi(max_pages=2500):
    # Current official docs: GET /events uses external-api.kalshi.com and max limit=200.
    domain = "https://external-api.kalshi.com/trade-api/v2/events"
    rows, cursor, page = [], "", 0
    while page < max_pages:
        q = {"limit": 200, "status": "settled"}
        if cursor: q["cursor"] = cursor
        obj = get_json(domain + "?" + urlencode(q))
        evs = obj.get("events", [])
        if not evs: break
        for e in evs:
            txt = " ".join(str(e.get(k) or "") for k in ("title", "sub_title", "series_ticker", "category"))
            hits = classify(txt)
            yr = year_from_iso(e.get("strike_date")) or year_from_iso(e.get("settlement_ts"))
            for fam in hits:
                rows.append({"venue":"KALSHI","family":fam,"event_id":e.get("event_ticker"),"year":yr,"series":e.get("series_ticker") or "","token":"REAL_MONEY","title":e.get("title") or ""})
        cursor = obj.get("cursor") or ""
        page += 1
        if not cursor: break
    return rows, {"pages": page, "domain": domain, "page_limit":200, "truncated": bool(cursor)}


def census_manifold(max_pages=300):
    base = "https://api.manifold.markets/v0/search-markets"
    rows, before, page = [], None, 0
    while page < max_pages:
        q = {"sort":"newest","filter":"resolved","contractType":"BINARY","limit":1000}
        if before is not None: q["beforeTime"] = before
        arr = get_json(base + "?" + urlencode(q))
        if not arr: break
        for m in arr:
            hits = classify(m.get("question") or "")
            yr = year_from_ms(m.get("resolutionTime") or m.get("closeTime") or m.get("createdTime"))
            for fam in hits:
                rows.append({"venue":"MANIFOLD","family":fam,"event_id":m.get("id"),"year":yr,"series":"","token":m.get("token") or "UNKNOWN","title":m.get("question") or ""})
        last = arr[-1].get("createdTime")
        if last is None or last == before: break
        before = int(last) - 1
        page += 1
        if len(arr) < 1000: break
    return rows, {"pages": page, "truncated": page >= max_pages}


def existing_polymarket_counts():
    plan = json.loads((REG / "post_freeze_extension_plan.json").read_text())
    accepted = plan.get("W2C", {}).get("accepted_total")
    tested = plan.get("W2C", {}).get("pit_candidate_events")
    fams = {"EARNINGS_EPS":100,"FDA_FINAL_PDUFA_DECISION":63,"MACRO_STATISTICAL_RELEASE":97}
    return {"semantic_accepted_total": accepted, "pit_candidate_events": tested, "known_pit_family_counts": fams}


def main():
    kalshi, km = census_kalshi()
    manifold, mm = census_manifold()
    allrows = kalshi + manifold
    REG.mkdir(exist_ok=True)
    out_csv = REG / "w4_backtest_expansion_census_candidates_v1.csv"
    fields = ["venue","family","event_id","year","series","token","title"]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(allrows)

    by_vf = Counter((r["venue"], r["family"]) for r in allrows)
    by_vfy = Counter((r["venue"], r["family"], str(r["year"])) for r in allrows)
    kalshi_series = defaultdict(set)
    for r in kalshi:
        if r["series"]: kalshi_series[r["family"]].add(r["series"])
    token_mix = Counter(r["token"] for r in manifold)
    unique_k = len({r["event_id"] for r in kalshi})
    unique_m = len({r["event_id"] for r in manifold})
    poly = existing_polymarket_counts()
    lower_union = unique_k + unique_m + int(poly.get("semantic_accepted_total") or 0)

    summary = {
        "artifact":"W4_BACKTEST_EXPANSION_CENSUS_SUMMARY",
        "version":"W4-BER-CENSUS-v1.0",
        "performance_blind":True,
        "realized_linked_asset_returns_read":False,
        "protocol":"registry/w4_backtest_expansion_research_protocol_v1.json",
        "venues": {
            "KALSHI":{"unique_classified_events":unique_k, "classified_rows":len(kalshi), **km},
            "MANIFOLD":{"unique_classified_markets":unique_m, "classified_rows":len(manifold), "token_mix":dict(token_mix), **mm},
            "POLYMARKET_EXISTING":poly,
        },
        "counts_by_venue_family": {f"{v}|{f}":n for (v,f),n in sorted(by_vf.items())},
        "counts_by_venue_family_year": {f"{v}|{f}|{y}":n for (v,f,y),n in sorted(by_vfy.items())},
        "kalshi_recurring_series_count_by_family": {f:len(s) for f,s in sorted(kalshi_series.items())},
        "lower_bound_pre_dedup_classified_union": lower_union,
        "interpretation_limits":[
            "keyword-classified counts are discovery capacity, not semantic-valid population",
            "cross-venue duplicates are not removed",
            "Manifold is robustness-only until separately authorized",
            "no count authorizes a trading rule"
        ]
    }
    (REG / "w4_backtest_expansion_census_summary_v1.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()

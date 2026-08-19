#!/usr/bin/env python3
"""Profile the oldest genuinely backtestable history available to the demo suite.

Presentation/research extension only. This profiler never changes the frozen
competition protocol. It distinguishes event metadata dates from actual venue
price-history availability and records the oldest reproducible observation per
venue before the max-history backtest is expanded.
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
OUT_JSON = REG / "presentation_demo_max_history_profile_v3.json"
OUT_CSV = REG / "presentation_demo_max_history_profile_v3.csv"
UA = "ARGOS-max-history-profiler/3.0"


def read_gz(path: Path):
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8", newline="", errors="replace") as f:
        return list(csv.DictReader(f))


def parse_date(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def iso_from_ts(v):
    try:
        return datetime.fromtimestamp(int(float(v)), timezone.utc).isoformat()
    except Exception:
        return None


def http_json(url: str, timeout=30, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except Exception as e:
            last = e
            if i + 1 < retries:
                time.sleep(0.5 * (2 ** i))
    raise last


def json_array(v):
    if isinstance(v, list):
        return v
    if v is None:
        return []
    try:
        x = json.loads(v)
        return x if isinstance(x, list) else []
    except Exception:
        return []


def profile_cross_venue():
    rows = read_gz(REG / "w4b_cross_venue_records_v1.csv.gz")
    out = {}
    for venue in ("POLYMARKET", "KALSHI", "FORECASTEX"):
        vr = [r for r in rows if r.get("venue") == venue]
        dts = [parse_date(r.get("event_reference_date")) for r in vr]
        dts = [d for d in dts if d]
        out[venue] = {
            "canonical_records": len(vr),
            "metadata_reference_min": min(dts).date().isoformat() if dts else None,
            "metadata_reference_max": max(dts).date().isoformat() if dts else None,
            "metadata_year_counts": dict(sorted(Counter(d.year for d in dts).items())),
        }
    return out


def profile_kalshi():
    event_rows = read_gz(REG / "w4b_kalshi_history_event_v1_0_3.csv.gz")
    market_rows = read_gz(REG / "w4b_kalshi_history_market_v1_0_3.csv.gz")
    t0s = []
    for r in event_rows:
        try:
            t0s.append(int(r.get("operational_t0_ts") or 0))
        except Exception:
            pass
    t0s = [x for x in t0s if x > 0]
    resolved = [r for r in market_rows if r.get("http_resolution_status") == "RESOLVED_200_DATA"]
    first_ts = []
    last_ts = []
    for r in resolved:
        for col, arr in (("first_end_period_ts", first_ts), ("last_end_period_ts", last_ts)):
            try:
                x = int(r.get(col) or 0)
                if x > 0:
                    arr.append(x)
            except Exception:
                pass
    return {
        "canonical_events": len(event_rows),
        "market_rows": len(market_rows),
        "resolved_market_rows": len(resolved),
        "oldest_operational_t0": iso_from_ts(min(t0s)) if t0s else None,
        "newest_operational_t0": iso_from_ts(max(t0s)) if t0s else None,
        "oldest_audited_candle": iso_from_ts(min(first_ts)) if first_ts else None,
        "newest_audited_candle": iso_from_ts(max(last_ts)) if last_ts else None,
        "history_class_counts": dict(sorted(Counter(r.get("history_class", "") for r in event_rows).items())),
    }


def profile_forecastex():
    events = read_gz(REG / "w4b_forecastex_events_v1.csv.gz")
    contracts = read_gz(REG / "w4b_forecastex_contracts_v1.csv.gz")
    date_fields = []
    if contracts:
        date_fields = [c for c in contracts[0] if any(k in c.lower() for k in ("date", "expiry", "expire", "settle", "start", "end"))]
    field_ranges = {}
    for c in date_fields:
        vals = [parse_date(r.get(c)) for r in contracts]
        vals = [v for v in vals if v]
        if vals:
            field_ranges[c] = {"min": min(vals).date().isoformat(), "max": max(vals).date().isoformat(), "non_null": len(vals)}
    return {
        "canonical_events": len(events),
        "contract_identifier_rows": len(contracts),
        "contract_columns": list(contracts[0].keys()) if contracts else [],
        "date_field_ranges": field_ranges,
    }


def choose_pm_market(event_obj):
    markets = event_obj.get("markets") or []
    candidates = []
    for m in markets:
        outs = json_array(m.get("outcomes"))
        toks = json_array(m.get("clobTokenIds"))
        prices = json_array(m.get("outcomePrices"))
        if len(outs) != 2 or len(toks) != 2:
            continue
        norm = [str(x).strip().lower() for x in outs]
        if set(norm) != {"yes", "no"}:
            continue
        yi = norm.index("yes")
        settlement = None
        if len(prices) == 2:
            try:
                settlement = float(prices[yi])
            except Exception:
                pass
        try:
            mid = int(str(m.get("id") or "0"))
        except Exception:
            mid = 10**30
        candidates.append((mid, str(m.get("slug") or ""), m, str(toks[yi]), settlement))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    _, _, m, yes_token, settlement = candidates[0]
    return m, yes_token, settlement


def profile_polymarket():
    rows = read_gz(REG / "w4b_polymarket_recensus_events_v1.csv.gz")
    dated = []
    for r in rows:
        d = parse_date(r.get("event_reference_date"))
        ids = [x for x in re.split(r"[|,;]", str(r.get("gamma_event_ids") or "")) if x.strip()]
        if d and ids:
            dated.append((d, r, ids))
    dated.sort(key=lambda x: (x[0], x[1].get("canonical_event_id", "")))

    probes = []
    seen_token = set()
    # Probe a bounded set of the oldest canonical metadata events. Metadata may
    # predate Polymarket itself, so actual CLOB history is the authoritative lower bound.
    for d, r, ids in dated[:120]:
        gid = sorted(ids, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 10**30, x))[0]
        try:
            ev = http_json(f"https://gamma-api.polymarket.com/events/{urllib.parse.quote(gid)}")
            chosen = choose_pm_market(ev)
            if not chosen:
                continue
            m, token, settlement = chosen
            if token in seen_token:
                continue
            seen_token.add(token)
            q = urllib.parse.urlencode({"market": token, "interval": "max", "fidelity": 1440})
            hist = http_json("https://clob.polymarket.com/prices-history?" + q)
            pts = hist.get("history", []) if isinstance(hist, dict) else []
            ts = sorted(int(p["t"]) for p in pts if isinstance(p, dict) and p.get("t") is not None)
            probes.append({
                "canonical_event_id": r.get("canonical_event_id"),
                "event_reference_date": d.date().isoformat(),
                "gamma_event_id": gid,
                "gamma_market_id": m.get("id"),
                "market_start_date": m.get("startDate"),
                "market_end_date": m.get("endDate"),
                "yes_token": token,
                "terminal_yes_price": settlement,
                "history_points": len(ts),
                "history_first": iso_from_ts(ts[0]) if ts else None,
                "history_last": iso_from_ts(ts[-1]) if ts else None,
            })
            if len([p for p in probes if p["history_points"] > 0]) >= 25:
                break
        except Exception as e:
            probes.append({
                "canonical_event_id": r.get("canonical_event_id"),
                "event_reference_date": d.date().isoformat(),
                "gamma_event_id": gid,
                "error": f"{type(e).__name__}: {e}",
                "history_points": 0,
            })
        time.sleep(0.03)

    with_hist = [p for p in probes if p.get("history_points", 0) > 0 and p.get("history_first")]
    return {
        "canonical_events": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "metadata_reference_min": dated[0][0].date().isoformat() if dated else None,
        "metadata_reference_max": dated[-1][0].date().isoformat() if dated else None,
        "oldest_actual_price_history_from_probe": min((p["history_first"] for p in with_hist), default=None),
        "newest_actual_price_history_from_probe": max((p["history_last"] for p in with_hist), default=None),
        "probe_count": len(probes),
        "probe_with_history": len(with_hist),
        "oldest_probe_examples": sorted(with_hist, key=lambda p: p["history_first"])[:10],
        "probe_errors": [p for p in probes if p.get("error")][:10],
    }


def main():
    cross = profile_cross_venue()
    k = profile_kalshi()
    f = profile_forecastex()
    p = profile_polymarket()
    out = {
        "artifact": "PRESENTATION_DEMO_MAX_HISTORY_PROFILE",
        "version": "v3.0",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "guardrails": [
            "presentation_only",
            "retrospective_non_confirmatory",
            "metadata_date_is_not_price_history",
            "no_linked_asset_realized_return_used_for_universe_selection",
        ],
        "cross_venue_canonical_metadata": cross,
        "polymarket": p,
        "kalshi": k,
        "forecastex": f,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    flat = []
    flat.append({"venue": "POLYMARKET", "canonical_events": p.get("canonical_events"), "metadata_min": p.get("metadata_reference_min"), "metadata_max": p.get("metadata_reference_max"), "oldest_tradeable_observation": p.get("oldest_actual_price_history_from_probe"), "newest_tradeable_observation": p.get("newest_actual_price_history_from_probe"), "notes": f"probe_with_history={p.get('probe_with_history')}/{p.get('probe_count')}"})
    flat.append({"venue": "KALSHI", "canonical_events": k.get("canonical_events"), "metadata_min": cross.get("KALSHI", {}).get("metadata_reference_min"), "metadata_max": cross.get("KALSHI", {}).get("metadata_reference_max"), "oldest_tradeable_observation": k.get("oldest_audited_candle"), "newest_tradeable_observation": k.get("newest_audited_candle"), "notes": f"resolved_market_rows={k.get('resolved_market_rows')}"})
    # ForecastEx archive lower bound will be verified by the full runner; contracts
    # date fields are metadata only at this stage.
    ranges = f.get("date_field_ranges", {})
    mins = [x["min"] for x in ranges.values() if x.get("min")]
    maxs = [x["max"] for x in ranges.values() if x.get("max")]
    flat.append({"venue": "FORECASTEX", "canonical_events": f.get("canonical_events"), "metadata_min": min(mins) if mins else cross.get("FORECASTEX", {}).get("metadata_reference_min"), "metadata_max": max(maxs) if maxs else cross.get("FORECASTEX", {}).get("metadata_reference_max"), "oldest_tradeable_observation": None, "newest_tradeable_observation": None, "notes": "official archive lower bound verified during full runner"})
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["venue", "canonical_events", "metadata_min", "metadata_max", "oldest_tradeable_observation", "newest_tradeable_observation", "notes"])
        w.writeheader(); w.writerows(flat)
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

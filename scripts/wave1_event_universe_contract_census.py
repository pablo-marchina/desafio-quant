#!/usr/bin/env python3
"""Wave-1 event-universe census from the official public Polymarket Gamma API.

This script is deliberately PERFORMANCE-BLIND. It never reads ARGOS outcomes,
equity returns, model scores, or trade P&L. It measures only prediction-market
contract availability / density properties needed by EUAS-v1.0.

Outputs are research evidence for report framing and future-universe design;
they do not amend FST-v1.0 or re-open H2.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://gamma-api.polymarket.com"
API_LIMIT = 500
MAX_PAGES = 300
USER_AGENT = "ARGOS-Wave1-EUAS-Census/1.0 (+research; public Gamma API)"
CLASSIFIER_VERSION = "EUAS_TEXT_CLASSIFIER_v1.0"

# Frozen before the census is executed. These patterns classify market/event
# *topics*, not profitability or realized linked-asset behavior.
FAMILY_PATTERNS = {
    "EARNINGS_EPS": [r"\bearnings\b", r"\beps\b", r"earnings per share"],
    "FDA_APPROVAL_ADVISORY": [
        r"\bfda\b", r"food and drug administration", r"\bpdufa\b",
        r"drug approval", r"advisory committee",
    ],
    "ANTITRUST_REGULATORY": [
        r"\bantitrust\b", r"\bftc\b", r"federal trade commission",
        r"department of justice", r"\bdoj\b", r"competition commission",
        r"regulatory approval", r"regulatory clearance",
    ],
    "LITIGATION_COURT": [
        r"supreme court", r"federal court", r"court ruling", r"court decision",
        r"\blawsuit\b", r"\blitigation\b", r"\bverdict\b", r"\binjunction\b",
    ],
    "MACRO_FED_CPI": [
        r"federal reserve", r"\bfed\b", r"\bcpi\b", r"consumer price index",
        r"\binflation\b", r"interest rate", r"rate cut", r"rate hike",
        r"\bgdp\b", r"\bpayrolls?\b", r"\bunemployment\b",
    ],
}

MA_CORE = re.compile(r"\b(merger|acquisition|acquire|acquires|acquired|buyout|takeover|deal)\b", re.I)
MA_COMPLETION = re.compile(
    r"\b(close|closing|closed|complete|completion|completed|approve|approved|approval|clearance|terminate|terminated|break|breaks)\b",
    re.I,
)
COMPILED = {fam: [re.compile(p, re.I) for p in pats] for fam, pats in FAMILY_PATTERNS.items()}


def fetch_json(path: str, params: dict[str, object] | None = None, retries: int = 6):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries - 1:
                raise
            delay = min(2 ** attempt, 20)
            print(f"retry {attempt + 1}/{retries} after {exc}: {url}")
            time.sleep(delay)
    raise RuntimeError("unreachable")


def fetch_all_closed_events() -> list[dict]:
    events: list[dict] = []
    cursor: str | None = None
    seen_ids: set[str] = set()
    for page in range(MAX_PAGES):
        params: dict[str, object] = {
            "limit": API_LIMIT,
            "closed": "true",
            "ascending": "true",
            "order": "createdAt",
        }
        if cursor:
            params["after_cursor"] = cursor
        payload = fetch_json("/events/keyset", params)
        batch = payload.get("events", [])
        for event in batch:
            eid = str(event.get("id", ""))
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                events.append(event)
        cursor = payload.get("next_cursor")
        print(f"page={page + 1} batch={len(batch)} total={len(events)} next={bool(cursor)}")
        if not cursor or not batch:
            break
    else:
        raise RuntimeError(f"Exceeded MAX_PAGES={MAX_PAGES}; census incomplete")
    return events


def text_blob(event: dict) -> str:
    bits: list[str] = []
    for key in ("title", "subtitle", "description", "slug", "category", "subcategory"):
        if event.get(key):
            bits.append(str(event[key]))
    for tag in event.get("tags") or []:
        if isinstance(tag, dict):
            bits.extend(str(tag.get(k, "")) for k in ("label", "slug"))
    for market in event.get("markets") or []:
        if isinstance(market, dict):
            bits.extend(str(market.get(k, "")) for k in ("question", "slug", "description", "category"))
    return " \n ".join(bits).lower()


def classify(event: dict) -> list[tuple[str, str]]:
    blob = text_blob(event)
    matches: list[tuple[str, str]] = []
    for family, patterns in COMPILED.items():
        hit = next((p.pattern for p in patterns if p.search(blob)), None)
        if hit:
            matches.append((family, hit))
    if MA_CORE.search(blob):
        if MA_COMPLETION.search(blob):
            matches.append(("MA_DEAL_COMPLETION_REGULATORY_CLEARANCE", "MA_CORE+MA_COMPLETION"))
        else:
            matches.append(("MA_ANNOUNCEMENT_RUMOR", "MA_CORE_without_completion_term"))
    dedup: dict[str, str] = {}
    for family, reason in matches:
        dedup.setdefault(family, reason)
    return sorted(dedup.items())


def parse_dt(value) -> datetime | None:
    if not value:
        return None
    s = str(value).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def as_float(value) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def deterministic_gzip_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw_fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_fh, mtime=0) as gz:
            gz.write(payload)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_gzip_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    sio = io.StringIO(newline="")
    writer = csv.DictWriter(sio, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    deterministic_gzip_write(path, sio.getvalue().encode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry-dir", default="registry")
    ap.add_argument("--raw-output", default="/tmp/wave1_polymarket_closed_events_raw.json.gz")
    args = ap.parse_args()

    registry = Path(args.registry_dir)
    registry.mkdir(parents=True, exist_ok=True)
    snapshot_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    events = fetch_all_closed_events()
    raw_bytes = json.dumps(events, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    raw_sha = hashlib.sha256(raw_bytes).hexdigest()
    raw_path = Path(args.raw_output)
    deterministic_gzip_write(raw_path, raw_bytes)

    classified_rows: list[dict] = []
    by_family: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        start = parse_dt(event.get("startDate") or event.get("creationDate") or event.get("createdAt"))
        end = parse_dt(event.get("endDate") or event.get("closedTime"))
        lead_days = (end - start).total_seconds() / 86400 if start and end and end >= start else None
        volume = as_float(event.get("volume"))
        liquidity = as_float(event.get("liquidity"))
        tags = sorted({str(t.get("slug") or t.get("label") or "") for t in (event.get("tags") or []) if isinstance(t, dict)})
        market_count = len(event.get("markets") or [])
        for family, reason in classify(event):
            row = {
                "family": family,
                "event_id": str(event.get("id", "")),
                "title": str(event.get("title", "")),
                "slug": str(event.get("slug", "")),
                "start_utc": start.isoformat().replace("+00:00", "Z") if start else "",
                "end_utc": end.isoformat().replace("+00:00", "Z") if end else "",
                "lead_days": "" if lead_days is None else f"{lead_days:.8f}",
                "volume": "" if volume is None else f"{volume:.8f}",
                "liquidity_snapshot": "" if liquidity is None else f"{liquidity:.8f}",
                "market_count": market_count,
                "tags": "|".join(tags),
                "classifier_reason": reason,
            }
            classified_rows.append(row)
            by_family[family].append(row)

    event_fields = [
        "family", "event_id", "title", "slug", "start_utc", "end_utc", "lead_days",
        "volume", "liquidity_snapshot", "market_count", "tags", "classifier_reason",
    ]
    classified_rows.sort(key=lambda r: (r["family"], r["start_utc"], r["event_id"]))
    events_path = registry / "wave1_event_universe_census_events.csv.gz"
    write_gzip_csv(events_path, classified_rows, event_fields)

    families = sorted(set(FAMILY_PATTERNS) | {"MA_DEAL_COMPLETION_REGULATORY_CLEARANCE", "MA_ANNOUNCEMENT_RUMOR"})
    summary_rows: list[dict] = []
    for family in families:
        rows = by_family.get(family, [])
        volumes = [float(r["volume"]) for r in rows if r["volume"] != ""]
        leads = [float(r["lead_days"]) for r in rows if r["lead_days"] != ""]
        starts = [r["start_utc"] for r in rows if r["start_utc"]]
        summary_rows.append({
            "family": family,
            "candidate_events": len(rows),
            "events_with_volume": len(volumes),
            "volume_median": percentile(volumes, 0.5),
            "volume_p25": percentile(volumes, 0.25),
            "volume_p75": percentile(volumes, 0.75),
            "volume_ge_1k": sum(v >= 1_000 for v in volumes),
            "volume_ge_10k": sum(v >= 10_000 for v in volumes),
            "volume_ge_100k": sum(v >= 100_000 for v in volumes),
            "events_with_lead_days": len(leads),
            "lead_days_median": percentile(leads, 0.5),
            "lead_days_p25": percentile(leads, 0.25),
            "lead_days_p75": percentile(leads, 0.75),
            "earliest_start_utc": min(starts) if starts else "",
            "latest_start_utc": max(starts) if starts else "",
            "classifier_version": CLASSIFIER_VERSION,
            "manual_validation_required": True,
        })

    summary_fields = list(summary_rows[0].keys()) if summary_rows else []
    summary_path = registry / "wave1_event_universe_census_summary.csv"
    write_csv(summary_path, summary_rows, summary_fields)

    meta = {
        "artifact": "WAVE1_EVENT_UNIVERSE_POLYMARKET_CENSUS",
        "version": "EUAS-CENSUS-v1.0",
        "snapshot_utc": snapshot_utc,
        "source": "official Polymarket Gamma API /events/keyset?closed=true",
        "source_docs": "https://docs.polymarket.com/api-reference/events/list-events-keyset-pagination",
        "performance_blind": True,
        "scientific_reopen": False,
        "classifier_version": CLASSIFIER_VERSION,
        "total_closed_events_retrieved": len(events),
        "classified_event_family_rows": len(classified_rows),
        "raw_json_sha256": raw_sha,
        "classified_events_csv_gz_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
        "summary_csv_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "limitations": [
            "Text/tag classifier is a discovery instrument and can create false positives/negatives.",
            "Event volume is lifetime event volume, not a historical point-in-time liquidity measure.",
            "Current closed-event records may reflect taxonomy changes after market close.",
            "Lead days use API start/creation to end timestamps and do not establish that the contract predated every material public rumor/news item.",
            "Linked-asset mapping and information-asymmetry scores require separate primary-evidence review.",
            "No ARGOS performance, equity return, Brier/log loss, or outcome-based family selection is used."
        ],
        "next_step": "Manually validate family samples and use the census only for EUAS contractability/liquidity/sampleability evidence."
    }
    meta_path = registry / "wave1_event_universe_census_summary.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()

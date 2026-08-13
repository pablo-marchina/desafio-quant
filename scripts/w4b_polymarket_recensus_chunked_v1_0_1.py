#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
CKPT = REG / "w4b_pm_checkpoint_v1_0_1"
STATE_PATH = CKPT / "state.json"

BASE_PATH = ROOT / "scripts" / "w4b_polymarket_recensus_v1.py"
spec = importlib.util.spec_from_file_location("w4b_pm_v1_frozen", BASE_PATH)
PM = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(PM)

PROTO = PM.PROTO
SEM = PM.SEM
BASE = PM.BASE

PAGE_FIELDS = [
    "page_number","input_cursor_sha256","output_cursor_sha256","event_rows_returned",
    "http_status","response_bytes","response_sha256","terminal_page"
]
VENUE_FIELDS = [
    "gamma_event_id","title","slug","end_date","event_reference_date",
    "associated_market_count","market_ids","strict_family_hits","resolved_family",
    "semantic_status","normalized_subject_key","canonicalization_status",
    "canonical_event_id","semantic_text_sha256"
]

def write_gz(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in fields} for r in rows])

def read_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)

def state_default():
    return {
        "artifact": "W4B_POLYMARKET_RECENSUS_RUNTIME_STATE",
        "version": "W4B-PM-R-RUNTIME-v1.0.1",
        "protocol_version": PROTO["version"],
        "cursor": "",
        "page_no": 0,
        "terminal": False,
        "unresolved": [],
        "seen_cursor_sha256": [],
        "chunks": [],
        "chunk_index": 0,
    }

def load_state():
    if not STATE_PATH.exists():
        return state_default()
    x = json.loads(STATE_PATH.read_text())
    assert x["version"] == "W4B-PM-R-RUNTIME-v1.0.1"
    assert x["protocol_version"] == PROTO["version"]
    return x

def save_state(x):
    CKPT.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(x, indent=2, sort_keys=True) + "\n")

def reduced_event(ev: dict):
    eid = str(ev.get("id") or "").strip()
    if not eid:
        return None
    text = PM.semantic_text(ev)
    passes = SEM.strict_families(text)
    fam, status = SEM.resolve_family(passes)
    ref_date = PM.parse_utc_date(ev.get("endDate") or "")
    subject = SEM.subject_key(fam, text) if fam else ""
    cstatus = "PASS" if fam and ref_date and subject else ("CANONICALIZATION_AMBIGUOUS" if fam else "NOT_APPLICABLE")
    cid = SEM.canonical_id(fam, ref_date, subject) if cstatus == "PASS" else ""
    markets = ev.get("markets") or []
    market_ids = []
    if isinstance(markets, list):
        for m in markets:
            if isinstance(m, dict) and m.get("id") is not None:
                market_ids.append(str(m.get("id")))
    return {
        "gamma_event_id": eid,
        "title": PM.scalar_text(ev.get("title")),
        "slug": PM.scalar_text(ev.get("slug")),
        "end_date": PM.scalar_text(ev.get("endDate")),
        "event_reference_date": ref_date or "",
        "associated_market_count": len(markets) if isinstance(markets, list) else 0,
        "market_ids": "|".join(sorted(set(market_ids))),
        "strict_family_hits": "|".join(passes),
        "resolved_family": fam or "",
        "semantic_status": status,
        "normalized_subject_key": subject,
        "canonicalization_status": cstatus,
        "canonical_event_id": cid,
        "semantic_text_sha256": hashlib.sha256(SEM.norm(text).encode()).hexdigest(),
    }

def collect(max_pages: int):
    closeout = REG / "w4b_forecastex_census_closeout_v1.json"
    if not closeout.exists():
        raise SystemExit("SEQUENCE_GATE_MISSING_FORECASTEX_CLOSEOUT")
    fx = json.loads(closeout.read_text())
    if fx.get("technical_gate_decision") != PROTO["sequence_prerequisite"]["required_decision"]:
        raise SystemExit("SEQUENCE_GATE_FORECASTEX_NOT_PASSED")

    s = load_state()
    if s["terminal"]:
        print(json.dumps({"terminal": True, "page_no": s["page_no"], "message": "already_terminal"}))
        return

    cursor = s.get("cursor", "")
    seen_hashes = set(s.get("seen_cursor_sha256", []))
    page_rows, venue_rows = [], []
    start_page = int(s["page_no"]) + 1

    for _ in range(max_pages):
        q = {"closed": "true", "limit": 500}
        if cursor:
            q["after_cursor"] = cursor
        url = BASE + PROTO["source_contract"]["endpoint"] + "?" + urlencode(q)
        obj, body, status, err = PM.get_json_bytes(url)
        if err or status != 200 or not isinstance(obj, dict):
            s["unresolved"].append({
                "page_number": int(s["page_no"]) + 1,
                "status": status if status is not None else "",
                "error": (err or {}).get("error", ""),
                "cursor_sha256": hashlib.sha256(cursor.encode()).hexdigest() if cursor else "",
            })
            save_state(s)
            raise SystemExit("POLYMARKET_PAGINATION_UNRESOLVED")
        batch = obj.get("events")
        if not isinstance(batch, list):
            s["unresolved"].append({
                "page_number": int(s["page_no"]) + 1,
                "status": status,
                "error": "invalid_events_wrapper",
                "cursor_sha256": hashlib.sha256(cursor.encode()).hexdigest() if cursor else "",
            })
            save_state(s)
            raise SystemExit("POLYMARKET_INVALID_EVENTS_WRAPPER")

        s["page_no"] = int(s["page_no"]) + 1
        next_cursor = obj.get("next_cursor") or ""
        out_hash = hashlib.sha256(next_cursor.encode()).hexdigest() if next_cursor else ""
        page_rows.append({
            "page_number": s["page_no"],
            "input_cursor_sha256": hashlib.sha256(cursor.encode()).hexdigest() if cursor else "",
            "output_cursor_sha256": out_hash,
            "event_rows_returned": len(batch),
            "http_status": status,
            "response_bytes": len(body),
            "response_sha256": hashlib.sha256(body).hexdigest(),
            "terminal_page": "YES" if not next_cursor else "NO",
        })
        for ev in batch:
            if isinstance(ev, dict):
                row = reduced_event(ev)
                if row:
                    venue_rows.append(row)

        if not next_cursor:
            s["terminal"] = True
            cursor = ""
            break
        if out_hash in seen_hashes:
            s["unresolved"].append({
                "page_number": s["page_no"],
                "status": 200,
                "error": "cursor_cycle_detected",
                "cursor_sha256": out_hash,
            })
            save_state(s)
            raise SystemExit("POLYMARKET_CURSOR_CYCLE")
        seen_hashes.add(out_hash)
        cursor = next_cursor
        if int(s["page_no"]) % 100 == 0:
            print(f"polymarket_chunk_pages={s['page_no']}", flush=True)

    end_page = int(s["page_no"])
    if page_rows:
        idx = int(s.get("chunk_index", 0)) + 1
        pfile = f"pages_{idx:04d}_{start_page:08d}_{end_page:08d}.csv.gz"
        vfile = f"venue_{idx:04d}_{start_page:08d}_{end_page:08d}.csv.gz"
        write_gz(CKPT / pfile, page_rows, PAGE_FIELDS)
        write_gz(CKPT / vfile, venue_rows, VENUE_FIELDS)
        s["chunks"].append({
            "chunk_index": idx,
            "start_page": start_page,
            "end_page": end_page,
            "page_file": pfile,
            "venue_file": vfile,
            "venue_rows": len(venue_rows),
        })
        s["chunk_index"] = idx
    s["cursor"] = "" if s["terminal"] else cursor
    s["seen_cursor_sha256"] = sorted(seen_hashes)
    save_state(s)
    print(json.dumps({
        "terminal": s["terminal"],
        "page_no": s["page_no"],
        "chunks": len(s["chunks"]),
        "current_chunk_venue_rows": len(venue_rows),
        "unresolved": len(s["unresolved"]),
    }, sort_keys=True))

def gamma_sort_key(v: str):
    return (0, int(v)) if v.isdigit() else (1, v)

def finalize():
    s = load_state()
    if not s["terminal"]:
        raise SystemExit("CHECKPOINT_NOT_TERMINAL")
    if s["unresolved"]:
        raise SystemExit(f"POLYMARKET_PAGINATION_UNRESOLVED:{s['unresolved'][:5]}")

    pages = []
    all_rows = []
    for c in sorted(s["chunks"], key=lambda x: int(x["chunk_index"])):
        pages.extend(read_gz(CKPT / c["page_file"]))
        all_rows.extend(read_gz(CKPT / c["venue_file"]))
    pages.sort(key=lambda r: int(r["page_number"]))
    if not pages or pages[-1]["terminal_page"] != "YES":
        raise SystemExit("MISSING_TERMINAL_PAGE")

    by_id = {}
    duplicate_api_rows = 0
    for r in all_rows:
        eid = r["gamma_event_id"]
        if eid in by_id:
            duplicate_api_rows += 1
        else:
            by_id[eid] = r
    venue_rows = [by_id[k] for k in sorted(by_id, key=gamma_sort_key)]

    ambiguous, rejected = [], 0
    canonical_groups = defaultdict(list)
    for row in venue_rows:
        status = row["semantic_status"]
        cstatus = row["canonicalization_status"]
        cid = row["canonical_event_id"]
        if status.startswith("ACCEPT") and cstatus == "PASS":
            canonical_groups[cid].append(row)
        elif status.startswith("AMBIGUOUS") or cstatus == "CANONICALIZATION_AMBIGUOUS":
            ambiguous.append(row)
        else:
            rejected += 1

    events, collisions = [], []
    family_counts = Counter()
    aliases_collapsed = 0
    for cid, rows in sorted(canonical_groups.items()):
        sigs = {(r["resolved_family"], r["event_reference_date"], r["normalized_subject_key"]) for r in rows}
        if len(sigs) != 1:
            collisions.append({"canonical_event_id": cid, "signatures": ["|".join(x) for x in sorted(sigs)]})
            continue
        fam, ref_date, subject = next(iter(sigs))
        family_counts[fam] += 1
        aliases_collapsed += max(0, len(rows) - 1)
        events.append({
            "canonical_event_id": cid,
            "resolved_family": fam,
            "event_reference_date": ref_date,
            "normalized_subject_key": subject,
            "gamma_event_ids": "|".join(sorted((r["gamma_event_id"] for r in rows), key=gamma_sort_key)),
            "gamma_event_alias_count": len(rows),
            "slugs": "|".join(sorted({r["slug"] for r in rows if r["slug"]})),
            "associated_market_count": sum(int(r["associated_market_count"] or 0) for r in rows),
        })

    w2_rows, w2_by_id, w2_by_slug = PM.load_w2()
    w2_seen = set()
    overlap = []
    for row in venue_rows:
        eid = row["gamma_event_id"]
        slug = (row["slug"] or "").strip().lower()
        matches, match_type = [], "NEW_TO_W4_RECENSUS"
        if eid in w2_by_id:
            matches, match_type = w2_by_id[eid], "MATCH_EVENT_ID"
        elif slug and slug in w2_by_slug:
            matches, match_type = w2_by_slug[slug], "MATCH_SLUG"
        for m in matches:
            w2_seen.add((m.get("event_id", ""), m.get("independence_cluster_id", "")))
        overlap.append({
            "gamma_event_id": eid,
            "slug": row["slug"],
            "w4_semantic_status": row["semantic_status"],
            "w4_resolved_family": row["resolved_family"],
            "w4_canonical_event_id": row["canonical_event_id"],
            "w2_overlap_type": match_type,
            "w2_event_ids": "|".join(sorted({m.get("event_id", "") for m in matches if m.get("event_id")})),
            "w2_cluster_ids": "|".join(sorted({m.get("independence_cluster_id", "") for m in matches if m.get("independence_cluster_id")})),
            "w2_families_audit_only": "|".join(sorted({m.get("resolved_family", "") for m in matches if m.get("resolved_family")})),
        })

    w2_total_keys = {(r.get("event_id", ""), r.get("independence_cluster_id", "")) for r in w2_rows}
    w2_not_rediscovered = len(w2_total_keys - w2_seen)

    PM.write_gz(REG / "w4b_polymarket_recensus_page_manifest_v1.csv.gz", pages, PAGE_FIELDS)
    PM.write_gz(REG / "w4b_polymarket_recensus_venue_events_v1.csv.gz", venue_rows, VENUE_FIELDS)
    PM.write_gz(REG / "w4b_polymarket_recensus_events_v1.csv.gz", events, [
        "canonical_event_id","resolved_family","event_reference_date","normalized_subject_key",
        "gamma_event_ids","gamma_event_alias_count","slugs","associated_market_count"
    ])
    PM.write_gz(REG / "w4b_polymarket_recensus_ambiguous_v1.csv.gz", ambiguous, VENUE_FIELDS)
    PM.write_gz(REG / "w4b_polymarket_w2_overlap_v1.csv.gz", overlap, [
        "gamma_event_id","slug","w4_semantic_status","w4_resolved_family","w4_canonical_event_id",
        "w2_overlap_type","w2_event_ids","w2_cluster_ids","w2_families_audit_only"
    ])

    raw_event_rows = sum(int(r["event_rows_returned"]) for r in pages)
    gate = not collisions and pages[-1]["terminal_page"] == "YES"
    out = {
        "artifact": "W4B_POLYMARKET_RECENSUS_SUMMARY",
        "version": "W4B-PM-R-RESULT-v1.0.1",
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTO["version"],
        "runtime_erratum_version": "W4B-PM-R-ERRATUM-v1.0.1",
        "performance_blind": True,
        "linked_asset_realized_returns_read": False,
        "clob_price_history_read": False,
        "selection_by_volume_liquidity_or_price": False,
        "pages_fetched": len(pages),
        "raw_event_rows": raw_event_rows,
        "unique_gamma_event_ids": len(venue_rows),
        "duplicate_api_event_rows": duplicate_api_rows,
        "venue_event_rows_classified": len(venue_rows),
        "accepted_unique_canonical_events": len(events),
        "canonical_alias_rows_collapsed": aliases_collapsed,
        "accepted_family_counts": dict(sorted(family_counts.items())),
        "ambiguous_venue_event_rows": len(ambiguous),
        "rejected_venue_event_rows": rejected,
        "w2_accepted_rows": len(w2_rows),
        "w2_overlap_event_id": sum(r["w2_overlap_type"] == "MATCH_EVENT_ID" for r in overlap),
        "w2_overlap_slug_only": sum(r["w2_overlap_type"] == "MATCH_SLUG" for r in overlap),
        "w2_new_gamma_events": sum(r["w2_overlap_type"] == "NEW_TO_W4_RECENSUS" for r in overlap),
        "w2_accepted_keys_not_rediscovered": w2_not_rediscovered,
        "pagination_unresolved": s["unresolved"],
        "canonical_collisions": collisions,
        "canonical_signature_collisions": collisions,
        "gate_decision": "PASS_POLYMARKET_RECENSUS_MATERIALIZED" if gate else "FAIL_POLYMARKET_RECENSUS_MATERIALIZATION",
        "interpretation": "Exhaustive performance-blind closed-event Gamma recensus over one continuous keyset cursor chain. Runtime chunking changes transport only; counts remain venue semantic/canonical capacity, not cross-venue unique N or N_final_backtestable."
    }
    (REG / "w4b_polymarket_recensus_summary_v1.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: out[k] for k in [
        "pages_fetched","raw_event_rows","unique_gamma_event_ids","accepted_unique_canonical_events",
        "accepted_family_counts","ambiguous_venue_event_rows","w2_overlap_event_id",
        "w2_overlap_slug_only","w2_new_gamma_events","gate_decision"
    ]}, indent=2, sort_keys=True))
    if not gate:
        raise SystemExit(2)

def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="mode", required=True)
    cp = sp.add_parser("collect")
    cp.add_argument("--max-pages", type=int, default=1500)
    sp.add_parser("finalize")
    args = ap.parse_args()
    if args.mode == "collect":
        collect(args.max_pages)
    else:
        finalize()

if __name__ == "__main__":
    main()

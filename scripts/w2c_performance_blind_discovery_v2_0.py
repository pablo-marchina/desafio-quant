#!/usr/bin/env python3
"""W2C-DISC-v2.0 bounded lower-bound discovery wrapper.

The v1.0 base discovery logic (taxonomy/classifier/output construction) is
reused unchanged. This wrapper changes only pagination failure semantics:
reaching a pre-frozen bound records truncation telemetry and returns the
lower-bound candidates already observed instead of claiming archive failure.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w2c_performance_blind_discovery as base

PROTOCOL_PATH = Path("registry/w2c_discovery_protocol_v2_0.json")
TELEMETRY_PATH = Path("registry/w2c_discovery_pagination_telemetry.json")
EXPECTED_PROTOCOL_VERSION = "W2C-DISC-v2.0"

protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
assert protocol["version"] == EXPECTED_PROTOCOL_VERSION
assert protocol["performance_blind"] is True
assert protocol["lineage"]["family_counts_opened_before_v2"] is False
pag = protocol["pagination"]
telemetry: list[dict] = []

base.EXPECTED_PROTOCOL_VERSION = EXPECTED_PROTOCOL_VERSION


def _route_for_keyset(params: dict) -> str:
    if "title_search" in params:
        return "TITLE_SEARCH_KEYSET"
    if "tag_slug" in params:
        return "TAG_RELATED_KEYSET"
    if "series_id" in params:
        return "SERIES_KEYSET"
    return "BROAD_CLOSED_EVENT_CONTEXT"


def bounded_keyset(params: dict, _generic_max_pages: int):
    route = _route_for_keyset(params)
    cap = pag["broad_keyset_max_pages"] if route == "BROAD_CLOSED_EVENT_CONTEXT" else pag["targeted_keyset_max_pages"]
    events: list[dict] = []
    seen: set[str] = set()
    cursor = None
    raw_rows = 0
    complete = False
    pages_used = 0
    for page in range(cap):
        q = dict(params)
        if cursor:
            q["after_cursor"] = cursor
        payload = base.fetch_json("/events/keyset", q)
        batch = payload.get("events") or []
        pages_used = page + 1
        raw_rows += len(batch)
        for event in batch:
            eid = str(event.get("id") or "")
            if eid and eid not in seen:
                seen.add(eid)
                events.append(event)
        nxt = payload.get("next_cursor")
        if not batch or not nxt:
            complete = True
            cursor = nxt
            break
        if nxt == cursor:
            raise RuntimeError(f"non-advancing keyset cursor on {route}")
        cursor = nxt
    truncated = not complete and bool(cursor)
    telemetry.append({
        "channel": "KEYSET",
        "route": route,
        "title_search": str(params.get("title_search") or ""),
        "tag_slug": str(params.get("tag_slug") or ""),
        "series_id": str(params.get("series_id") or ""),
        "page_cap": cap,
        "pages_used": pages_used,
        "raw_rows": raw_rows,
        "unique_events": len(events),
        "complete_within_bound": complete,
        "truncated": truncated,
        "remaining_cursor": bool(cursor) if truncated else False,
        "count_semantics": "LOWER_BOUND" if truncated else "COMPLETE_WITHIN_ROUTE_BOUND"
    })
    return events


def bounded_public_search(q: str, limit: int, _max_pages: int):
    events: list[dict] = []
    tags: list[dict] = []
    seen_e: set[str] = set()
    seen_t: set[str] = set()
    has_more = False
    pages_used = 0
    for page in range(1, pag["public_search_max_pages"] + 1):
        payload = base.fetch_json("/public-search", {
            "q": q,
            "events_status": "closed",
            "limit_per_type": limit,
            "page": page,
            "keep_closed_markets": 1,
            "search_tags": "true",
            "search_profiles": "false"
        })
        pages_used = page
        for event in payload.get("events") or []:
            eid = str(event.get("id") or "")
            if eid and eid not in seen_e:
                seen_e.add(eid)
                events.append(event)
        for tag in payload.get("tags") or []:
            slug = str(tag.get("slug") or "")
            if slug and slug not in seen_t:
                seen_t.add(slug)
                tags.append(tag)
        has_more = bool((payload.get("pagination") or {}).get("hasMore"))
        if not has_more:
            break
    telemetry.append({
        "channel": "PUBLIC_SEARCH",
        "route": "FROZEN_PUBLIC_SEARCH",
        "query": q,
        "page_cap": pag["public_search_max_pages"],
        "pages_used": pages_used,
        "unique_events": len(events),
        "unique_tags": len(tags),
        "complete_within_bound": not has_more,
        "truncated": has_more,
        "count_semantics": "LOWER_BOUND" if has_more else "COMPLETE_WITHIN_ROUTE_BOUND"
    })
    return events, tags


def bounded_list_series(limit: int, _max_pages: int):
    out: list[dict] = []
    full_last_page = False
    pages_used = 0
    for page in range(pag["series_max_pages"]):
        batch = base.fetch_json("/series", {"limit": limit, "offset": page * limit}) or []
        if not isinstance(batch, list):
            raise RuntimeError("unexpected /series response")
        pages_used = page + 1
        out.extend(batch)
        full_last_page = len(batch) == limit
        if len(batch) < limit:
            full_last_page = False
            break
    telemetry.append({
        "channel": "SERIES",
        "route": "SERIES_CATALOG",
        "page_cap": pag["series_max_pages"],
        "pages_used": pages_used,
        "raw_series": len(out),
        "complete_within_bound": not full_last_page,
        "truncated": full_last_page,
        "count_semantics": "LOWER_BOUND" if full_last_page else "COMPLETE_WITHIN_ROUTE_BOUND"
    })
    return out


base.keyset = bounded_keyset
base.public_search = bounded_public_search
base.list_series = bounded_list_series


def main() -> None:
    sys.argv = [sys.argv[0], "--protocol", str(PROTOCOL_PATH)] + sys.argv[1:]
    base.main()

    telemetry_doc = {
        "artifact": "W2C_DISCOVERY_PAGINATION_TELEMETRY",
        "version": "W2C-PAG-v2.0",
        "protocol_version": EXPECTED_PROTOCOL_VERSION,
        "performance_blind": True,
        "science_reopened": False,
        "routes": telemetry,
        "route_count": len(telemetry),
        "truncated_route_count": sum(1 for x in telemetry if x.get("truncated")),
        "broad_archive_exhaustion_required": False,
        "interpretation": "All truncated route counts are lower bounds and cannot establish population completeness or family absence."
    }
    TELEMETRY_PATH.write_text(json.dumps(telemetry_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    meta_path = Path("registry/w2c_discovery_summary.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["bounded_lower_bound_discovery"] = True
    meta["archive_exhaustion_required"] = False
    meta["pagination_telemetry"] = {
        "path": str(TELEMETRY_PATH),
        "sha256": hashlib.sha256(TELEMETRY_PATH.read_bytes()).hexdigest(),
        "route_count": telemetry_doc["route_count"],
        "truncated_route_count": telemetry_doc["truncated_route_count"]
    }
    meta["interpretation"] = "Lower-bound candidate discovery only. Manual validation is mandatory; no IAS, F1-F9 or W3 selection is authorized. Truncated routes cannot prove absence or completeness."
    meta["limitations"] = list(meta.get("limitations") or []) + [
        "W2C-DISC-v2.0 intentionally bounds archive/query pagination and records truncation rather than requiring archive exhaustion.",
        "Candidate counts from truncated routes are lower bounds, not population estimates."
    ]
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

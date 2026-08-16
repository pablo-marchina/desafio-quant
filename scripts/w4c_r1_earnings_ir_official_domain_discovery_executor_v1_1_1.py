#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"

IMPL_V11 = ROOT / "scripts/w4c_r1_earnings_ir_official_domain_discovery_executor_v1_1.py"
PROTOCOL_V111 = REG / "w4c_r1_earnings_ir_official_domain_discovery_protocol_v1_1_1.json"
FREEZE_V111 = REG / "w4c_r1_earnings_ir_official_domain_discovery_executor_freeze_v1_1_1.json"
SAMPLE = REG / "w4c_r1_earnings_ir_probe_sample_v1.json"
TICKER_PROFILE = REG / "w4c_r1_earnings_ticker_profile_v1.json"

OUT_RESOLUTION = REG / "w4c_r1_earnings_ir_official_domain_resolution_manifest_v1_1_1.csv.gz"
OUT_NAV = REG / "w4c_r1_earnings_ir_official_domain_navigation_manifest_v1_1_1.csv.gz"
OUT_BODY = REG / "w4c_r1_earnings_ir_official_domain_body_manifest_v1_1_1.csv.gz"
OUT_SUMMARY = REG / "w4c_r1_earnings_ir_official_domain_capacity_summary_v1_1_1.json"
OUT_EXEC = REG / "w4c_r1_earnings_ir_official_domain_execution_manifest_v1_1_1.json"

EXECUTE_ENV = "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_V1_1_1_EXECUTE"
EXECUTE_TOKEN = "YES_FROZEN_OFFICIAL_DOMAIN_V1_1_1_PROBE"
VALIDATE_ENV = "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_V1_1_1_VALIDATE_ONLY"

MAX_CANDIDATES = 8
REQUEST_TIMEOUT_SECONDS = 5
WDQS_TIMEOUT_SECONDS = 20
MAX_BYTES = 1_000_000

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36 "
    "desafio-quant-w4c-r1-eir-odd-v1.1.1"
)

SPEC = importlib.util.spec_from_file_location("w4c_r1_eir_odd_v1_1_impl", IMPL_V11)
assert SPEC and SPEC.loader
impl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(impl)
base = impl.base

PATH_TEMPLATES_BOUNDED = (
    "/investors",
    "/investor-relations",
    "/ir",
    "/newsroom",
    "/news-releases",
    "/press-releases",
    "/investors/news-events/press-releases",
    "/investor-relations/news-events/press-releases",
    "/investors/financial-information/quarterly-results",
    "/investor-relations/financial-information/quarterly-results",
)

SUBDOMAIN_HINTS = ("investors", "ir")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return base.sha256_bytes(data)


def norm_host(url: str) -> str:
    return base.norm_host(url)


def allowed_host(url: str, official_host: str) -> bool:
    return base.allowed_host(url, official_host)


def is_ir_candidate(url: str) -> bool:
    return impl.is_ir_candidate(url)


def _add_url(out: list[str], url: str, official_host: str) -> None:
    if not url:
        return
    url = url.split("#", 1)[0]
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        return
    if allowed_host(url, official_host) and url not in out:
        out.append(url)


def http_get_bounded(url: str, max_bytes: int = MAX_BYTES, attempts: int = 1) -> dict:
    timeout_seconds = WDQS_TIMEOUT_SECONDS if "query.wikidata.org" in url else REQUEST_TIMEOUT_SECONDS
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,application/json,*/*;q=0.1",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    last = {"status": 0, "body": b"", "content_type": "", "final_url": url, "attempts": 0, "error_class": "NOT_ATTEMPTED"}
    for attempt in range(1, max(1, min(attempts, 1)) + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                body = response.read(max_bytes + 1)
                return {
                    "status": int(response.status),
                    "body": body[:max_bytes],
                    "content_type": str(response.headers.get("Content-Type", "")),
                    "final_url": str(response.geturl()),
                    "attempts": attempt,
                    "error_class": "",
                }
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read(max_bytes)
            except Exception:
                body = b""
            return {
                "status": int(exc.code),
                "body": body,
                "content_type": str(exc.headers.get("Content-Type", "")),
                "final_url": str(exc.geturl()),
                "attempts": attempt,
                "error_class": f"HTTP_{exc.code}",
            }
        except Exception as exc:
            last = {
                "status": 0,
                "body": b"",
                "content_type": "",
                "final_url": url,
                "attempts": attempt,
                "error_class": type(exc).__name__,
            }
    return last


def sparql_query_bounded(tickers: list[str]) -> dict[str, list[dict[str, str]]]:
    old = impl.http_get_v11
    impl.http_get_v11 = http_get_bounded
    try:
        return impl.sparql_query_v11(tickers)
    finally:
        impl.http_get_v11 = old


def candidate_urls_bounded(homepage: str, official_host: str) -> list[str]:
    candidates: list[str] = []
    root = homepage.rstrip("/")
    parsed = urllib.parse.urlsplit(homepage)
    scheme = parsed.scheme or "https"

    _add_url(candidates, root, official_host)
    for path in PATH_TEMPLATES_BOUNDED:
        _add_url(candidates, root + path, official_host)
        if len(candidates) >= MAX_CANDIDATES:
            return candidates[:MAX_CANDIDATES]

    for sub in SUBDOMAIN_HINTS:
        _add_url(candidates, f"{scheme}://{sub}.{official_host}", official_host)
        if len(candidates) >= MAX_CANDIDATES:
            return candidates[:MAX_CANDIDATES]

    # One-hop official-domain expansion is bounded and best-effort only. A timeout here
    # is a closed failure for navigation discovery, never a blocker for materialization.
    for entry in list(candidates[:3]):
        result = http_get_bounded(entry, max_bytes=MAX_BYTES, attempts=1)
        if result["status"] != 200 or not result["body"]:
            continue
        for link in base.extract_links(result["body"], entry, official_host):
            if is_ir_candidate(link):
                _add_url(candidates, link, official_host)
                if len(candidates) >= MAX_CANDIDATES:
                    return candidates[:MAX_CANDIDATES]
    return candidates[:MAX_CANDIDATES]


def sample_tickers(profile: dict, sample: dict) -> dict[str, str]:
    tickers = impl.repaired_ticker_map(profile)
    sample_ids = {row["exact_group_id"] for row in sample["rows"]}
    if len(sample_ids & set(tickers)) != 40:
        raise RuntimeError(f"missing_ticker_profile_after_repair={40 - len(sample_ids & set(tickers))}")
    return tickers


def validate_inputs() -> dict:
    protocol = load_json(PROTOCOL_V111)
    sample = load_json(SAMPLE)
    profile = load_json(TICKER_PROFILE)

    assert protocol["version"] == "W4C-R1-EIR-ODD-v1.1.1"
    assert protocol["status"] == "FROZEN_PROTOCOL_PRE_EXTERNAL_REQUEST"
    assert protocol["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_DISCOVERY_PROTOCOL_V1_1_1_FROZEN_PRE_REQUEST"
    assert protocol["sample_binding"]["sample_size"] == 40
    assert protocol["sample_binding"]["selection_change_allowed"] is False
    assert protocol["sample_binding"]["resampling_allowed"] is False
    assert protocol["capacity_gate"]["thresholds_unchanged_from_v1_0"] is True
    assert protocol["scientific_firewall"]["earnings_numeric_outcomes_allowed"] is False
    assert protocol["scientific_firewall"]["n_final_backtestable_authorized"] is False

    assert sample["status"] == "FROZEN_SAMPLE_PRE_EXTERNAL_REQUEST"
    assert sample["sample_size"] == 40 and len(sample["rows"]) == 40
    assert sample["external_probe_requests_performed"] is False
    assert sample["issuer_ir_lookup_performed"] is False
    assert sample["event_truth_verification_authorized"] is False

    assert profile["issuer_ir_lookup_performed"] is False
    assert profile["new_external_source_reads"] is False
    assert profile["queue_groups"] == 1355

    if FREEZE_V111.exists():
        freeze = load_json(FREEZE_V111)
        assert freeze["status"] == "FROZEN_EXECUTOR_PRE_EXTERNAL_REQUEST"
        assert freeze["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTOR_V1_1_1_FROZEN_PRE_REQUEST"
        assert freeze["external_requests_performed_before_freeze"] is False
        assert freeze["sample_selection_changed"] is False
        assert freeze["thresholds_changed"] is False

    sample_tickers(profile, sample)
    return {"protocol": protocol, "sample": sample, "profile": profile}


def write_gzip(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def execute() -> int:
    ctx = validate_inputs()
    sample = ctx["sample"]
    profile = ctx["profile"]
    tickers = sample_tickers(profile, sample)
    groups = {row["exact_group_id"]: row for row in sample["rows"]}
    ticker_values = [tickers[gid] for gid in groups]

    resolution_rows: list[dict] = []
    nav_rows: list[dict] = []
    body_rows: list[dict] = []
    successes: list[dict] = []

    resolved = sparql_query_bounded(ticker_values)

    for gid, row in sorted(groups.items()):
        year = str(row["year"])
        ticker = tickers[gid]
        issuer_display, issuer_raw = base.issuer_parts(row["pretruth_subject_key"], ticker)
        tokens = base.core_tokens(issuer_raw)
        matches = resolved.get(ticker, [])
        unique_items = {(m["item"], m["website"]) for m in matches if m.get("item") and m.get("website")}
        if len(unique_items) != 1:
            resolution_rows.append({
                "exact_group_id": gid,
                "year": year,
                "ticker": ticker,
                "resolution_status": "UNRESOLVED_UNIQUE_ENTITY_REQUIRED",
                "candidate_entity_count": len(unique_items),
                "official_host": "",
                "official_website": "",
            })
            continue

        item, website = next(iter(unique_items))
        official_host = norm_host(website)
        if not official_host:
            resolution_rows.append({
                "exact_group_id": gid,
                "year": year,
                "ticker": ticker,
                "resolution_status": "UNRESOLVED_INVALID_OFFICIAL_WEBSITE",
                "candidate_entity_count": 1,
                "official_host": "",
                "official_website": website,
            })
            continue

        resolution_rows.append({
            "exact_group_id": gid,
            "year": year,
            "ticker": ticker,
            "resolution_status": "RESOLVED_UNIQUE_WIKIDATA_ENTITY_AND_P856",
            "candidate_entity_count": 1,
            "official_host": official_host,
            "official_website": website,
        })

        candidates = candidate_urls_bounded(website, official_host)
        for rank, candidate in enumerate(candidates, start=1):
            nav_rows.append({
                "exact_group_id": gid,
                "year": year,
                "ticker": ticker,
                "candidate_rank": rank,
                "candidate_url_sha256": sha256_bytes(candidate.encode()),
                "candidate_host": norm_host(candidate),
                "official_host": official_host,
                "path_ir_signal": is_ir_candidate(candidate),
            })
            if not allowed_host(candidate, official_host):
                continue
            result = http_get_bounded(candidate, max_bytes=MAX_BYTES, attempts=1)
            body = result["body"]
            bind, matched = base.identity_bind(body, result["content_type"], tokens, issuer_display)
            body_rows.append({
                "exact_group_id": gid,
                "year": year,
                "candidate_rank": rank,
                "candidate_url_sha256": sha256_bytes(candidate.encode()),
                "final_url_sha256": sha256_bytes(result["final_url"].encode()),
                "official_host": official_host,
                "final_host": norm_host(result["final_url"]),
                "http_status": result["status"],
                "attempts": result["attempts"],
                "error_class": result["error_class"],
                "content_type": result["content_type"],
                "body_sha256": sha256_bytes(body) if body else "",
                "identity_bindable": bind,
                "matched_identity_token_count": len(matched),
            })
            if result["status"] == 200 and bind:
                successes.append({"exact_group_id": gid, "year": year, "candidate_rank": rank})
                break

    total = len({x["exact_group_id"] for x in successes})
    y25 = sum(x["year"] == "2025" for x in successes)
    y26 = sum(x["year"] == "2026" for x in successes)
    gate = base.decision(total, y25, y26)

    write_gzip(OUT_RESOLUTION, resolution_rows, ["exact_group_id", "year", "ticker", "resolution_status", "candidate_entity_count", "official_host", "official_website"])
    write_gzip(OUT_NAV, nav_rows, ["exact_group_id", "year", "ticker", "candidate_rank", "candidate_url_sha256", "candidate_host", "official_host", "path_ir_signal"])
    write_gzip(OUT_BODY, body_rows, ["exact_group_id", "year", "candidate_rank", "candidate_url_sha256", "final_url_sha256", "official_host", "final_host", "http_status", "attempts", "error_class", "content_type", "body_sha256", "identity_bindable", "matched_identity_token_count"])

    summary = {
        "artifact": "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_CAPACITY_SUMMARY",
        "version": "W4C-R1-EIR-ODD-RESULT-v1.1.1",
        "protocol_version": "W4C-R1-EIR-ODD-v1.1.1",
        "sample_size": 40,
        "probe_success_total": total,
        "probe_success_by_year": {"2025": y25, "2026": y26},
        "unique_wikidata_resolution_total": sum(r["resolution_status"] == "RESOLVED_UNIQUE_WIKIDATA_ENTITY_AND_P856" for r in resolution_rows),
        "candidate_navigation_rows": len(nav_rows),
        "official_body_attempt_rows": len(body_rows),
        "capacity_decision": gate,
        "amendment_scope": "transport_bounding_only",
        "max_candidates_per_resolved_group": MAX_CANDIDATES,
        "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "wdqs_timeout_seconds": WDQS_TIMEOUT_SECONDS,
        "thresholds_unchanged_from_v1_0": True,
        "outcome_reveal_authorized": False,
        "n_final_backtestable_authorized": False,
        "gate_decision": "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_CAPACITY_PROBE_V1_1_1_MATERIALIZED",
    }
    write_json(OUT_SUMMARY, summary)

    execution = {
        "artifact": "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTION_MANIFEST",
        "protocol": PROTOCOL_V111.name,
        "sample": SAMPLE.name,
        "executor": Path(__file__).name,
        "result_version": "W4C-R1-EIR-ODD-RESULT-v1.1.1",
        "sample_size": 40,
        "external_requests_performed": True,
        "capacity_decision": gate,
        "amendment_scope": "transport_bounding_only",
        "transport_bounding": {
            "max_candidates_per_resolved_group": MAX_CANDIDATES,
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "wdqs_timeout_seconds": WDQS_TIMEOUT_SECONDS,
            "http_attempts_per_candidate": 1,
            "recursive_sitemap_crawl_enabled": False,
            "timeout_or_transport_error_policy": "FAIL_CLOSED_NON_SUCCESS_AND_MATERIALIZE_OUTPUTS",
        },
        "outputs": {
            "resolution_sha256": sha256_bytes(OUT_RESOLUTION.read_bytes()),
            "navigation_sha256": sha256_bytes(OUT_NAV.read_bytes()),
            "official_body_sha256": sha256_bytes(OUT_BODY.read_bytes()),
            "summary_sha256": sha256_bytes(OUT_SUMMARY.read_bytes()),
        },
        "scientific_firewall": {
            "earnings_numeric_outcomes_read": False,
            "prediction_market_settlement_read": False,
            "realized_returns_read": False,
            "argos_pnl_read": False,
            "event_truth_verification_used": False,
            "n_final_backtestable_authorized": False,
        },
    }
    write_json(OUT_EXEC, execution)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def validate_only() -> int:
    validate_inputs()
    print("PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTOR_V1_1_1_VALIDATE_ONLY")
    print("sample_groups=40")
    print("external_requests_performed=false")
    print(f"max_candidates_per_resolved_group={MAX_CANDIDATES}")
    print(f"request_timeout_seconds={REQUEST_TIMEOUT_SECONDS}")
    return 0


def main() -> int:
    if os.environ.get(VALIDATE_ENV) == "YES":
        return validate_only()
    validate_inputs()
    if os.environ.get(EXECUTE_ENV) != EXECUTE_TOKEN:
        raise SystemExit("execution authorization missing")
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())

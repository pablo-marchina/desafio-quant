#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
IMPL = ROOT / "scripts/w4c_r1_earnings_ir_official_domain_discovery_executor_v1_2.py"
AUTH = REG / "w4c_r1_earnings_ir_official_domain_full_expansion_authorization_v1.json"
V12_SUMMARY = REG / "w4c_r1_earnings_ir_official_domain_capacity_summary_v1_2.json"
QUEUE = REG / "w4c_r1_earnings_ir_queue_v1.csv.gz"
PROFILE = REG / "w4c_r1_earnings_ticker_profile_v1.json"
REPAIR = REG / "w4c_r1_earnings_ir_input_repair_v1.json"

OUT_RESOLUTION = REG / "w4c_r1_earnings_ir_official_domain_full_resolution_manifest_v1.csv.gz"
OUT_NAV = REG / "w4c_r1_earnings_ir_official_domain_full_navigation_manifest_v1.csv.gz"
OUT_BODY = REG / "w4c_r1_earnings_ir_official_domain_full_body_manifest_v1.csv.gz"
OUT_SUMMARY = REG / "w4c_r1_earnings_ir_official_domain_full_expansion_summary_v1.json"
OUT_EXEC = REG / "w4c_r1_earnings_ir_official_domain_full_execution_manifest_v1.json"

EXECUTE_ENV = "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FULL_EXECUTE"
EXECUTE_TOKEN = "YES_FROZEN_OFFICIAL_DOMAIN_FULL_1355_EXPANSION"
VALIDATE_ENV = "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FULL_VALIDATE_ONLY"

spec = importlib.util.spec_from_file_location("w4c_r1_eir_odd_v12", IMPL)
assert spec and spec.loader
v12 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v12)
impl = v12.impl
base = v12.base

# Reuse v1.2 bounded transport policy.
impl.MAX_CANDIDATES = 12
impl.REQUEST_TIMEOUT_SECONDS = 8
impl.WDQS_TIMEOUT_SECONDS = 25
impl.UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36 "
    "desafio-quant-w4c-r1-eir-odd-full-v1"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_queue() -> list[dict[str, str]]:
    with gzip.open(QUEUE, "rt", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return rows


def write_gzip(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def ticker_map(profile: dict, repair: dict) -> dict[str, str]:
    out = {
        r["exact_group_id"]: r.get("ticker_candidate", "")
        for r in profile.get("rows", [])
        if r.get("mode") == "UNIQUE_PRE_GAAP_TICKER_CANDIDATE" and r.get("ticker_candidate")
    }
    for r in repair.get("repaired_rows", []):
        if r.get("status") != "PRESERVED_UNRESOLVED_NO_GUESS" and r.get("ticker_candidate"):
            out[r["exact_group_id"]] = r["ticker_candidate"]
    return out


def year_of(row: dict[str, str]) -> str:
    if row.get("year"):
        return str(row["year"])
    for key in ("event_date", "date", "target_date"):
        val = row.get(key, "")
        if len(val) >= 4 and val[:4].isdigit():
            return val[:4]
    return "UNKNOWN"


def subject_of(row: dict[str, str]) -> str:
    return row.get("pretruth_subject_key") or row.get("subject_key") or row.get("canonical_event_id") or ""


def validate_inputs() -> dict:
    auth = load_json(AUTH)
    summary = load_json(V12_SUMMARY)
    profile = load_json(PROFILE)
    repair = load_json(REPAIR)
    queue = read_queue()
    assert auth["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FULL_EXPANSION_AUTHORIZED_OUTCOME_BLIND"
    assert auth["scope"]["expected_queue_groups"] == 1355
    assert auth["scope"]["outcome_reveal_authorized"] is False
    assert auth["scope"]["n_final_backtestable_authorized"] is False
    assert summary["capacity_decision"] == "FULL_ROUTE_TECHNICALLY_VIABLE"
    assert summary["probe_success_total"] >= 24
    assert summary["probe_success_by_year"]["2025"] >= 10
    assert summary["probe_success_by_year"]["2026"] >= 10
    assert summary["outcome_reveal_authorized"] is False
    assert summary["n_final_backtestable_authorized"] is False
    assert profile["issuer_ir_lookup_performed"] is False
    assert profile["new_external_source_reads"] is False
    assert profile["queue_groups"] == 1355
    assert repair["outcome_data_used"] is False
    assert len(queue) == 1355
    gids = [r.get("exact_group_id", "") for r in queue]
    assert len(gids) == len(set(gids)) == 1355
    return {"auth": auth, "summary": summary, "profile": profile, "repair": repair, "queue": queue}


def batch_resolve(tickers: list[str]) -> dict[str, list[dict[str, str]]]:
    resolved: dict[str, list[dict[str, str]]] = {}
    uniq = sorted({t.upper() for t in tickers if t})
    for i in range(0, len(uniq), 80):
        batch = uniq[i:i+80]
        try:
            resolved.update(impl.sparql_query_bounded(batch))
        except Exception:
            for t in batch:
                resolved.setdefault(t, [])
    return resolved


def execute() -> int:
    ctx = validate_inputs()
    qrows = ctx["queue"]
    tmap = ticker_map(ctx["profile"], ctx["repair"])
    tickers = [tmap.get(r["exact_group_id"], "").upper() for r in qrows]
    resolved = batch_resolve(tickers)

    candidate_cache: dict[tuple[str, str], list[str]] = {}
    http_cache: dict[str, dict] = {}
    resolution_rows: list[dict] = []
    nav_rows: list[dict] = []
    body_rows: list[dict] = []
    success_gids: set[str] = set()

    for row in sorted(qrows, key=lambda r: r.get("exact_group_id", "")):
        gid = row["exact_group_id"]
        year = year_of(row)
        subject = subject_of(row)
        ticker = tmap.get(gid, "").upper()
        if not ticker:
            resolution_rows.append({"exact_group_id": gid, "year": year, "ticker": "", "resolution_status": "UNRESOLVED_NO_UNIQUE_PRE_REQUEST_TICKER", "candidate_entity_count": 0, "official_host": "", "official_website": ""})
            continue
        issuer_display, issuer_raw = base.issuer_parts(subject, ticker)
        tokens = base.core_tokens(issuer_raw)
        matches = resolved.get(ticker, [])
        unique_items = {(m.get("item", ""), m.get("website", "")) for m in matches if m.get("item") and m.get("website")}
        if len(unique_items) != 1:
            resolution_rows.append({"exact_group_id": gid, "year": year, "ticker": ticker, "resolution_status": "UNRESOLVED_UNIQUE_ENTITY_REQUIRED", "candidate_entity_count": len(unique_items), "official_host": "", "official_website": ""})
            continue
        item, website = next(iter(unique_items))
        official_host = base.norm_host(website)
        if not official_host:
            resolution_rows.append({"exact_group_id": gid, "year": year, "ticker": ticker, "resolution_status": "UNRESOLVED_INVALID_OFFICIAL_WEBSITE", "candidate_entity_count": 1, "official_host": "", "official_website": website})
            continue
        resolution_rows.append({"exact_group_id": gid, "year": year, "ticker": ticker, "resolution_status": "RESOLVED_UNIQUE_WIKIDATA_ENTITY_AND_P856", "candidate_entity_count": 1, "official_host": official_host, "official_website": website})

        ckey = (website, official_host)
        if ckey not in candidate_cache:
            candidate_cache[ckey] = impl.candidate_urls_bounded(website, official_host)
        for rank, candidate in enumerate(candidate_cache[ckey], start=1):
            nav_rows.append({"exact_group_id": gid, "year": year, "ticker": ticker, "candidate_rank": rank, "candidate_url_sha256": impl.sha256_bytes(candidate.encode()), "candidate_host": base.norm_host(candidate), "official_host": official_host, "path_ir_signal": impl.is_ir_candidate(candidate)})
            if not base.allowed_host(candidate, official_host):
                continue
            cache_hit = candidate in http_cache
            if not cache_hit:
                http_cache[candidate] = impl.http_get_bounded(candidate, max_bytes=impl.MAX_BYTES, attempts=1)
            result = http_cache[candidate]
            body = result["body"]
            bind, matched = base.identity_bind(body, result["content_type"], tokens, issuer_display)
            body_rows.append({"exact_group_id": gid, "year": year, "candidate_rank": rank, "candidate_url_sha256": impl.sha256_bytes(candidate.encode()), "final_url_sha256": impl.sha256_bytes(result["final_url"].encode()), "official_host": official_host, "final_host": base.norm_host(result["final_url"]), "http_status": result["status"], "attempts": result["attempts"], "error_class": result["error_class"], "content_type": result["content_type"], "body_sha256": impl.sha256_bytes(body) if body else "", "identity_bindable": bind, "matched_identity_token_count": len(matched), "cache_hit": cache_hit})
            if result["status"] == 200 and bind:
                success_gids.add(gid)
                break

    write_gzip(OUT_RESOLUTION, resolution_rows, ["exact_group_id", "year", "ticker", "resolution_status", "candidate_entity_count", "official_host", "official_website"])
    write_gzip(OUT_NAV, nav_rows, ["exact_group_id", "year", "ticker", "candidate_rank", "candidate_url_sha256", "candidate_host", "official_host", "path_ir_signal"])
    write_gzip(OUT_BODY, body_rows, ["exact_group_id", "year", "candidate_rank", "candidate_url_sha256", "final_url_sha256", "official_host", "final_host", "http_status", "attempts", "error_class", "content_type", "body_sha256", "identity_bindable", "matched_identity_token_count", "cache_hit"])

    success_by_year = Counter(year_of(r) for r in qrows if r["exact_group_id"] in success_gids)
    resolved_count = sum(r["resolution_status"] == "RESOLVED_UNIQUE_WIKIDATA_ENTITY_AND_P856" for r in resolution_rows)
    summary = {
        "artifact": "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FULL_EXPANSION_SUMMARY",
        "version": "W4C-R1-EIR-ODD-FULL-RESULT-v1.0",
        "date": "2026-08-16",
        "status": "MATERIALIZED_OUTCOME_BLIND_FULL_EXPANSION",
        "input_queue_groups": len(qrows),
        "unique_ticker_candidate_groups": sum(1 for r in qrows if tmap.get(r["exact_group_id"], "")),
        "unique_wikidata_resolution_total": resolved_count,
        "official_body_identity_success_total": len(success_gids),
        "official_body_identity_success_by_year": dict(sorted(success_by_year.items())),
        "resolution_rows": len(resolution_rows),
        "candidate_navigation_rows": len(nav_rows),
        "official_body_attempt_rows": len(body_rows),
        "unique_http_requests_performed": len(http_cache),
        "unique_candidate_sets_materialized": len(candidate_cache),
        "outcome_reveal_authorized": False,
        "n_final_backtestable_authorized": False,
        "backtest_authorized": False,
        "scientific_firewall": {
            "earnings_numeric_outcomes_read": False,
            "prediction_market_settlement_read": False,
            "realized_returns_read": False,
            "argos_pnl_read": False,
            "event_truth_verification_used": False,
            "n_final_backtestable_authorized": False
        },
        "gate_decision": "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FULL_EXPANSION_MATERIALIZED_OUTCOME_BLIND"
    }
    write_json(OUT_SUMMARY, summary)
    execution = {
        "artifact": "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FULL_EXECUTION_MANIFEST",
        "version": "W4C-R1-EIR-ODD-FULL-EXECUTION-v1.0",
        "authorization": AUTH.name,
        "executor": Path(__file__).name,
        "external_requests_performed": True,
        "outputs": {
            "resolution_sha256": impl.sha256_bytes(OUT_RESOLUTION.read_bytes()),
            "navigation_sha256": impl.sha256_bytes(OUT_NAV.read_bytes()),
            "official_body_sha256": impl.sha256_bytes(OUT_BODY.read_bytes()),
            "summary_sha256": impl.sha256_bytes(OUT_SUMMARY.read_bytes())
        },
        "scientific_firewall": summary["scientific_firewall"]
    }
    write_json(OUT_EXEC, execution)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def main() -> int:
    if os.environ.get(VALIDATE_ENV) == "YES":
        ctx = validate_inputs()
        tmap = ticker_map(ctx["profile"], ctx["repair"])
        print("PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FULL_VALIDATE_ONLY")
        print(f"queue_groups={len(ctx['queue'])}")
        print(f"ticker_candidate_groups={sum(1 for r in ctx['queue'] if tmap.get(r['exact_group_id'], ''))}")
        print("external_requests_performed=false")
        return 0
    if os.environ.get(EXECUTE_ENV) != EXECUTE_TOKEN:
        raise SystemExit("execution authorization missing")
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())

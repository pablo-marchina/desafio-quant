#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
PROTOCOL = REG / "w4c_r1_earnings_ir_official_domain_discovery_protocol_v1.json"
SAMPLE = REG / "w4c_r1_earnings_ir_probe_sample_v1.json"
TICKER_PROFILE = REG / "w4c_r1_earnings_ticker_profile_v1.json"
FREEZE = REG / "w4c_r1_earnings_ir_official_domain_discovery_executor_freeze_v1.json"
OUT_RESOLUTION = REG / "w4c_r1_earnings_ir_official_domain_resolution_manifest_v1.csv.gz"
OUT_NAV = REG / "w4c_r1_earnings_ir_official_domain_navigation_manifest_v1.csv.gz"
OUT_BODY = REG / "w4c_r1_earnings_ir_official_domain_body_manifest_v1.csv.gz"
OUT_SUMMARY = REG / "w4c_r1_earnings_ir_official_domain_capacity_summary_v1.json"
OUT_EXEC = REG / "w4c_r1_earnings_ir_official_domain_execution_manifest_v1.json"

UA = "desafio-quant-w4c-r1-earnings-ir-official-domain/1.0"
EXECUTE_ENV = "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTE"
EXECUTE_TOKEN = "YES_FROZEN_OFFICIAL_DOMAIN_PROBE"
WDQS = "https://query.wikidata.org/sparql"
IR_HINTS = ("investor", "investor-relations", "/ir", "ir.", "earnings", "financial-results", "quarterly-results", "results", "newsroom", "press-release", "events-and-presentations")
FIXED_PATHS = ("/investors", "/investor-relations", "/ir", "/newsroom", "/news", "/earnings", "/financial-results", "/quarterly-results", "/results", "/events-and-presentations")
MAX_BYTES = 5_000_000
MAX_CANDIDATES = 12


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def norm_host(url: str) -> str:
    host = (urllib.parse.urlsplit(url).hostname or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def allowed_host(url: str, official_host: str) -> bool:
    host = norm_host(url)
    return bool(host) and (host == official_host or host.endswith("." + official_host))


def normalize_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def issuer_parts(subject_key: str, ticker: str) -> tuple[str, list[str]]:
    tokens = [t for t in subject_key.lower().split("_") if t]
    semantic = {"nongaap", "gaap", "up", "its", "cash"}
    cut = len(tokens)
    for i, token in enumerate(tokens):
        if token in semantic:
            cut = i
            break
    prefix = tokens[:cut]
    if ticker and len(prefix) > 1 and prefix[-1] == ticker.lower():
        prefix = prefix[:-1]
    prefix = [t for t in prefix if not re.fullmatch(r"(?:neg)?\d+pt\d+", t)]
    return " ".join(prefix).strip(), prefix


def core_tokens(tokens: Iterable[str]) -> list[str]:
    generic = {"inc", "incorporated", "corp", "corporation", "company", "co", "ltd", "limited", "plc", "holdings", "holding", "group"}
    clean = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in tokens]
    return [t for t in clean if len(t) >= 3 and t not in generic]


def ticker_map(profile: dict) -> dict[str, str]:
    out = {}
    for row in profile["rows"]:
        ticker = str(row.get("ticker_candidate", "")).strip().upper()
        if row.get("mode") == "UNIQUE_PRE_GAAP_TICKER_CANDIDATE" and ticker:
            out[row["exact_group_id"]] = ticker
    return out


def validate_inputs() -> dict:
    protocol = load(PROTOCOL)
    sample = load(SAMPLE)
    profile = load(TICKER_PROFILE)
    assert protocol["version"] == "W4C-R1-EIR-ODD-v1.0"
    assert protocol["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_DISCOVERY_PROTOCOL_FROZEN_PRE_REQUEST"
    assert protocol["firewall"]["earnings_numeric_outcomes_allowed"] is False
    assert protocol["firewall"]["n_final_backtestable_authorized"] is False
    assert sample["status"] == "FROZEN_SAMPLE_PRE_EXTERNAL_REQUEST"
    assert sample["sample_size"] == 40 and len(sample["rows"]) == 40
    assert sample["external_probe_requests_performed"] is False
    assert sample["issuer_ir_lookup_performed"] is False
    assert sample["event_truth_verification_authorized"] is False
    assert profile["issuer_ir_lookup_performed"] is False
    assert profile["new_external_source_reads"] is False
    assert profile["queue_groups"] == 1355
    if FREEZE.exists():
        freeze = load(FREEZE)
        assert freeze["status"] == "FROZEN_EXECUTOR_PRE_EXTERNAL_REQUEST"
        for item in freeze["bound_files"]:
            path = ROOT / item["path"]
            assert git_blob_sha(path) == item["git_blob_sha"], item["path"]
    return {"protocol": protocol, "sample": sample, "profile": profile}


def http_get(url: str, max_bytes: int = MAX_BYTES, attempts: int = 3) -> dict:
    last = {"status": 0, "body": b"", "content_type": "", "final_url": url, "attempts": 0, "error_class": ""}
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,*/*;q=0.1", "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                body = response.read(max_bytes + 1)
                last = {"status": int(response.status), "body": body[:max_bytes], "content_type": str(response.headers.get("Content-Type", "")), "final_url": str(response.geturl()), "attempts": attempt, "error_class": ""}
        except urllib.error.HTTPError as exc:
            last = {"status": int(exc.code), "body": exc.read(max_bytes), "content_type": str(exc.headers.get("Content-Type", "")), "final_url": str(exc.geturl()), "attempts": attempt, "error_class": f"HTTP_{exc.code}"}
        except Exception as exc:
            last = {"status": 0, "body": b"", "content_type": "", "final_url": url, "attempts": attempt, "error_class": type(exc).__name__}
        if last["status"] == 200 and last["body"]:
            return last
        if last["status"] not in {0, 429} and not 500 <= last["status"] <= 599:
            return last
        if attempt < attempts:
            time.sleep(float(attempt))
    return last


def sparql_query(tickers: list[str]) -> dict[str, list[dict[str, str]]]:
    values = " ".join(json.dumps(t) for t in sorted(set(tickers)))
    query = f"""
SELECT DISTINCT ?ticker ?item ?itemLabel ?website WHERE {{
  VALUES ?ticker {{ {values} }}
  {{ ?item wdt:P249 ?ticker . }}
  UNION
  {{ ?item p:P414 ?stmt . ?stmt pq:P249 ?ticker . }}
  ?item wdt:P856 ?website .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en\". }}
}}
"""
    url = WDQS + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    result = http_get(url, max_bytes=2_000_000, attempts=3)
    if result["status"] != 200:
        raise RuntimeError(f"WDQS_HTTP_{result['status']}")
    payload = json.loads(result["body"].decode("utf-8"))
    out: dict[str, list[dict[str, str]]] = {t: [] for t in tickers}
    for binding in payload.get("results", {}).get("bindings", []):
        ticker = binding.get("ticker", {}).get("value", "").upper()
        if ticker in out:
            out[ticker].append({
                "item": binding.get("item", {}).get("value", ""),
                "label": binding.get("itemLabel", {}).get("value", ""),
                "website": binding.get("website", {}).get("value", ""),
            })
    return out


def extract_locs(body: bytes) -> list[str]:
    text = body.decode("utf-8", errors="replace")
    return [html.unescape(x.strip()) for x in re.findall(r"<loc[^>]*>(.*?)</loc>", text, flags=re.I | re.S) if x.strip()]


def extract_links(body: bytes, base_url: str, official_host: str) -> list[str]:
    text = body.decode("utf-8", errors="replace")
    urls = []
    for href in re.findall(r"(?:href|data-href)=[\"']([^\"']+)[\"']", text, flags=re.I):
        url = urllib.parse.urljoin(base_url, html.unescape(href))
        if urllib.parse.urlsplit(url).scheme in {"http", "https"} and allowed_host(url, official_host):
            urls.append(url.split("#", 1)[0])
    return list(dict.fromkeys(urls))


def is_ir_candidate(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in IR_HINTS)


def candidate_urls(homepage: str, official_host: str) -> list[str]:
    candidates: list[str] = []
    root = homepage.rstrip("/")
    robots = urllib.parse.urljoin(root + "/", "robots.txt")
    r = http_get(robots, max_bytes=500_000)
    sitemaps = []
    if r["status"] == 200:
        sitemaps.extend(re.findall(r"(?im)^\s*sitemap:\s*(\S+)\s*$", r["body"].decode("utf-8", errors="replace")))
    sitemaps.append(urllib.parse.urljoin(root + "/", "sitemap.xml"))
    seen_maps = set()
    for sitemap in sitemaps:
        if sitemap in seen_maps or not allowed_host(sitemap, official_host):
            continue
        seen_maps.add(sitemap)
        s = http_get(sitemap, max_bytes=2_000_000)
        if s["status"] == 200:
            for loc in extract_locs(s["body"]):
                if allowed_host(loc, official_host) and is_ir_candidate(loc):
                    candidates.append(loc)
    h = http_get(homepage, max_bytes=MAX_BYTES)
    if h["status"] == 200:
        for link in extract_links(h["body"], homepage, official_host):
            if is_ir_candidate(link):
                candidates.append(link)
    for path in FIXED_PATHS:
        candidates.append(root + path)
    return list(dict.fromkeys(candidates))[:MAX_CANDIDATES]


def identity_bind(body: bytes, content_type: str, tokens: list[str], issuer_display: str) -> tuple[bool, list[str]]:
    if "html" not in content_type.lower() and "xhtml" not in content_type.lower():
        return False, []
    text = normalize_text(body.decode("utf-8", errors="replace"))
    matched = [t for t in tokens if re.search(rf"\b{re.escape(t)}\b", text)]
    phrase = re.sub(r"\s+", " ", issuer_display.lower()).strip()
    needed = 1 if len(tokens) <= 1 else max(2, (len(tokens) + 1) // 2)
    return bool((len(phrase) >= 4 and phrase in text) or len(matched) >= needed), matched


def write_gzip(path: Path, rows: list[dict], fields: list[str]) -> None:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fields})
    with path.open("wb") as fh:
        with gzip.GzipFile(filename=path.stem, mode="wb", fileobj=fh, mtime=0) as gz:
            gz.write(buf.getvalue().encode("utf-8"))


def decision(total: int, y25: int, y26: int) -> str:
    if total >= 24 and y25 >= 10 and y26 >= 10:
        return "FULL_ROUTE_TECHNICALLY_VIABLE"
    if total >= 12 and y25 >= 5 and y26 >= 5:
        return "CONDITIONAL_ROUTE"
    return "ROUTE_INFEASIBLE_CURRENT_PROTOCOL"


def execute() -> int:
    ctx = validate_inputs()
    sample = ctx["sample"]
    profile = ctx["profile"]
    tickers = ticker_map(profile)
    groups = {r["exact_group_id"]: r for r in sample["rows"]}
    ticker_values = [tickers[g] for g in groups if g in tickers]
    if len(ticker_values) != 40:
        raise RuntimeError(f"missing_unique_ticker_profile_for_sample={40-len(ticker_values)}")

    resolution_rows = []
    nav_rows = []
    body_rows = []
    successes = []

    resolved = sparql_query(ticker_values)
    for gid, row in sorted(groups.items()):
        ticker = tickers[gid]
        issuer_display, issuer_raw = issuer_parts(row["pretruth_subject_key"], ticker)
        tokens = core_tokens(issuer_raw)
        matches = resolved.get(ticker, [])
        unique_items = {(m["item"], m["website"]) for m in matches if m["item"] and m["website"]}
        if len(unique_items) != 1:
            resolution_rows.append({"exact_group_id": gid, "year": row["year"], "ticker": ticker, "resolution_status": "UNRESOLVED_UNIQUE_ENTITY_REQUIRED", "candidate_entity_count": len(unique_items), "official_host": "", "official_website": ""})
            continue
        item, website = next(iter(unique_items))
        official_host = norm_host(website)
        if not official_host:
            resolution_rows.append({"exact_group_id": gid, "year": row["year"], "ticker": ticker, "resolution_status": "UNRESOLVED_INVALID_OFFICIAL_WEBSITE", "candidate_entity_count": 1, "official_host": "", "official_website": website})
            continue
        resolution_rows.append({"exact_group_id": gid, "year": row["year"], "ticker": ticker, "resolution_status": "RESOLVED_UNIQUE_WIKIDATA_ENTITY_AND_P856", "candidate_entity_count": 1, "official_host": official_host, "official_website": website})
        candidates = candidate_urls(website, official_host)
        for rank, candidate in enumerate(candidates, start=1):
            nav_rows.append({"exact_group_id": gid, "year": row["year"], "ticker": ticker, "candidate_rank": rank, "candidate_url_sha256": sha256_bytes(candidate.encode()), "candidate_host": norm_host(candidate), "official_host": official_host, "path_ir_signal": is_ir_candidate(candidate)})
            if not allowed_host(candidate, official_host):
                continue
            result = http_get(candidate, max_bytes=MAX_BYTES, attempts=3)
            body = result["body"]
            bind, matched = identity_bind(body, result["content_type"], tokens, issuer_display)
            body_rows.append({"exact_group_id": gid, "year": row["year"], "candidate_rank": rank, "candidate_url_sha256": sha256_bytes(candidate.encode()), "final_url_sha256": sha256_bytes(result["final_url"].encode()), "official_host": official_host, "final_host": norm_host(result["final_url"]), "http_status": result["status"], "attempts": result["attempts"], "error_class": result["error_class"], "content_type": result["content_type"], "body_sha256": sha256_bytes(body) if body else "", "identity_bindable": bind, "matched_identity_token_count": len(matched)})
            if result["status"] == 200 and bind:
                successes.append({"exact_group_id": gid, "year": row["year"], "candidate_rank": rank})
                break

    total = len({x["exact_group_id"] for x in successes})
    y25 = sum(x["year"] == "2025" for x in successes)
    y26 = sum(x["year"] == "2026" for x in successes)
    gate = decision(total, y25, y26)

    write_gzip(OUT_RESOLUTION, resolution_rows, ["exact_group_id", "year", "ticker", "resolution_status", "candidate_entity_count", "official_host", "official_website"])
    write_gzip(OUT_NAV, nav_rows, ["exact_group_id", "year", "ticker", "candidate_rank", "candidate_url_sha256", "candidate_host", "official_host", "path_ir_signal"])
    write_gzip(OUT_BODY, body_rows, ["exact_group_id", "year", "candidate_rank", "candidate_url_sha256", "final_url_sha256", "official_host", "final_host", "http_status", "attempts", "error_class", "content_type", "body_sha256", "identity_bindable", "matched_identity_token_count"])
    summary = {
        "artifact": "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_CAPACITY_SUMMARY",
        "version": "W4C-R1-EIR-ODD-RESULT-v1.0",
        "sample_size": 40,
        "probe_success_total": total,
        "probe_success_by_year": {"2025": y25, "2026": y26},
        "unique_wikidata_resolution_total": sum(r["resolution_status"] == "RESOLVED_UNIQUE_WIKIDATA_ENTITY_AND_P856" for r in resolution_rows),
        "candidate_navigation_rows": len(nav_rows),
        "official_body_attempt_rows": len(body_rows),
        "capacity_decision": gate,
        "outcome_reveal_authorized": False,
        "n_final_backtestable_authorized": False,
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    execution = {
        "artifact": "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTION_MANIFEST",
        "protocol": PROTOCOL.name,
        "sample": SAMPLE.name,
        "executor": Path(__file__).name,
        "sample_size": 40,
        "external_requests_performed": True,
        "capacity_decision": gate,
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
    OUT_EXEC.write_text(json.dumps(execution, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    validate_inputs()
    if args.validate_only:
        print("PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTOR_VALIDATE_ONLY")
        return 0
    if not args.execute:
        raise SystemExit("choose --validate-only or --execute")
    if os.environ.get(EXECUTE_ENV) != EXECUTE_TOKEN:
        raise SystemExit("execution authorization missing")
    if not FREEZE.exists():
        raise SystemExit("executor freeze manifest missing")
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())

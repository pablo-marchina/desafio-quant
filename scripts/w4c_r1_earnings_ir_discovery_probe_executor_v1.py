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
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"

PROTOCOL = REG / "w4c_r1_earnings_ir_discovery_probe_protocol_v1.json"
SAMPLE = REG / "w4c_r1_earnings_ir_probe_sample_v1.json"
TICKER_PROFILE = REG / "w4c_r1_earnings_ticker_profile_v1.json"
FREEZE = REG / "w4c_r1_earnings_ir_discovery_probe_executor_freeze_v1.json"

OUT_NAV = REG / "w4c_r1_earnings_ir_probe_navigation_manifest_v1.csv.gz"
OUT_BODY = REG / "w4c_r1_earnings_ir_probe_official_body_manifest_v1.csv.gz"
OUT_SUMMARY = REG / "w4c_r1_earnings_ir_probe_capacity_summary_v1.json"

UA = "desafio-quant-w4c-r1-earnings-ir-probe/1.0 capacity-only"
EXECUTE_ENV = "W4C_R1_EARNINGS_IR_PROBE_EXECUTE"
EXECUTE_TOKEN = "YES_FROZEN_CAPACITY_PROBE"

SEARCH_PROVIDERS = ("duckduckgo_html", "bing_html")
MAX_SEARCH_BYTES = 2_000_000
MAX_BODY_BYTES = 5_000_000
MAX_CANDIDATES_PER_GROUP = 6

DENY_DOMAINS = (
    "duckduckgo.com", "bing.com", "google.com", "yahoo.com", "finance.yahoo.com",
    "marketwatch.com", "seekingalpha.com", "nasdaq.com", "investing.com",
    "reuters.com", "bloomberg.com", "cnbc.com", "forbes.com", "benzinga.com",
    "thestreet.com", "fool.com", "tipranks.com", "stocktitan.net", "sec.gov",
    "prnewswire.com", "businesswire.com", "globenewswire.com", "accesswire.com",
)

IR_PATH_HINTS = (
    "investor", "investors", "investor-relations", "ir.", "/ir/", "press-release",
    "press_releases", "news-release", "newsroom", "earnings", "financial-results",
    "quarterly-results", "results",
)

SEMANTIC_MARKERS = ("nongaap", "gaap", "up", "its", "cash")
GENERIC_ISSUER_TOKENS = {
    "inc", "incorporated", "corp", "corporation", "company", "co", "ltd", "limited",
    "plc", "holdings", "holding", "group",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def json_load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def normalize_host(url: str) -> str:
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except Exception:
        return ""
    host = host.lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def host_compact(host: str) -> str:
    return re.sub(r"[^a-z0-9]", "", host.lower())


def is_denied_host(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in DENY_DOMAINS)


def ticker_map(profile: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in profile["rows"]:
        ticker = str(row.get("ticker_candidate", "")).strip().upper()
        if row.get("mode") == "UNIQUE_PRE_GAAP_TICKER_CANDIDATE" and ticker:
            out[row["exact_group_id"]] = ticker
    return out


def issuer_parts(subject_key: str, ticker: str) -> tuple[str, list[str]]:
    tokens = [t for t in subject_key.lower().split("_") if t]
    cut = len(tokens)
    for i, token in enumerate(tokens):
        if token in SEMANTIC_MARKERS:
            cut = i
            break
    prefix = tokens[:cut]
    if ticker and len(prefix) > 1 and prefix[-1] == ticker.lower():
        prefix = prefix[:-1]
    # Never allow the numeric estimate encoded in the frozen subject key into navigation.
    prefix = [t for t in prefix if not re.fullmatch(r"(?:neg)?\d+pt\d+", t)]
    display = " ".join(prefix).strip()
    return display, prefix


def core_identity_tokens(tokens: Iterable[str]) -> list[str]:
    raw = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in tokens]
    raw = [t for t in raw if t and t not in GENERIC_ISSUER_TOKENS]
    strong = [t for t in raw if len(t) >= 3]
    return strong or [t for t in raw if len(t) >= 2]


def navigation_query(issuer_display: str, ticker: str, event_date: str) -> str:
    if not issuer_display:
        return ""
    # Deliberately excludes EPS/revenue/guidance values and outcome language.
    parts = [f'"{issuer_display}"']
    if ticker:
        parts.append(ticker)
    parts.extend(["investor relations", "earnings", event_date])
    return " ".join(parts)


def search_url(provider: str, query: str) -> str:
    q = urllib.parse.quote_plus(query)
    if provider == "duckduckgo_html":
        return f"https://html.duckduckgo.com/html/?q={q}"
    if provider == "bing_html":
        return f"https://www.bing.com/search?q={q}&count=20"
    raise ValueError(provider)


def decode_ddg_url(url: str) -> str:
    try:
        u = urllib.parse.urlsplit(url)
        if "duckduckgo.com" in (u.hostname or ""):
            target = urllib.parse.parse_qs(u.query).get("uddg", [""])[0]
            if target:
                return urllib.parse.unquote(target)
    except Exception:
        pass
    return url


def extract_search_urls(provider: str, body: bytes) -> list[str]:
    text = body.decode("utf-8", errors="replace")
    urls: list[str] = []
    if provider == "duckduckgo_html":
        for href in re.findall(
            r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
            text,
            flags=re.I,
        ):
            urls.append(decode_ddg_url(html.unescape(href)))
    elif provider == "bing_html":
        for block in re.findall(r'<li[^>]+class=["\'][^"\']*b_algo[^"\']*["\'][^>]*>(.*?)</li>', text, flags=re.I | re.S):
            m = re.search(r'<a[^>]+href=["\'](https?://[^"\']+)["\']', block, flags=re.I)
            if m:
                urls.append(html.unescape(m.group(1)))
    clean: list[str] = []
    seen: set[str] = set()
    for url in urls:
        url = url.strip()
        try:
            parsed = urllib.parse.urlsplit(url)
        except Exception:
            continue
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        key = urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))
        if key not in seen:
            seen.add(key)
            clean.append(url)
    return clean


def domain_identity(host: str, core_tokens: list[str]) -> bool:
    hc = host_compact(host)
    return bool(hc) and any(len(t) >= 3 and t in hc for t in core_tokens)


def path_ir_signal(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in IR_PATH_HINTS)


def candidate_score(url: str, core_tokens: list[str]) -> int:
    host = normalize_host(url)
    if not host or is_denied_host(host):
        return -100
    score = 0
    if domain_identity(host, core_tokens):
        score += 5
    if path_ir_signal(url):
        score += 3
    if urllib.parse.urlsplit(url).scheme == "https":
        score += 1
    return score


def body_identity(text: str, core_tokens: list[str], issuer_display: str) -> tuple[bool, list[str]]:
    if not text or not core_tokens:
        return False, []
    matched = [t for t in core_tokens if re.search(rf"\b{re.escape(t)}\b", text)]
    phrase = re.sub(r"\s+", " ", issuer_display.lower()).strip()
    phrase_match = len(phrase) >= 4 and phrase in text
    needed = 1 if len(core_tokens) == 1 else max(2, (len(core_tokens) + 1) // 2)
    return bool(phrase_match or len(matched) >= needed), matched


def fetch_bytes(url: str, max_bytes: int, attempts: int = 3) -> dict:
    last = {
        "status": 0, "body": b"", "content_type": "", "final_url": url,
        "attempts": 0, "error_class": "",
    }
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.8,*/*;q=0.1",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                body = response.read(max_bytes + 1)
                last = {
                    "status": int(response.status),
                    "body": body[:max_bytes],
                    "content_type": str(response.headers.get("Content-Type", "")),
                    "final_url": str(response.geturl()),
                    "attempts": attempt,
                    "error_class": "",
                    "body_truncated": len(body) > max_bytes,
                }
        except urllib.error.HTTPError as exc:
            body = exc.read(max_bytes + 1)
            last = {
                "status": int(exc.code),
                "body": body[:max_bytes],
                "content_type": str(exc.headers.get("Content-Type", "")),
                "final_url": str(exc.geturl()),
                "attempts": attempt,
                "error_class": f"HTTP_{exc.code}",
                "body_truncated": len(body) > max_bytes,
            }
        except Exception as exc:
            last = {
                "status": 0, "body": b"", "content_type": "", "final_url": url,
                "attempts": attempt, "error_class": type(exc).__name__,
                "body_truncated": False,
            }

        status = int(last["status"])
        retryable = status == 0 or status == 429 or 500 <= status <= 599
        if not retryable or attempt == attempts:
            return last
        time.sleep(float(attempt))
    return last


def write_gzip_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    raw = io.StringIO(newline="")
    writer = csv.DictWriter(raw, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    data = raw.getvalue().encode("utf-8")
    with path.open("wb") as fh:
        with gzip.GzipFile(filename=path.stem, mode="wb", fileobj=fh, mtime=0) as gz:
            gz.write(data)


def validate_frozen_inputs(require_freeze: bool = True) -> dict:
    protocol = json_load(PROTOCOL)
    sample = json_load(SAMPLE)
    profile = json_load(TICKER_PROFILE)

    assert protocol["version"] == "W4C-R1-EIR-DP-v1.0.1"
    assert protocol["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_DISCOVERY_PROBE_PROTOCOL_FROZEN_PRE_REQUEST"
    assert protocol["firewall"]["event_truth_verification_authorized"] is False
    assert protocol["firewall"]["n_final_backtestable_authorized"] is False

    assert sample["version"] == "W4C-R1-EIR-DP-SAMPLE-v1.0"
    assert sample["status"] == "FROZEN_SAMPLE_PRE_EXTERNAL_REQUEST"
    assert sample["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_PROBE_SAMPLE_FROZEN_PRE_REQUEST"
    assert sample["sample_size"] == 40 and len(sample["rows"]) == 40
    assert sample["allocation"] == {"2025": 20, "2026": 20}
    assert sample["external_probe_requests_performed"] is False
    assert sample["issuer_ir_lookup_performed"] is False
    assert sample["event_truth_verification_authorized"] is False
    assert sample["n_final_backtestable_authorized"] is False
    assert len({r["exact_group_id"] for r in sample["rows"]}) == 40
    years = Counter(str(r["year"]) for r in sample["rows"])
    assert years == Counter({"2025": 20, "2026": 20})

    sorted_digest = sha256_bytes(("\n".join(sorted(r["exact_group_id"] for r in sample["rows"])) + "\n").encode("utf-8"))
    assert sorted_digest == sample["sorted_sample_group_ids_sha256"]

    assert profile["gate_decision"] == "PASS_W4C_R1_EARNINGS_TICKER_PROFILE_DESCRIPTIVE_ONLY"
    assert profile["issuer_ir_lookup_performed"] is False
    assert profile["new_external_source_reads"] is False
    assert profile["queue_groups"] == 1355

    if require_freeze:
        freeze = json_load(FREEZE)
        assert freeze["status"] == "FROZEN_EXECUTOR_PRE_EXTERNAL_REQUEST"
        assert freeze["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_DISCOVERY_PROBE_EXECUTOR_FROZEN_PRE_REQUEST"
        assert freeze["external_probe_requests_performed_before_freeze"] is False
        assert freeze["issuer_ir_lookup_performed_before_freeze"] is False
        for item in freeze["bound_files"]:
            path = ROOT / item["path"]
            assert path.is_file(), item["path"]
            assert git_blob_sha(path) == item["git_blob_sha"], item["path"]

    return {"protocol": protocol, "sample": sample, "profile": profile}


def capacity_decision(total: int, y2025: int, y2026: int) -> str:
    if total >= 24 and y2025 >= 10 and y2026 >= 10:
        return "FULL_ROUTE_TECHNICALLY_VIABLE"
    if total >= 12 and y2025 >= 5 and y2026 >= 5:
        return "CONDITIONAL_ROUTE"
    return "ROUTE_INFEASIBLE_CURRENT_PROTOCOL"


def execute_probe() -> dict:
    frozen = validate_frozen_inputs(require_freeze=True)
    sample = frozen["sample"]
    tmap = ticker_map(frozen["profile"])

    retrieved_at = datetime.now(timezone.utc).isoformat()
    nav_rows: list[dict] = []
    body_rows: list[dict] = []
    group_results: list[dict] = []

    for row in sample["rows"]:
        gid = row["exact_group_id"]
        ticker = tmap.get(gid, "")
        issuer_display, issuer_tokens = issuer_parts(row["pretruth_subject_key"], ticker)
        core_tokens = core_identity_tokens(issuer_tokens)
        query = navigation_query(issuer_display, ticker, row["pretruth_event_reference_date"])

        if not query or not core_tokens:
            group_results.append({
                "exact_group_id": gid,
                "year": str(row["year"]),
                "navigation_found": False,
                "official_body_retrievable": False,
                "identity_bindable": False,
                "probe_success": False,
                "failure_reason": "INSUFFICIENT_FROZEN_ISSUER_METADATA",
            })
            continue

        candidates: list[tuple[int, int, str, str]] = []
        seen_urls: set[str] = set()
        navigation_found = False

        for provider_index, provider in enumerate(SEARCH_PROVIDERS):
            s_url = search_url(provider, query)
            result = fetch_bytes(s_url, MAX_SEARCH_BYTES, attempts=3)
            nav_rows.append({
                "exact_group_id": gid,
                "year": str(row["year"]),
                "provider": provider,
                "navigation_query": query,
                "navigation_query_sha256": sha256_bytes(query.encode("utf-8")),
                "request_url_sha256": sha256_bytes(s_url.encode("utf-8")),
                "http_status": result["status"],
                "attempts": result["attempts"],
                "error_class": result["error_class"],
                "search_body_sha256": sha256_bytes(result["body"]) if result["body"] else "",
                "search_metadata_navigation_only": True,
                "search_snippet_persisted": False,
            })
            if int(result["status"]) != 200 or not result["body"]:
                continue

            for rank, url in enumerate(extract_search_urls(provider, result["body"]), start=1):
                host = normalize_host(url)
                score = candidate_score(url, core_tokens)
                if score < 1 or url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append((-score, provider_index * 100 + rank, provider, url))
                if domain_identity(host, core_tokens) or path_ir_signal(url):
                    navigation_found = True

        candidates.sort()
        official_body_retrievable = False
        identity_bindable = False
        chosen_url = ""
        failure_reason = "NO_ISSUER_CANDIDATE_FOUND"

        for _, _, provider, url in candidates[:MAX_CANDIDATES_PER_GROUP]:
            result = fetch_bytes(url, MAX_BODY_BYTES, attempts=3)
            final_url = str(result["final_url"])
            final_host = normalize_host(final_url)
            status = int(result["status"])
            retrievable = 200 <= status <= 299 and bool(result["body"])

            text = ""
            content_type = str(result["content_type"]).lower()
            if result["body"] and ("html" in content_type or "text" in content_type or not content_type):
                text = normalize_text(result["body"].decode("utf-8", errors="replace"))

            d_identity = domain_identity(final_host, core_tokens) and not is_denied_host(final_host)
            b_identity, matched_tokens = body_identity(text, core_tokens, issuer_display)
            ir_signal = path_ir_signal(final_url)
            bindable = bool(retrievable and d_identity and (b_identity or ir_signal))

            body_rows.append({
                "exact_group_id": gid,
                "year": str(row["year"]),
                "provider": provider,
                "candidate_url": url,
                "candidate_domain": normalize_host(url),
                "final_url": final_url,
                "final_domain": final_host,
                "http_status": status,
                "attempts": result["attempts"],
                "error_class": result["error_class"],
                "content_type": result["content_type"],
                "response_bytes_captured": len(result["body"]),
                "body_truncated": bool(result.get("body_truncated", False)),
                "source_body_sha256_or_document_hash_when_retrievable": sha256_bytes(result["body"]) if result["body"] else "",
                "domain_identity": d_identity,
                "body_identity": b_identity,
                "matched_identity_tokens": "|".join(sorted(matched_tokens)),
                "ir_path_signal": ir_signal,
                "official_body_retrievable": retrievable,
                "identity_bindable": bindable,
                "probe_success": bindable,
                "retrieved_at_utc": retrieved_at,
                "numeric_outcome_fields_persisted": False,
                "truth_verified_by_probe": False,
            })

            if retrievable:
                official_body_retrievable = True
            if bindable:
                identity_bindable = True
                chosen_url = final_url
                failure_reason = ""
                break
            failure_reason = "NO_RETRIEVABLE_IDENTITY_BINDABLE_ISSUER_BODY"

        group_results.append({
            "exact_group_id": gid,
            "year": str(row["year"]),
            "navigation_found": navigation_found,
            "official_body_retrievable": official_body_retrievable,
            "identity_bindable": identity_bindable,
            "probe_success": bool(official_body_retrievable and identity_bindable),
            "chosen_official_url": chosen_url,
            "failure_reason": failure_reason,
        })

    assert len(group_results) == 40
    successes = [r for r in group_results if r["probe_success"]]
    y25 = sum(1 for r in successes if r["year"] == "2025")
    y26 = sum(1 for r in successes if r["year"] == "2026")
    total = len(successes)
    decision = capacity_decision(total, y25, y26)

    nav_fields = [
        "exact_group_id", "year", "provider", "navigation_query", "navigation_query_sha256",
        "request_url_sha256", "http_status", "attempts", "error_class", "search_body_sha256",
        "search_metadata_navigation_only", "search_snippet_persisted",
    ]
    body_fields = [
        "exact_group_id", "year", "provider", "candidate_url", "candidate_domain", "final_url",
        "final_domain", "http_status", "attempts", "error_class", "content_type",
        "response_bytes_captured", "body_truncated",
        "source_body_sha256_or_document_hash_when_retrievable", "domain_identity", "body_identity",
        "matched_identity_tokens", "ir_path_signal", "official_body_retrievable", "identity_bindable",
        "probe_success", "retrieved_at_utc", "numeric_outcome_fields_persisted", "truth_verified_by_probe",
    ]
    write_gzip_csv(OUT_NAV, nav_rows, nav_fields)
    write_gzip_csv(OUT_BODY, body_rows, body_fields)

    summary = {
        "artifact": "W4C_R1_EARNINGS_IR_DISCOVERY_PROBE_CAPACITY_SUMMARY",
        "version": "W4C-R1-EIR-DP-RESULT-v1.0",
        "date_utc": retrieved_at,
        "science_reopened": False,
        "performance_blind": True,
        "sample_size": 40,
        "allocation": {"2025": 20, "2026": 20},
        "probe_success_total": total,
        "probe_success_by_year": {"2025": y25, "2026": y26},
        "navigation_found_total": sum(1 for r in group_results if r["navigation_found"]),
        "official_body_retrievable_total": sum(1 for r in group_results if r["official_body_retrievable"]),
        "identity_bindable_total": sum(1 for r in group_results if r["identity_bindable"]),
        "capacity_decision": decision,
        "capacity_thresholds": {
            "FULL_ROUTE_TECHNICALLY_VIABLE": ">=24/40 overall AND >=10/20 in each year",
            "CONDITIONAL_ROUTE": "not FULL, but >=12/40 overall AND >=5/20 in each year",
            "ROUTE_INFEASIBLE_CURRENT_PROTOCOL": "<12/40 overall OR <5/20 in either year",
        },
        "group_results": group_results,
        "search_or_index_results_navigation_only": True,
        "search_snippets_persisted": False,
        "event_truth_verification_authorized": False,
        "truth_verified_by_probe": False,
        "numeric_eps_revenue_guidance_results_persisted": False,
        "prediction_market_settlement_used": False,
        "prediction_market_price_or_performance_used": False,
        "linked_asset_realized_returns_used": False,
        "ARGOS_PnL_used": False,
        "model_performance_used": False,
        "family_reclassification_allowed": False,
        "w4b_artifacts_modified": False,
        "n_final_backtestable_authorized": False,
        "outcome_reveal_authorized": False,
        "navigation_manifest_path": str(OUT_NAV.relative_to(ROOT)),
        "official_body_manifest_path": str(OUT_BODY.relative_to(ROOT)),
        "gate_decision": "PASS_W4C_R1_EARNINGS_IR_DISCOVERY_CAPACITY_PROBE_MATERIALIZED",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.validate_only:
        frozen = validate_frozen_inputs(require_freeze=True)
        sample = frozen["sample"]
        result = {
            "gate_decision": "PASS_W4C_R1_EARNINGS_IR_DISCOVERY_PROBE_EXECUTOR_VALIDATE_ONLY",
            "sample_size": sample["sample_size"],
            "allocation": sample["allocation"],
            "network_requests_performed": False,
            "issuer_ir_lookup_performed": False,
            "event_truth_verification_authorized": False,
            "n_final_backtestable_authorized": False,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if os.environ.get(EXECUTE_ENV, "") != EXECUTE_TOKEN:
        raise SystemExit(
            f"Refusing network execution: set {EXECUTE_ENV}={EXECUTE_TOKEN} only after the executor freeze is authoritative."
        )
    summary = execute_probe()
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

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

BASE_EXECUTOR = ROOT / "scripts/w4c_r1_earnings_ir_official_domain_discovery_executor_v1.py"
PROTOCOL_V11 = REG / "w4c_r1_earnings_ir_official_domain_discovery_protocol_v1_1.json"
FREEZE_V11 = REG / "w4c_r1_earnings_ir_official_domain_discovery_executor_freeze_v1_1.json"
SAMPLE = REG / "w4c_r1_earnings_ir_probe_sample_v1.json"
TICKER_PROFILE = REG / "w4c_r1_earnings_ticker_profile_v1.json"

OUT_RESOLUTION = REG / "w4c_r1_earnings_ir_official_domain_resolution_manifest_v1_1.csv.gz"
OUT_NAV = REG / "w4c_r1_earnings_ir_official_domain_navigation_manifest_v1_1.csv.gz"
OUT_BODY = REG / "w4c_r1_earnings_ir_official_domain_body_manifest_v1_1.csv.gz"
OUT_SUMMARY = REG / "w4c_r1_earnings_ir_official_domain_capacity_summary_v1_1.json"
OUT_EXEC = REG / "w4c_r1_earnings_ir_official_domain_execution_manifest_v1_1.json"

EXECUTE_ENV = "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_V1_1_EXECUTE"
EXECUTE_TOKEN = "YES_FROZEN_OFFICIAL_DOMAIN_V1_1_PROBE"
VALIDATE_ENV = "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_V1_1_VALIDATE_ONLY"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36 "
    "desafio-quant-w4c-r1-eir-odd-v1.1"
)

REPAIR_MAP = {
    "W4CE1-255de5efc59b0a13cd48": "CASH",
    "W4CE1-41656e7ed0dc094bc332": "PLAY",
    "W4CE1-29ac4c9b8f8a339821f1": "VSCO",
    "W4CE1-8642b204a5d2db51203c": "",
}

IR_HINTS = (
    "investor", "investor-relations", "/ir", "ir.", "earnings", "financial-results",
    "quarterly-results", "results", "newsroom", "press-release", "press-releases",
    "news-releases", "events-and-presentations", "financial-information", "news-events",
    "news-and-events", "presentations",
)

PATH_TEMPLATES = (
    "/investors", "/investor-relations", "/ir", "/newsroom", "/news", "/earnings",
    "/financial-results", "/quarterly-results", "/results", "/events-and-presentations",
    "/investors/news-events/press-releases", "/investors/news-and-events/press-releases",
    "/investor-relations/news-events/press-releases", "/investor-relations/news-and-events/press-releases",
    "/investors/financial-information/quarterly-results",
    "/investor-relations/financial-information/quarterly-results",
    "/investors/events-and-presentations", "/investor-relations/events-and-presentations",
    "/news-releases", "/press-releases",
)

SPEC = importlib.util.spec_from_file_location("w4c_r1_eir_odd_v1_base", BASE_EXECUTOR)
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return base.sha256_bytes(data)


def norm_host(url: str) -> str:
    return base.norm_host(url)


def allowed_host(url: str, official_host: str) -> bool:
    return base.allowed_host(url, official_host)


def is_ir_candidate(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in IR_HINTS)


def http_get_v11(url: str, max_bytes: int = base.MAX_BYTES, attempts: int = 3) -> dict:
    last = {"status": 0, "body": b"", "content_type": "", "final_url": url, "attempts": 0, "error_class": ""}
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,*/*;q=0.1",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers=headers)
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
                }
        except urllib.error.HTTPError as exc:
            last = {
                "status": int(exc.code),
                "body": exc.read(max_bytes),
                "content_type": str(exc.headers.get("Content-Type", "")),
                "final_url": str(exc.geturl()),
                "attempts": attempt,
                "error_class": f"HTTP_{exc.code}",
            }
        except Exception as exc:
            last = {"status": 0, "body": b"", "content_type": "", "final_url": url, "attempts": attempt, "error_class": type(exc).__name__}
        if last["status"] == 200 and last["body"]:
            return last
        if last["status"] not in {0, 429} and not 500 <= last["status"] <= 599:
            return last
        if attempt < attempts:
            time.sleep(float(attempt))
    return last


def repaired_ticker_map(profile: dict) -> dict[str, str]:
    out = base.ticker_map(profile)
    out.update(REPAIR_MAP)
    return out


def _sample_ticker_context() -> dict[str, list[str]]:
    sample = load_json(SAMPLE)
    profile = load_json(TICKER_PROFILE)
    tickers = repaired_ticker_map(profile)
    contexts: dict[str, list[str]] = defaultdict(list)
    for row in sample["rows"]:
        gid = row["exact_group_id"]
        ticker = str(tickers.get(gid, "")).upper()
        if not ticker:
            continue
        display, raw_tokens = base.issuer_parts(row["pretruth_subject_key"], ticker)
        tokens = base.core_tokens(raw_tokens)
        if display:
            tokens.extend(base.core_tokens(display.split()))
        contexts[ticker].extend(tokens)
    return {ticker: sorted(set(tokens)) for ticker, tokens in contexts.items()}


def _candidate_score(candidate: dict[str, object], tokens: list[str]) -> int:
    host = norm_host(str(candidate.get("website", ""))).replace(".", " ")
    label = str(candidate.get("label", ""))
    aliases = " ".join(str(x) for x in candidate.get("aliases", []))
    text = re.sub(r"[^a-z0-9]+", " ", f"{label} {aliases} {host}".lower())
    return sum(1 for token in tokens if re.search(rf"\b{re.escape(token.lower())}\b", text))


def sparql_query_v11(tickers: list[str]) -> dict[str, list[dict[str, str]]]:
    requested = sorted(set(t.upper() for t in tickers))
    nonempty = [t for t in requested if t]
    out: dict[str, list[dict[str, str]]] = {t: [] for t in requested}
    if not nonempty:
        return out

    values = " ".join(json.dumps(t) for t in nonempty)
    query = f"""
SELECT DISTINCT ?ticker ?item ?itemLabel ?website ?alias WHERE {{
  VALUES ?ticker {{ {values} }}
  {{
    ?item wdt:P249 ?ticker .
  }}
  UNION
  {{
    ?item p:P414 ?stmt .
    ?stmt pq:P249 ?ticker .
  }}
  ?item wdt:P856 ?website .
  OPTIONAL {{
    ?item skos:altLabel ?alias .
    FILTER(LANG(?alias) = "en")
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""
    url = base.WDQS + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    result = http_get_v11(url, max_bytes=2_500_000, attempts=3)
    if result["status"] != 200:
        raise RuntimeError(f"WDQS_HTTP_{result['status']}")

    payload = json.loads(result["body"].decode("utf-8"))
    grouped: dict[str, dict[tuple[str, str], dict[str, object]]] = {t: {} for t in requested}
    for binding in payload.get("results", {}).get("bindings", []):
        ticker = binding.get("ticker", {}).get("value", "").upper()
        if ticker not in grouped:
            continue
        item = binding.get("item", {}).get("value", "")
        website = binding.get("website", {}).get("value", "")
        if not item or not website:
            continue
        key = (item, website)
        row = grouped[ticker].setdefault(key, {"item": item, "website": website, "label": "", "aliases": set()})
        label = binding.get("itemLabel", {}).get("value", "")
        alias = binding.get("alias", {}).get("value", "")
        if label:
            row["label"] = label
        if alias:
            row["aliases"].add(alias)

    contexts = _sample_ticker_context()
    for ticker, rows in grouped.items():
        candidates = list(rows.values())
        for candidate in candidates:
            candidate["aliases"] = sorted(candidate["aliases"])
        if len(candidates) <= 1:
            out[ticker] = [{"item": str(c["item"]), "label": str(c.get("label", "")), "website": str(c["website"])} for c in candidates]
            continue

        tokens = contexts.get(ticker, [])
        scored = [(candidate, _candidate_score(candidate, tokens)) for candidate in candidates]
        max_score = max((score for _, score in scored), default=0)
        filtered = [candidate for candidate, score in scored if score == max_score and score > 0]
        if len(filtered) == 1:
            out[ticker] = [{"item": str(filtered[0]["item"]), "label": str(filtered[0].get("label", "")), "website": str(filtered[0]["website"])}]
        else:
            out[ticker] = [{"item": str(c["item"]), "label": str(c.get("label", "")), "website": str(c["website"])} for c in candidates]
    return out


def _add_url(out: list[str], url: str, official_host: str) -> None:
    if not url:
        return
    url = url.split("#", 1)[0]
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        return
    if allowed_host(url, official_host) and url not in out:
        out.append(url)


def _sitemap_urls(root: str, official_host: str, depth: int = 0, seen: set[str] | None = None) -> list[str]:
    if seen is None:
        seen = set()
    if depth > 2 or root in seen or not allowed_host(root, official_host):
        return []
    seen.add(root)
    result = http_get_v11(root, max_bytes=2_000_000, attempts=3)
    if result["status"] != 200 or not result["body"]:
        return []
    urls: list[str] = []
    for loc in base.extract_locs(result["body"]):
        if not allowed_host(loc, official_host):
            continue
        low = loc.lower()
        if "sitemap" in low and depth < 2:
            for child in _sitemap_urls(loc, official_host, depth + 1, seen):
                _add_url(urls, child, official_host)
        elif is_ir_candidate(loc):
            _add_url(urls, loc, official_host)
    return urls


def candidate_urls_v11(homepage: str, official_host: str) -> list[str]:
    candidates: list[str] = []
    root = homepage.rstrip("/")
    scheme = urllib.parse.urlsplit(homepage).scheme or "https"

    first_party_roots = [root]
    for sub in ("investors", "investor", "ir", "newsroom"):
        first_party_roots.append(f"{scheme}://{sub}.{official_host}")

    sitemaps: list[str] = []
    for entry_root in first_party_roots:
        robots = urllib.parse.urljoin(entry_root.rstrip("/") + "/", "robots.txt")
        rob = http_get_v11(robots, max_bytes=500_000, attempts=2)
        if rob["status"] == 200:
            text = rob["body"].decode("utf-8", errors="replace")
            sitemaps.extend(re.findall(r"(?im)^\s*sitemap:\s*(\S+)\s*$", text))
        sitemaps.append(urllib.parse.urljoin(entry_root.rstrip("/") + "/", "sitemap.xml"))
        sitemaps.append(urllib.parse.urljoin(entry_root.rstrip("/") + "/", "sitemap_index.xml"))

    seen_sitemaps: set[str] = set()
    for sitemap in sitemaps:
        for url in _sitemap_urls(sitemap, official_host, depth=0, seen=seen_sitemaps):
            _add_url(candidates, url, official_host)
            if len(candidates) >= 24:
                return candidates[:24]

    landing_pages: list[str] = []
    for entry_root in first_party_roots:
        h = http_get_v11(entry_root, max_bytes=base.MAX_BYTES, attempts=2)
        if h["status"] != 200:
            continue
        for link in base.extract_links(h["body"], entry_root, official_host):
            if is_ir_candidate(link):
                _add_url(candidates, link, official_host)
                _add_url(landing_pages, link, official_host)
                if len(candidates) >= 24:
                    return candidates[:24]

    for landing in landing_pages[:8]:
        h = http_get_v11(landing, max_bytes=base.MAX_BYTES, attempts=2)
        if h["status"] != 200:
            continue
        for link in base.extract_links(h["body"], landing, official_host):
            if is_ir_candidate(link):
                _add_url(candidates, link, official_host)
                if len(candidates) >= 24:
                    return candidates[:24]

    for entry_root in first_party_roots:
        for path in PATH_TEMPLATES:
            _add_url(candidates, entry_root.rstrip("/") + path, official_host)
            if len(candidates) >= 24:
                return candidates[:24]

    return candidates[:24]


def validate_inputs_v11() -> dict:
    protocol = load_json(PROTOCOL_V11)
    sample = load_json(SAMPLE)
    profile = load_json(TICKER_PROFILE)

    assert protocol["version"] == "W4C-R1-EIR-ODD-v1.1"
    assert protocol["status"] == "FROZEN_PROTOCOL_PRE_EXTERNAL_REQUEST"
    assert protocol["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_DISCOVERY_PROTOCOL_V1_1_FROZEN_PRE_REQUEST"
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

    if FREEZE_V11.exists():
        freeze = load_json(FREEZE_V11)
        assert freeze["status"] == "FROZEN_EXECUTOR_PRE_EXTERNAL_REQUEST"
        assert freeze["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTOR_V1_1_FROZEN_PRE_REQUEST"
        assert freeze["external_requests_performed_before_freeze"] is False
        assert freeze["sample_selection_changed"] is False
        assert freeze["thresholds_changed"] is False
        for item in freeze.get("bound_files", []):
            path = ROOT / item["path"]
            assert base.git_blob_sha(path) == item["git_blob_sha"], item["path"]

    tickers = repaired_ticker_map(profile)
    sample_ids = {row["exact_group_id"] for row in sample["rows"]}
    assert len(sample_ids & set(tickers)) == 40
    return {"protocol": protocol, "sample": sample, "profile": profile}


def patch_base() -> None:
    base.PROTOCOL = PROTOCOL_V11
    base.FREEZE = FREEZE_V11
    base.OUT_RESOLUTION = OUT_RESOLUTION
    base.OUT_NAV = OUT_NAV
    base.OUT_BODY = OUT_BODY
    base.OUT_SUMMARY = OUT_SUMMARY
    base.OUT_EXEC = OUT_EXEC
    base.MAX_CANDIDATES = 24
    base.http_get = http_get_v11
    base.ticker_map = repaired_ticker_map
    base.sparql_query = sparql_query_v11
    base.candidate_urls = candidate_urls_v11
    base.validate_inputs = validate_inputs_v11


def finalize_v11_outputs() -> None:
    summary = load_json(OUT_SUMMARY)
    summary["version"] = "W4C-R1-EIR-ODD-RESULT-v1.1"
    summary["protocol_version"] = "W4C-R1-EIR-ODD-v1.1"
    summary["executor"] = Path(__file__).name
    summary["amendment_scope"] = "navigation_transport_only"
    summary["thresholds_unchanged_from_v1_0"] = True
    summary["outcome_reveal_authorized"] = False
    summary["n_final_backtestable_authorized"] = False
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    execution = load_json(OUT_EXEC)
    execution["protocol"] = PROTOCOL_V11.name
    execution["executor"] = Path(__file__).name
    execution["result_version"] = "W4C-R1-EIR-ODD-RESULT-v1.1"
    execution["amendment_scope"] = "navigation_transport_only"
    execution["external_requests_performed"] = True
    execution["sample_size"] = 40
    execution["outputs"] = {
        "resolution_sha256": sha256_bytes(OUT_RESOLUTION.read_bytes()),
        "navigation_sha256": sha256_bytes(OUT_NAV.read_bytes()),
        "official_body_sha256": sha256_bytes(OUT_BODY.read_bytes()),
        "summary_sha256": sha256_bytes(OUT_SUMMARY.read_bytes()),
    }
    execution["scientific_firewall"] = {
        "earnings_numeric_outcomes_read": False,
        "prediction_market_settlement_read": False,
        "realized_returns_read": False,
        "argos_pnl_read": False,
        "event_truth_verification_used": False,
        "n_final_backtestable_authorized": False,
    }
    OUT_EXEC.write_text(json.dumps(execution, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_only() -> int:
    patch_base()
    validate_inputs_v11()
    print("PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTOR_V1_1_VALIDATE_ONLY")
    print("sample_groups=40")
    print("external_requests_performed=false")
    return 0


def execute() -> int:
    patch_base()
    validate_inputs_v11()
    if os.environ.get(EXECUTE_ENV) != EXECUTE_TOKEN:
        raise SystemExit("execution authorization missing")
    rc = base.execute()
    finalize_v11_outputs()
    print(json.dumps(load_json(OUT_SUMMARY), indent=2, sort_keys=True))
    return rc


def main() -> int:
    if os.environ.get(VALIDATE_ENV) == "YES":
        return validate_only()
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())

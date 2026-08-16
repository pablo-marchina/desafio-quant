#!/usr/bin/env python3
"""Live transport/parser diagnostic only; never reads earnings outcomes."""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
SAMPLE = REG / "w4c_r1_earnings_ir_probe_sample_v1.json"
TICKER_PROFILE = REG / "w4c_r1_earnings_ticker_profile_v1.json"
OUT = REG / "w4c_r1_earnings_ir_probe_live_transport_diagnosis_v1.json"
UA = "desafio-quant-w4c-r1-earnings-ir-probe-diagnostic/1.0"

sys.path.insert(0, str(ROOT / "scripts"))
from w4c_r1_earnings_ir_discovery_probe_executor_v1 import issuer_parts, navigation_query, ticker_map  # noqa: E402

DDG_RE = re.compile(r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)["\']', re.I)
BING_BLOCK_RE = re.compile(r'<li[^>]+class=["\'][^"\']*b_algo[^"\']*["\'][^>]*>(.*?)</li>', re.I | re.S)
BING_LINK_RE = re.compile(r'<a[^>]+href=["\'](https?://[^"\']+)["\']', re.I)


def fetch(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.1"})
    with urllib.request.urlopen(req, timeout=35) as response:
        return int(response.status), response.read(2_000_000), str(response.headers.get("Content-Type", ""))


def main() -> int:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    profile = json.loads(TICKER_PROFILE.read_text(encoding="utf-8"))
    tickers = ticker_map(profile)
    rows = sorted(sample["rows"], key=lambda r: (str(r["year"]), r["exact_group_id"]))
    selected = [rows[0], rows[1], rows[-2], rows[-1]]
    results = []

    for row in selected:
        issuer_display, _ = issuer_parts(row["pretruth_subject_key"], tickers.get(row["exact_group_id"], ""))
        query = navigation_query(issuer_display, tickers.get(row["exact_group_id"], ""), row["pretruth_event_reference_date"])
        for provider in ("duckduckgo_html", "bing_html"):
            q = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={q}" if provider == "duckduckgo_html" else f"https://www.bing.com/search?q={q}&count=20"
            try:
                status, body, content_type = fetch(url)
                text = body.decode("utf-8", errors="replace")
                if provider == "duckduckgo_html":
                    structural = {
                        "result__a_marker_count": text.lower().count("result__a"),
                        "current_regex_match_count": len(DDG_RE.findall(text)),
                        "uddg_marker_count": text.lower().count("uddg="),
                    }
                else:
                    blocks = BING_BLOCK_RE.findall(text)
                    structural = {
                        "b_algo_marker_count": text.lower().count("b_algo"),
                        "current_regex_block_count": len(blocks),
                        "current_regex_match_count": sum(1 for b in blocks if BING_LINK_RE.search(b)),
                    }
                low = text.lower()
                structural["captcha_marker"] = any(x in low for x in ("captcha", "unusual traffic", "verify you are human"))
                structural["consent_marker"] = "consent" in low
                results.append({
                    "exact_group_id": row["exact_group_id"],
                    "year": row["year"],
                    "provider": provider,
                    "http_status": status,
                    "body_bytes": len(body),
                    "content_type": content_type,
                    "structural": structural,
                })
            except Exception as exc:
                results.append({
                    "exact_group_id": row["exact_group_id"],
                    "year": row["year"],
                    "provider": provider,
                    "http_status": 0,
                    "body_bytes": 0,
                    "content_type": "",
                    "error_class": type(exc).__name__,
                })

    report = {
        "artifact": "W4C_R1_EARNINGS_IR_PROBE_LIVE_TRANSPORT_DIAGNOSIS",
        "version": "W4C-R1-EIR-DP-LIVE-DIAG-v1.1",
        "purpose": "Outcome-blind diagnosis of the exact frozen search transports and parsers on four deterministic sample cases.",
        "selected_cases": len(selected),
        "external_requests_performed": True,
        "earnings_outcomes_read": False,
        "prediction_market_settlement_read": False,
        "realized_returns_read": False,
        "arg_os_pnl_read": False,
        "results": results,
        "interpretation": "Compare HTTP/body availability with parser marker matches; this is not a new capacity probe and does not change the frozen 0/40 result.",
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

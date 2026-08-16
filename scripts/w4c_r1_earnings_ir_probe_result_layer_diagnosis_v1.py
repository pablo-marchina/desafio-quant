#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = ROOT / "registry/w4c_r1_earnings_ir_probe_navigation_manifest_v1.csv.gz"
BODY = ROOT / "registry/w4c_r1_earnings_ir_probe_official_body_manifest_v1.csv.gz"
OUT = ROOT / "registry/w4c_r1_earnings_ir_probe_failure_layer_diagnosis_v1.json"


def read_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    nav = read_gz(NAV)
    body = read_gz(BODY)
    nav_provider = Counter(r.get("provider", "") for r in nav)
    nav_status = Counter(r.get("http_status", "") for r in nav)
    nav_errors = Counter(r.get("error_class", "") for r in nav if r.get("error_class"))
    body_provider = Counter(r.get("provider", "") for r in body)
    body_status = Counter(r.get("http_status", "") for r in body)
    body_errors = Counter(r.get("error_class", "") for r in body if r.get("error_class"))
    domain_identity = Counter(r.get("domain_identity", "") for r in body)
    body_identity = Counter(r.get("body_identity", "") for r in body)
    ir_signal = Counter(r.get("ir_path_signal", "") for r in body)
    failure_reasons = Counter()
    for r in body:
        if r.get("official_body_retrievable") != "true" and r.get("identity_bindable") != "true":
            if r.get("error_class"):
                failure_reasons[r["error_class"]] += 1
            elif r.get("http_status") not in {"", "200"}:
                failure_reasons[f"HTTP_{r.get('http_status')}"] += 1
            elif r.get("body_identity") == "false":
                failure_reasons["BODY_IDENTITY_FALSE"] += 1
            else:
                failure_reasons["OTHER_NO_PASS"] += 1

    # The key distinction is whether search returned parseable candidates,
    # whether those candidates looked issuer/IR-like, and whether official-body
    # retrieval/binding failed. No earnings outcomes are read.
    if body:
        if sum(v == "true" for v in domain_identity.values()) == 0 and sum(v == "true" for v in ir_signal.values()) == 0:
            diagnosis = "SEARCH_RESULTS_RETRIEVED_BUT_NO_CANDIDATE_PASSED_ISSUER_IR_NAVIGATION_HEURISTICS"
        elif body_status.get("200", 0) and body_identity.get("false", 0) >= body_status.get("200", 0):
            diagnosis = "OFFICIAL_BODY_RETRIEVED_BUT_ISSUER_IDENTITY_BINDING_FAILED"
        else:
            diagnosis = "MIXED_BODY_LAYER_FAILURE"
    else:
        diagnosis = "NO_OFFICIAL_BODY_ATTEMPTS_RECORDED"

    report = {
        "artifact": "W4C_R1_EARNINGS_IR_PROBE_FAILURE_LAYER_DIAGNOSIS",
        "version": "W4C-R1-EIR-DP-DIAG-v1.0",
        "external_requests_performed": False,
        "navigation_rows": len(nav),
        "body_rows": len(body),
        "navigation_provider_counts": dict(nav_provider),
        "navigation_http_status_counts": dict(nav_status),
        "navigation_error_counts": dict(nav_errors),
        "body_provider_counts": dict(body_provider),
        "body_http_status_counts": dict(body_status),
        "body_error_counts": dict(body_errors),
        "body_domain_identity_counts": dict(domain_identity),
        "body_ir_path_signal_counts": dict(ir_signal),
        "body_identity_counts": dict(body_identity),
        "failure_reason_counts": dict(failure_reasons),
        "diagnosis": diagnosis,
        "scientific_firewall": {
            "earnings_numeric_outcomes_read": False,
            "prediction_market_settlement_read": False,
            "realized_returns_read": False,
            "argos_pnl_read": False,
        },
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

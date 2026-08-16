#!/usr/bin/env python3
"""Outcome-blind diagnosis of the frozen W4-C R1 navigation manifest.

This script performs NO external requests. It reads only the already-frozen
capacity-probe navigation manifest and classifies the observed failure layer
(search transport vs parser/candidate extraction vs issuer binding).
"""
from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from pathlib import Path

MANIFEST = Path("registry/w4c_r1_earnings_ir_probe_navigation_manifest_v1.csv.gz")
OUT = Path("registry/w4c_r1_earnings_ir_probe_transport_diagnosis_v1.json")


def norm(s: str) -> str:
    return s.strip().lower().replace("-", "_").replace(" ", "_")


def pick(row: dict[str, str], *names: str) -> str | None:
    normalized = {norm(k): v for k, v in row.items()}
    for name in names:
        value = normalized.get(norm(name))
        if value is not None and value != "":
            return value
    return None


def as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def as_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "y"}


def main() -> int:
    if not MANIFEST.exists():
        raise SystemExit(f"missing frozen manifest: {MANIFEST}")

    with gzip.open(MANIFEST, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = reader.fieldnames or []

    providers = Counter()
    statuses = Counter()
    candidate_counts = Counter()
    errors = Counter()
    request_ok = Counter()
    response_bytes = []

    for row in rows:
        provider = pick(row, "provider", "search_provider", "transport") or "<missing>"
        providers[provider] += 1

        status = pick(row, "http_status", "status_code", "response_status") or "<missing>"
        statuses[status] += 1

        candidate = as_int(pick(row, "candidate_count", "candidates_found", "navigation_candidate_count"))
        candidate_counts[str(candidate if candidate is not None else "<missing>")] += 1

        error = pick(row, "error", "error_class", "failure", "failure_class", "exception")
        if error:
            errors[error] += 1

        ok = as_bool(pick(row, "request_ok", "response_ok", "transport_ok", "http_ok"))
        if ok is not None:
            request_ok[str(ok)] += 1

        rb = as_int(pick(row, "response_bytes", "body_bytes", "content_length", "response_length"))
        if rb is not None:
            response_bytes.append(rb)

    # Strongly outcome-blind diagnosis: we only classify the transport/parser
    # layer. No earnings values, market settlement, prices, returns or PnL are read.
    if rows and sum(candidate_counts.values()) == len(rows) and candidate_counts.get("0", 0) == len(rows):
        if response_bytes and max(response_bytes) > 0:
            diagnosis = "SEARCH_TRANSPORT_OR_PARSER_FAILURE_SUSPECTED"
        elif request_ok.get("False", 0) == len(rows) or all(v == "<missing>" for v in statuses.values()):
            diagnosis = "SEARCH_TRANSPORT_FAILURE_SUSPECTED"
        else:
            diagnosis = "NAVIGATION_ZERO_CANDIDATES_UNRESOLVED_WITH_FROZEN_TELEMETRY"
    else:
        diagnosis = "NOT_ALL_NAVIGATION_CANDIDATES_ZERO"

    report = {
        "artifact": "W4C_R1_EARNINGS_IR_PROBE_TRANSPORT_DIAGNOSIS",
        "version": "W4C-R1-EIR-DP-DIAG-v1.0",
        "external_requests_performed": False,
        "input_manifest": str(MANIFEST),
        "rows": len(rows),
        "fields": fields,
        "provider_counts": dict(providers),
        "http_status_counts": dict(statuses),
        "candidate_count_counts": dict(candidate_counts),
        "request_ok_counts": dict(request_ok),
        "error_counts": dict(errors),
        "response_bytes_summary": {
            "observed": bool(response_bytes),
            "min": min(response_bytes) if response_bytes else None,
            "max": max(response_bytes) if response_bytes else None,
            "nonzero": sum(v > 0 for v in response_bytes),
        },
        "diagnosis": diagnosis,
        "decision_rule": "Diagnose only transport/navigation/parser behavior from the frozen manifest; never inspect or use earnings outcomes, prediction-market settlement/performance, realized returns or PnL.",
    }

    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

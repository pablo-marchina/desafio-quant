#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"

SAMPLE = REG / "w4c_r1_earnings_ir_probe_sample_v1.json"
SUMMARY = REG / "w4c_r1_earnings_ir_official_domain_capacity_summary_v1_1_1.json"
RESOLUTION = REG / "w4c_r1_earnings_ir_official_domain_resolution_manifest_v1_1_1.csv.gz"
NAV = REG / "w4c_r1_earnings_ir_official_domain_navigation_manifest_v1_1_1.csv.gz"
BODY = REG / "w4c_r1_earnings_ir_official_domain_body_manifest_v1_1_1.csv.gz"
OUT = REG / "w4c_r1_earnings_ir_official_domain_failure_diagnosis_v1_1_1.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_gzip_csv(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def main() -> int:
    sample = load_json(SAMPLE)
    summary = load_json(SUMMARY)
    resolution_rows = read_gzip_csv(RESOLUTION)
    nav_rows = read_gzip_csv(NAV)
    body_rows = read_gzip_csv(BODY)

    assert summary["version"] == "W4C-R1-EIR-ODD-RESULT-v1.1.1"
    assert summary["capacity_decision"] == "CONDITIONAL_ROUTE"
    assert summary["sample_size"] == 40
    assert summary["outcome_reveal_authorized"] is False
    assert summary["n_final_backtestable_authorized"] is False

    rows_by_gid = {row["exact_group_id"]: row for row in sample["rows"]}
    assert len(rows_by_gid) == 40

    resolution_by_gid: dict[str, list[dict[str, str]]] = defaultdict(list)
    nav_by_gid: dict[str, list[dict[str, str]]] = defaultdict(list)
    body_by_gid: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in resolution_rows:
        resolution_by_gid[row["exact_group_id"]].append(row)
    for row in nav_rows:
        nav_by_gid[row["exact_group_id"]].append(row)
    for row in body_rows:
        body_by_gid[row["exact_group_id"]].append(row)

    success_gids: set[str] = set()
    for row in body_rows:
        if str(row.get("http_status", "")) == "200" and truthy(row.get("identity_bindable", "")):
            success_gids.add(row["exact_group_id"])

    failure_records: list[dict[str, object]] = []
    layer_counts: Counter[str] = Counter()
    by_year_layer_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for gid, sample_row in sorted(rows_by_gid.items()):
        year = str(sample_row["year"])
        if gid in success_gids:
            continue

        resolution_statuses = [r.get("resolution_status", "") for r in resolution_by_gid.get(gid, [])]
        nav_count = len(nav_by_gid.get(gid, []))
        bodies = body_by_gid.get(gid, [])
        body_count = len(bodies)

        if not resolution_statuses or not any(s == "RESOLVED_UNIQUE_WIKIDATA_ENTITY_AND_P856" for s in resolution_statuses):
            layer = "NO_UNIQUE_WIKIDATA_TICKER_P856_RESOLUTION"
        elif nav_count == 0:
            layer = "RESOLVED_NO_FIRST_PARTY_NAVIGATION_CANDIDATE"
        elif body_count == 0:
            layer = "RESOLVED_NAVIGATION_NO_BODY_ATTEMPT"
        else:
            any_200 = any(str(b.get("http_status", "")) == "200" for b in bodies)
            any_bindable = any(truthy(b.get("identity_bindable", "")) for b in bodies)
            if any_200 and not any_bindable:
                layer = "RESOLVED_BODY_RETRIEVED_IDENTITY_BINDING_FAILED"
            elif any(str(b.get("error_class", "")).strip() for b in bodies):
                layer = "RESOLVED_TRANSPORT_OR_TIMEOUT_ERROR_ONLY"
            else:
                layer = "RESOLVED_BODY_HTTP_NON_200_ONLY"

        layer_counts[layer] += 1
        by_year_layer_counts[year][layer] += 1
        failure_records.append({
            "exact_group_id": gid,
            "year": year,
            "layer": layer,
            "resolution_statuses": sorted(set(resolution_statuses)),
            "navigation_rows": nav_count,
            "body_attempt_rows": body_count,
            "http_status_counts": dict(Counter(str(b.get("http_status", "")) for b in bodies)),
            "transport_error_counts": dict(Counter((str(b.get("error_class", "")) or "NO_ERROR_CLASS") for b in bodies)),
        })

    success_by_year = Counter(str(rows_by_gid[gid]["year"]) for gid in success_gids)
    assert len(success_gids) == int(summary["probe_success_total"])
    assert len(failure_records) == 40 - int(summary["probe_success_total"])

    output = {
        "artifact": "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FAILURE_DIAGNOSIS",
        "version": "W4C-R1-EIR-ODD-FAILURE-DIAGNOSIS-v1.1.1",
        "date": "2026-08-16",
        "status": "MATERIALIZED_OUTCOME_BLIND_DIAGNOSIS",
        "input_result_version": summary["version"],
        "capacity_decision": summary["capacity_decision"],
        "sample_size": 40,
        "probe_success_total": len(success_gids),
        "probe_success_by_year": {"2025": success_by_year.get("2025", 0), "2026": success_by_year.get("2026", 0)},
        "failure_total": len(failure_records),
        "failure_layer_counts": dict(sorted(layer_counts.items())),
        "failure_layer_counts_by_year": {year: dict(sorted(counter.items())) for year, counter in sorted(by_year_layer_counts.items())},
        "failure_records": failure_records,
        "scientific_firewall": {
            "earnings_numeric_outcomes_read": False,
            "prediction_market_settlement_read": False,
            "realized_returns_read": False,
            "argos_pnl_read": False,
            "event_truth_verification_used": False,
            "n_final_backtestable_authorized": False,
        },
        "next_decision_support": {
            "full_route_threshold_total": 24,
            "full_route_threshold_each_year": 10,
            "current_total_success_gap_to_full": max(0, 24 - len(success_gids)),
            "current_2025_success_gap_to_full": max(0, 10 - success_by_year.get("2025", 0)),
            "current_2026_success_gap_to_full": max(0, 10 - success_by_year.get("2026", 0)),
            "diagnosis_supports_targeted_v1_2_amendment": True,
            "full_1355_execution_authorized": False,
        },
        "gate_decision": "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FAILURE_DIAGNOSIS_V1_1_1_OUTCOME_BLIND",
    }
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: output[k] for k in ["artifact", "version", "capacity_decision", "probe_success_total", "failure_total", "failure_layer_counts", "failure_layer_counts_by_year", "gate_decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Trigger-only comment: materialize v1.1.1 failure diagnosis after workflow registration.

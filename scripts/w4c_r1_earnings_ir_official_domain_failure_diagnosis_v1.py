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
SUMMARY = REG / "w4c_r1_earnings_ir_official_domain_capacity_summary_v1.json"
RESOLUTION = REG / "w4c_r1_earnings_ir_official_domain_resolution_manifest_v1.csv.gz"
NAV = REG / "w4c_r1_earnings_ir_official_domain_navigation_manifest_v1.csv.gz"
BODY = REG / "w4c_r1_earnings_ir_official_domain_body_manifest_v1.csv.gz"
OUT = REG / "w4c_r1_earnings_ir_official_domain_failure_diagnosis_v1.json"

RESOLVED_STATUS = "RESOLVED_UNIQUE_WIKIDATA_ENTITY_AND_P856"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gzip_csv(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def main() -> int:
    sample = load_json(SAMPLE)
    summary = load_json(SUMMARY)
    resolution_rows = load_gzip_csv(RESOLUTION)
    nav_rows = load_gzip_csv(NAV)
    body_rows = load_gzip_csv(BODY)

    sample_rows = {r["exact_group_id"]: r for r in sample["rows"]}
    sample_ids = set(sample_rows)
    resolution_by_gid = {r["exact_group_id"]: r for r in resolution_rows}
    resolved_ids = {gid for gid, row in resolution_by_gid.items() if row.get("resolution_status") == RESOLVED_STATUS}

    nav_by_gid: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in nav_rows:
        nav_by_gid[row["exact_group_id"]].append(row)

    body_by_gid: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in body_rows:
        body_by_gid[row["exact_group_id"]].append(row)

    success_ids = {
        row["exact_group_id"]
        for row in body_rows
        if str(row.get("http_status", "")) == "200" and as_bool(row.get("identity_bindable"))
    }
    failures = sorted(sample_ids - success_ids)
    no_resolution_failures = sorted(gid for gid in failures if gid not in resolved_ids)
    post_resolution_failures = sorted(gid for gid in failures if gid in resolved_ids)

    def post_resolution_layer(gid: str) -> str:
        nav = nav_by_gid.get(gid, [])
        body = body_by_gid.get(gid, [])
        if not nav:
            return "RESOLVED_BUT_NO_CANDIDATE_NAVIGATION"
        if not body:
            return "RESOLVED_WITH_CANDIDATES_BUT_NO_BODY_ATTEMPT"
        if not any(str(r.get("http_status", "")) == "200" for r in body):
            return "RESOLVED_BODY_HTTP_NON_200_ONLY"
        if not any(as_bool(r.get("identity_bindable")) for r in body):
            return "RESOLVED_BODY_RETRIEVED_IDENTITY_BINDING_FAILED"
        return "RESOLVED_BODY_OR_IDENTITY_OTHER_FAILURE"

    failure_rows = []
    for gid in failures:
        sample_row = sample_rows[gid]
        resolution = resolution_by_gid.get(gid, {})
        if gid not in resolved_ids:
            layer = "NO_UNIQUE_WIKIDATA_TICKER_P856_RESOLUTION"
        else:
            layer = post_resolution_layer(gid)
        body = body_by_gid.get(gid, [])
        nav = nav_by_gid.get(gid, [])
        failure_rows.append({
            "exact_group_id": gid,
            "year": sample_row.get("year", ""),
            "pretruth_event_reference_date": sample_row.get("pretruth_event_reference_date", ""),
            "pretruth_subject_key": sample_row.get("pretruth_subject_key", ""),
            "failure_layer": layer,
            "ticker": resolution.get("ticker", ""),
            "resolution_status": resolution.get("resolution_status", "MISSING_RESOLUTION_ROW"),
            "candidate_entity_count": resolution.get("candidate_entity_count", ""),
            "official_host_present": bool(resolution.get("official_host", "")),
            "navigation_rows": len(nav),
            "body_attempt_rows": len(body),
            "http_200_attempt_rows": sum(str(r.get("http_status", "")) == "200" for r in body),
            "identity_bindable_rows": sum(as_bool(r.get("identity_bindable")) for r in body),
            "max_matched_identity_token_count": max([int(r.get("matched_identity_token_count") or 0) for r in body] or [0]),
        })

    by_layer = Counter(r["failure_layer"] for r in failure_rows)
    by_year_layer: dict[str, dict[str, int]] = {}
    for row in failure_rows:
        by_year_layer.setdefault(row["year"], {})
        by_year_layer[row["year"]][row["failure_layer"]] = by_year_layer[row["year"]].get(row["failure_layer"], 0) + 1

    diagnosis = {
        "artifact": "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FAILURE_DIAGNOSIS",
        "version": "W4C-R1-EIR-ODD-FAILURE-DIAGNOSIS-v1.0",
        "status": "MATERIALIZED_OUTCOME_BLIND_DIAGNOSIS",
        "input_result_version": summary["version"],
        "capacity_decision": summary["capacity_decision"],
        "sample_size": summary["sample_size"],
        "probe_success_total": summary["probe_success_total"],
        "probe_success_by_year": summary["probe_success_by_year"],
        "failure_total": len(failures),
        "failure_split": {
            "no_unique_wikidata_ticker_p856_resolution": len(no_resolution_failures),
            "resolved_but_body_candidate_or_identity_failed": len(post_resolution_failures),
        },
        "failure_layer_counts": dict(sorted(by_layer.items())),
        "failure_layer_counts_by_year": by_year_layer,
        "manifest_rows": {
            "resolution_rows": len(resolution_rows),
            "navigation_rows": len(nav_rows),
            "body_rows": len(body_rows),
        },
        "invariants": {
            "sample_group_ids_unchanged": len(sample_ids) == 40,
            "success_plus_failure_equals_sample": len(success_ids) + len(failures) == len(sample_ids),
            "expected_failure_total_21": len(failures) == 21,
            "expected_no_resolution_failures_13": len(no_resolution_failures) == 13,
            "expected_post_resolution_failures_8": len(post_resolution_failures) == 8,
            "outcome_data_used": False,
            "settlement_data_used": False,
            "pnl_or_returns_used": False,
            "n_final_backtestable_authorized": False,
        },
        "failure_rows": failure_rows,
        "interpretation": "The conditional-route shortfall is split between ticker/P856 entity resolution coverage and official-domain navigation/body/identity coverage after resolution. This diagnosis reads only frozen manifests and sample metadata; it does not inspect outcomes, settlements, returns, or PnL.",
        "gate_decision": "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_FAILURE_DIAGNOSIS_OUTCOME_BLIND",
    }

    if not all(diagnosis["invariants"].values()):
        print(json.dumps(diagnosis, indent=2, sort_keys=True))
        raise SystemExit("FAIL_W4C_R1_EIR_ODD_FAILURE_DIAGNOSIS_INVARIANTS")

    OUT.write_text(json.dumps(diagnosis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "gate_decision": diagnosis["gate_decision"],
        "failure_total": diagnosis["failure_total"],
        "failure_split": diagnosis["failure_split"],
        "failure_layer_counts": diagnosis["failure_layer_counts"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

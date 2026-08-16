#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
IMPL = ROOT / "scripts/w4c_r1_earnings_ir_official_domain_discovery_executor_v1_1_1.py"
PROTOCOL_V12 = REG / "w4c_r1_earnings_ir_official_domain_discovery_protocol_v1_2.json"
FREEZE_V12 = REG / "w4c_r1_earnings_ir_official_domain_discovery_executor_freeze_v1_2.json"
SAMPLE = REG / "w4c_r1_earnings_ir_probe_sample_v1.json"
TICKER_PROFILE = REG / "w4c_r1_earnings_ticker_profile_v1.json"

OUT_RESOLUTION = REG / "w4c_r1_earnings_ir_official_domain_resolution_manifest_v1_2.csv.gz"
OUT_NAV = REG / "w4c_r1_earnings_ir_official_domain_navigation_manifest_v1_2.csv.gz"
OUT_BODY = REG / "w4c_r1_earnings_ir_official_domain_body_manifest_v1_2.csv.gz"
OUT_SUMMARY = REG / "w4c_r1_earnings_ir_official_domain_capacity_summary_v1_2.json"
OUT_EXEC = REG / "w4c_r1_earnings_ir_official_domain_execution_manifest_v1_2.json"

EXECUTE_ENV = "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_V1_2_EXECUTE"
EXECUTE_TOKEN = "YES_FROZEN_OFFICIAL_DOMAIN_V1_2_PROBE"
VALIDATE_ENV = "W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_V1_2_VALIDATE_ONLY"

spec = importlib.util.spec_from_file_location("w4c_r1_eir_odd_v1_1_1_impl", IMPL)
assert spec and spec.loader
impl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impl)
base = impl.base


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_inputs_v12() -> dict:
    protocol = load_json(PROTOCOL_V12)
    sample = load_json(SAMPLE)
    profile = load_json(TICKER_PROFILE)
    assert protocol["version"] == "W4C-R1-EIR-ODD-v1.2"
    assert protocol["status"] == "FROZEN_PROTOCOL_PRE_EXTERNAL_REQUEST"
    assert protocol["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_DISCOVERY_PROTOCOL_V1_2_FROZEN_PRE_REQUEST"
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
    if FREEZE_V12.exists():
        freeze = load_json(FREEZE_V12)
        assert freeze["status"] == "FROZEN_EXECUTOR_PRE_EXTERNAL_REQUEST"
        assert freeze["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTOR_V1_2_FROZEN_PRE_REQUEST"
        assert freeze["external_requests_performed_before_freeze"] is False
        assert freeze["sample_selection_changed"] is False
        assert freeze["thresholds_changed"] is False
    impl.sample_tickers(profile, sample)
    return {"protocol": protocol, "sample": sample, "profile": profile}


def patch_v12() -> None:
    impl.PROTOCOL_V111 = PROTOCOL_V12
    impl.FREEZE_V111 = FREEZE_V12
    impl.OUT_RESOLUTION = OUT_RESOLUTION
    impl.OUT_NAV = OUT_NAV
    impl.OUT_BODY = OUT_BODY
    impl.OUT_SUMMARY = OUT_SUMMARY
    impl.OUT_EXEC = OUT_EXEC
    impl.MAX_CANDIDATES = 12
    impl.REQUEST_TIMEOUT_SECONDS = 8
    impl.WDQS_TIMEOUT_SECONDS = 25
    impl.UA = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126 Safari/537.36 "
        "desafio-quant-w4c-r1-eir-odd-v1.2"
    )
    impl.validate_inputs = validate_inputs_v12


def retag_outputs_v12() -> None:
    summary = load_json(OUT_SUMMARY)
    summary["version"] = "W4C-R1-EIR-ODD-RESULT-v1.2"
    summary["protocol_version"] = "W4C-R1-EIR-ODD-v1.2"
    summary["amendment_scope"] = "targeted_resolution_and_transport_hardening_only"
    summary["gate_decision"] = "PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_CAPACITY_PROBE_V1_2_MATERIALIZED"
    summary["max_candidates_per_resolved_group"] = 12
    summary["request_timeout_seconds"] = 8
    summary["wdqs_timeout_seconds"] = 25
    write_json(OUT_SUMMARY, summary)

    execution = load_json(OUT_EXEC)
    execution["protocol"] = PROTOCOL_V12.name
    execution["executor"] = Path(__file__).name
    execution["result_version"] = "W4C-R1-EIR-ODD-RESULT-v1.2"
    execution["amendment_scope"] = "targeted_resolution_and_transport_hardening_only"
    execution["transport_bounding"]["max_candidates_per_resolved_group"] = 12
    execution["transport_bounding"]["request_timeout_seconds"] = 8
    execution["transport_bounding"]["wdqs_timeout_seconds"] = 25
    execution["outputs"] = {
        "resolution_sha256": impl.sha256_bytes(OUT_RESOLUTION.read_bytes()),
        "navigation_sha256": impl.sha256_bytes(OUT_NAV.read_bytes()),
        "official_body_sha256": impl.sha256_bytes(OUT_BODY.read_bytes()),
        "summary_sha256": impl.sha256_bytes(OUT_SUMMARY.read_bytes()),
    }
    write_json(OUT_EXEC, execution)


def validate_only() -> int:
    patch_v12()
    validate_inputs_v12()
    print("PASS_W4C_R1_EARNINGS_IR_OFFICIAL_DOMAIN_EXECUTOR_V1_2_VALIDATE_ONLY")
    print("sample_groups=40")
    print("external_requests_performed=false")
    print("max_candidates_per_resolved_group=12")
    print("request_timeout_seconds=8")
    return 0


def execute() -> int:
    patch_v12()
    validate_inputs_v12()
    if os.environ.get(EXECUTE_ENV) != EXECUTE_TOKEN:
        raise SystemExit("execution authorization missing")
    rc = impl.execute()
    retag_outputs_v12()
    print(json.dumps(load_json(OUT_SUMMARY), indent=2, sort_keys=True))
    return rc


def main() -> int:
    if os.environ.get(VALIDATE_ENV) == "YES":
        return validate_only()
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())

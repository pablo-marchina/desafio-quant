#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts/w4c_r1_earnings_ir_official_domain_discovery_executor_v1.py"
REPAIR = ROOT / "registry/w4c_r1_earnings_ir_input_repair_v1.json"

spec = importlib.util.spec_from_file_location("w4c_r1_original_executor", TARGET)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPAIR_MAP = {
    "W4CE1-255de5efc59b0a13cd48": "CASH",
    "W4CE1-41656e7ed0dc094bc332": "PLAY",
    "W4CE1-29ac4c9b8f8a339821f1": "VSCO",
    "W4CE1-8642b204a5d2db51203c": "",
}

_original_ticker_map = mod.ticker_map


def repaired_ticker_map(profile: dict) -> dict[str, str]:
    out = _original_ticker_map(profile)
    out.update(REPAIR_MAP)
    return out


def validate_repair_only() -> int:
    repair = mod.load(REPAIR)
    assert repair["gate_decision"] == "PASS_W4C_R1_EARNINGS_IR_INPUT_REPAIR_FROZEN_PRE_REQUEST"
    assert repair["sample_size"] == 40
    assert all(repair["invariants"].values())
    ctx = mod.validate_inputs()
    groups = {r["exact_group_id"] for r in ctx["sample"]["rows"]}
    repaired = repaired_ticker_map(ctx["profile"])
    assert len(groups) == 40
    assert set(REPAIR_MAP) <= groups
    assert len(set(groups) & set(repaired)) == 40
    assert os.environ.get(mod.EXECUTE_ENV, "") != mod.EXECUTE_TOKEN
    print("PASS_W4C_R1_EARNINGS_IR_INPUT_REPAIR_VALIDATE_ONLY")
    print(f"sample_groups={len(groups)}")
    print(f"ticker_profile_hits_after_repair={len(groups & set(repaired))}")
    print("external_requests_performed=false")
    return 0


if __name__ == "__main__":
    if os.environ.get("W4C_R1_EARNINGS_IR_REPAIR_VALIDATE_ONLY") == "YES":
        raise SystemExit(validate_repair_only())
    mod.ticker_map = repaired_ticker_map
    raise SystemExit(mod.execute())

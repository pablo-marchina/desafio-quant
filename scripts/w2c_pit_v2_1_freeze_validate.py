#!/usr/bin/env python3
"""Validate the W2C-PIT-v2.1 byte freeze before any Layer B/C network call."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(".")
MANIFEST = ROOT / "registry/w2c_pit_v2_1_freeze_manifest.json"


def git_blob(path: str) -> str:
    return subprocess.check_output(["git", "rev-parse", f"HEAD:{path}"], text=True).strip()


def run(*cmd: str) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> None:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["artifact"] == "W2C_PIT_V2_1_BYTE_FREEZE_MANIFEST"
    assert m["version"] == "W2C-PIT-FREEZE-v2.1"
    assert m["science_reopened"] is False
    assert m["performance_blind"] is True
    assert m["population_total"] == 260
    assert m["population_counts"] == {
        "EARNINGS_EPS": 100,
        "FDA_FINAL_PDUFA_DECISION": 63,
        "MACRO_STATISTICAL_RELEASE": 97,
    }
    assert m["right_censored_counts"] == {
        "EARNINGS_EPS": 0,
        "FDA_FINAL_PDUFA_DECISION": 3,
        "MACRO_STATISTICAL_RELEASE": 9,
    }
    assert all(v is False for v in m["authorization"].values()), m["authorization"]

    objects = m["objects"]
    assert len(objects) == 16
    actual = {}
    for path, expected in sorted(objects.items()):
        got = git_blob(path)
        actual[path] = got
        assert got == expected, f"BYTE_FREEZE_MISMATCH {path}: {got} != {expected}"

    payload = "".join(f"{path}\t{actual[path]}\n" for path in sorted(actual))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert digest == m["bundle_sha256"], f"BUNDLE_DIGEST_MISMATCH {digest} != {m['bundle_sha256']}"

    protocol = json.loads((ROOT / "registry/w2c_pit_protocol_v2_1.json").read_text(encoding="utf-8"))
    assert protocol["version"] == "W2C-PIT-v2.1"
    assert protocol["performance_blind"] is True
    assert protocol["execution_authorized"] is False
    assert protocol["frozen_asof_utc"] == "2026-08-12T20:00:00Z"
    assert protocol["population"]["total"] == 260
    assert protocol["layer_A_reuse"]["evidence_bundle_sha256"] == m["layer_a_evidence_bundle_sha256"]
    layer_a = {
        "registry/w2c_pit_v2_platform_events.csv.gz": protocol["layer_A_reuse"]["events_blob"],
        "registry/w2c_pit_v2_platform_request_manifest.jsonl.gz": protocol["layer_A_reuse"]["request_manifest_blob"],
        "registry/w2c_pit_v2_platform_summary.json": protocol["layer_A_reuse"]["summary_blob"],
    }
    for path, expected in layer_a.items():
        assert actual[path] == expected, f"LAYER_A_REUSE_MISMATCH {path}"

    # Static performance firewall: scan only executable PIT-v2.1 code for explicit
    # references to known performance/result artifacts. Generic words such as
    # 'return'/'PnL' are intentionally not used as a heuristic.
    code_paths = [
        "scripts/w2c_pit_v2_1_route_population.py",
        "scripts/w2c_pit_v2_1_primary_asset_collect.py",
        "scripts/w2c_pit_v2_1_build_combined.py",
        "scripts/w2c_pit_v2_1_gate_score.py",
    ]
    forbidden_refs = [
        "registry/w2a_results",
        "data/art030",
        "registry/art030_",
        "w2a_funded_portfolio_summary",
        "art030_primary_inference",
        "art030_model_metrics",
        "art030_trial_results",
    ]
    for path in code_paths:
        text = (ROOT / path).read_text(encoding="utf-8").lower()
        for bad in forbidden_refs:
            assert bad.lower() not in text, f"PERFORMANCE_FIREWALL_REFERENCE {path}: {bad}"

    # Network scope is frozen to the already-preregistered Layer B/C operational
    # hosts. This check prevents a silent endpoint/source rescue after coverage is
    # observed. Synthetic URLs live in a test file and are not scanned here.
    collector = (ROOT / "scripts/w2c_pit_v2_1_primary_asset_collect.py").read_text(encoding="utf-8")
    hosts = {
        urlparse(url).hostname
        for url in re.findall(r'https://[^"\s]+', collector)
        if urlparse(url).hostname
    }
    allowed_hosts = {
        "www.sec.gov",
        "data.sec.gov",
        "www.fda.gov",
        "www.bls.gov",
        "www.bea.gov",
        "query1.finance.yahoo.com",
    }
    assert hosts <= allowed_hosts, f"UNFROZEN_NETWORK_HOSTS {sorted(hosts - allowed_hosts)}"

    # No-network scientific/adversarial validation. These scripts may materialize
    # disposable validation outputs in the CI workspace, but they do not alter the
    # frozen Git objects above and do not perform real Layer B/C collection.
    py = sys.executable
    run(py, "-m", "py_compile", *[p for p in objects if p.endswith(".py")])
    run(py, "scripts/w2c_pit_v2_population_validate.py")
    run(py, "scripts/w2c_pit_v2_1_synthetic_validation.py")
    run(py, "scripts/w2c_pit_v2_1_execution_synthetic.py")
    run(py, "scripts/repository_hygiene_validate.py")

    result = {
        "artifact": "W2C_PIT_V2_1_FREEZE_VALIDATION",
        "version": "W2C-PIT-FREEZE-VALIDATION-v2.1",
        "status": "PASS",
        "bundle_sha256": digest,
        "object_count": len(objects),
        "population_total": 260,
        "layer_a_byte_identical": True,
        "network_called": False,
        "performance_blind": True,
        "science_reopened": False,
        "layer_b_c_network_execution_authorized": False,
        "f1_f9_real_execution_authorized": False,
        "ias_real_scoring_authorized": False,
        "smaa_ranking_authorized": False,
        "w3_execution_authorized": False,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

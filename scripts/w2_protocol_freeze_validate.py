#!/usr/bin/env python3
"""Fail-closed byte freeze validator for the W2-A/W2-B protocol contracts."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "registry/w2_protocol_freeze_manifest.json"
COMBINED = ROOT / "registry/w2_protocol_synthetic_validation_combined.json"
EXPECTED_BUNDLE = "e7b48d08f657aea7552f2a692f19c1b941ebd678aa03d8ff28b961c0b317777b"
EXPECTED = {
    "registry/w2a_portfolio_accounting_protocol_draft.json": "639f900eb876d6e46ecbeb10c1b3b3e6c3621a28",
    "registry/w2b_ias_protocol_draft.json": "cb9a9638f236c6c61c97f86805de9bf666209b21",
}


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


def bundle_id(items: dict[str, str]) -> str:
    h = hashlib.sha256()
    for path, sha in sorted(items.items()):
        h.update(path.encode("utf-8") + b"\0" + sha.encode("ascii") + b"\n")
    return h.hexdigest()


def record(checks: list[dict], name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "pass": bool(passed), "detail": detail})


def main() -> int:
    checks: list[dict] = []

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    combined = json.loads(COMBINED.read_text(encoding="utf-8"))

    record(checks, "manifest_version", manifest.get("version") == "W2PF-v1.0", str(manifest.get("version")))
    record(checks, "manifest_science_closed", manifest.get("science_reopened") is False, str(manifest.get("science_reopened")))
    record(checks, "source_commit", manifest.get("source_commit") == "ede3b4c9b88b1c699424e0f3bcc76ddb37b404bc", str(manifest.get("source_commit")))

    actual: dict[str, str] = {}
    for path, expected_sha in EXPECTED.items():
        p = ROOT / path
        if not p.exists():
            record(checks, f"exists:{path}", False, "missing")
            continue
        sha = git_blob_sha(p.read_bytes())
        actual[path] = sha
        record(checks, f"blob:{path}", sha == expected_sha, f"actual={sha} expected={expected_sha}")

    calc_bundle = bundle_id(actual) if len(actual) == len(EXPECTED) else "INCOMPLETE"
    record(checks, "bundle_id", calc_bundle == EXPECTED_BUNDLE, calc_bundle)
    record(checks, "manifest_bundle_id", manifest.get("freeze_bundle_id_sha256") == EXPECTED_BUNDLE, str(manifest.get("freeze_bundle_id_sha256")))

    listed = {x.get("path"): x.get("git_blob_sha1") for x in manifest.get("frozen_contracts", [])}
    record(checks, "manifest_contract_list", listed == EXPECTED, json.dumps(listed, sort_keys=True))

    w2a = json.loads((ROOT / "registry/w2a_portfolio_accounting_protocol_draft.json").read_text(encoding="utf-8"))
    w2b = json.loads((ROOT / "registry/w2b_ias_protocol_draft.json").read_text(encoding="utf-8"))
    record(checks, "w2a_ready_source_state", w2a.get("status") == "PASS_SYNTHETIC_VALIDATION_READY_FOR_FREEZE_NOT_FROZEN", str(w2a.get("status")))
    record(checks, "w2b_ready_source_state", w2b.get("status") == "PASS_SYNTHETIC_VALIDATION_READY_FOR_FREEZE_NOT_FROZEN", str(w2b.get("status")))
    record(checks, "w2a_no_science_reopen", w2a.get("science_reopened") is False, str(w2a.get("science_reopened")))
    record(checks, "w2b_no_science_reopen", w2b.get("science_reopened") is False, str(w2b.get("science_reopened")))

    record(checks, "synthetic_combined_status", combined.get("status") == "PASS_38_OF_38_SYNTHETIC_CASES_READY_FOR_FREEZE", str(combined.get("status")))
    record(checks, "synthetic_38_of_38", combined.get("total_cases") == 38 and combined.get("total_pass") == 38, f"{combined.get('total_pass')}/{combined.get('total_cases')}")
    record(checks, "synthetic_no_real_argos_performance", combined.get("real_argos_performance_read") is False, str(combined.get("real_argos_performance_read")))
    record(checks, "synthetic_no_real_ias_scores", combined.get("real_ias_family_scores_read") is False, str(combined.get("real_ias_family_scores_read")))
    record(checks, "synthetic_science_closed", combined.get("science_reopened") is False, str(combined.get("science_reopened")))

    authority = manifest.get("authority_after_freeze", {})
    record(checks, "w3_still_not_authorized", str(authority.get("w3_execution", "")).startswith("NOT_AUTHORIZED"), str(authority.get("w3_execution")))

    passed = all(c["pass"] for c in checks)
    result = {
        "artifact": "W2_PROTOCOL_BYTE_FREEZE_VALIDATION",
        "decision": "PASS_W2_PROTOCOL_BYTE_FREEZE" if passed else "FAIL_W2_PROTOCOL_BYTE_FREEZE",
        "checks_total": len(checks),
        "checks_pass": sum(1 for c in checks if c["pass"]),
        "checks_fail": sum(1 for c in checks if not c["pass"]),
        "freeze_bundle_id_sha256": calc_bundle,
        "science_reopened": False,
        "checks": checks,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

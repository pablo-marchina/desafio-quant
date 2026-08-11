#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_bytes(path: str) -> bytes:
    return (ROOT / path).read_bytes()


def read_json(path: str):
    return json.loads(read_bytes(path).decode("utf-8"))


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def fail(message: str):
    raise RuntimeError(message)


fst = read_json("registry/final_scientific_truth.json")
sf = read_json("registry/final_submission_answers_sf_v3.json")
manifest = read_json("registry/final_submission_manifest.json")
art030 = read_json("registry/art030_summary.json")
fer = read_json("registry/final_evidence_reconciliation_summary.json")
genai = read_json("registry/genai_usage_summary.json")
status_text = read_bytes("STATUS.yaml").decode("utf-8")

expected_state = {
    "H1": "SUPPORTED_IN_TESTED_SAMPLE",
    "H2": "FAIL_UNDER_FROZEN_EXP07I",
    "H3": "BLOCKED_BY_H2_FAIL_NO_RESCUE",
    "H4": "BLOCKED_BY_H2_FAIL",
    "H5": "BLOCKED_BY_H4",
}
if fst.get("scientific_state") != expected_state:
    fail(f"FST scientific state mismatch: {fst.get('scientific_state')}")
if manifest.get("final_state", {}).get("H2") != expected_state["H2"]:
    fail("Manifest does not preserve H2 FAIL")
if art030.get("decision") != "FAIL_H2" or not art030.get("stop_rule_applied"):
    fail("ART-030 FAIL_H2/stop rule lock missing")
if manifest.get("art030_lock", {}).get("post_hoc_rescue_permitted") is not False:
    fail("Post-hoc rescue must be false")

if sf.get("version") != "SF-v3.0" or sf.get("status") != "FINAL_TRUTH_ALIGNED_H2_FAIL":
    fail("SF-v3 final status missing")
if len(sf.get("fields", [])) != 7:
    fail("SF-v3 must contain exactly seven fields")
logic = next((x.get("answer", "") for x in sf["fields"] if x.get("field") == "Lógica da Estratégia"), "")
for token in ("M_MOVE_CORE", "H2", "no-trade"):
    if token not in logic:
        fail(f"SF-v3 strategy logic missing required token: {token}")

claims_text = read_bytes("registry/final_submission_claims.csv").decode("utf-8")
claims = list(csv.DictReader(io.StringIO(claims_text)))
if not any(r["classification"] == "PROHIBITED" and "insiders" in r["claim_text"].lower() for r in claims):
    fail("Insider overclaim prohibition missing")
if not any(r["classification"] == "PROHIBITED" and "alpha" in r["claim_text"].lower() for r in claims):
    fail("Alpha overclaim prohibition missing")
if not any(r["classification"] == "PERMITTED" and "não acrescentou" in r["claim_text"].lower() for r in claims):
    fail("Explicit permitted negative H2 claim missing")

numbers_text = read_bytes("registry/final_submission_numbers.csv").decode("utf-8")
nums = {r["number_id"]: r for r in csv.DictReader(io.StringIO(numbers_text))}
checks = {
    "FNUM-002": art030["model_metrics"]["p_M2_CAL"]["brier"],
    "FNUM-003": art030["model_metrics"]["p_M_MOVE_CORE"]["brier"],
    "FNUM-006": art030["model_metrics"]["p_M2_CAL"]["log_loss"],
    "FNUM-007": art030["model_metrics"]["p_M_MOVE_CORE"]["log_loss"],
    "FNUM-010": art030["scored_events"],
    "FNUM-011": art030["scored_date_clusters"],
}
for key, expected in checks.items():
    if key not in nums:
        fail(f"Missing frozen number {key}")
    actual = float(nums[key]["value"])
    if abs(actual - float(expected)) > 1e-12:
        fail(f"Frozen number mismatch {key}: {actual} != {expected}")

if fer.get("official_eps", {}).get("independently_validated") != 116:
    fail("EPS independent coverage must remain 116")
if fer.get("official_eps", {}).get("validated_mismatches") != 0:
    fail("EPS mismatches must remain zero")
if fer.get("official_eps", {}).get("remaining_event_keys") != ["BLSH|2025-09-17"]:
    fail("BLSH residual must be preserved exactly")
if genai.get("decision") != "PASS_GENAI_LEDGER_FINAL_EVIDENCE_SYNC" or genai.get("entries") != 11:
    fail("GenAI final ledger sync missing")

contract = manifest.get("report_contract", {})
if contract != {
    "format": "PDF",
    "max_pages": 5,
    "aspect_ratio": "16:9",
    "language": "pt-BR",
    "anonymous": True,
    "public_repository_url_in_submission": False,
}:
    fail(f"Report contract mismatch: {contract}")

if "current_phase: FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE" not in status_text:
    fail("STATUS not at expected pre-finalization phase")
for needle in (
    "H2: FAIL_UNDER_FROZEN_EXP07I",
    "H3: BLOCKED_BY_H2_FAIL_NO_RESCUE",
    "H4: BLOCKED_BY_H2_FAIL",
    "H5: BLOCKED_BY_H4",
):
    if needle not in status_text:
        fail(f"STATUS missing lock: {needle}")

# Verify every Git artifact recorded in the manifest against repository bytes.
for item in manifest.get("github_artifacts", []):
    path = item["path"]
    actual = git_blob_sha(read_bytes(path))
    if actual != item["git_blob_sha"]:
        fail(f"Manifest git blob mismatch for {path}: {actual} != {item['git_blob_sha']}")

bundle_paths = sorted(item["path"] for item in manifest["github_artifacts"])
h = hashlib.sha256()
for path in bundle_paths:
    data = read_bytes(path)
    h.update(path.encode("utf-8") + b"\0" + len(data).to_bytes(8, "big") + data)
bundle_sha256 = h.hexdigest()

validation = {
    "artifact": "FINAL_SUBMISSION_FREEZE_VALIDATION",
    "decision": "PASS_FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_WITH_DISCLOSED_EPS_RESIDUAL_1",
    "fst_version": "FST-v1.0",
    "sf_version": "SF-v3.0",
    "h2_preserved": "FAIL_UNDER_FROZEN_EXP07I",
    "post_hoc_rescue_permitted": False,
    "seven_submission_fields": 7,
    "official_eps_independent_coverage": "116/117",
    "official_eps_validated_mismatches": 0,
    "eps_residual": "BLSH|2025-09-17",
    "genai_entries": 11,
    "manifest_git_artifacts_verified": len(manifest["github_artifacts"]),
    "bundle_sha256": bundle_sha256,
    "report_contract": contract,
    "authorized_next_phase": "FINAL_REPORT_AUTHORING_AND_QA",
}
output = ROOT / "registry/final_submission_freeze_validation.json"
output.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(validation, indent=2, ensure_ascii=False))

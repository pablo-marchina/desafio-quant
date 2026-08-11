#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "STATUS.yaml"
s = p.read_text(encoding="utf-8")
validation = json.loads((ROOT / "registry/final_submission_freeze_validation.json").read_text(encoding="utf-8"))
manifest = json.loads((ROOT / "registry/final_submission_manifest.json").read_text(encoding="utf-8"))

if validation.get("decision") != "PASS_FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_WITH_DISCLOSED_EPS_RESIDUAL_1":
    raise RuntimeError("freeze validation PASS missing")
if manifest.get("authorized_next_phase") != "FINAL_REPORT_AUTHORING_AND_QA":
    raise RuntimeError("manifest next phase mismatch")
for required in (
    "current_phase: FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE",
    "H2: FAIL_UNDER_FROZEN_EXP07I",
    "H3: BLOCKED_BY_H2_FAIL_NO_RESCUE",
    "H4: BLOCKED_BY_H2_FAIL",
    "H5: BLOCKED_BY_H4",
):
    if required not in s:
        raise RuntimeError(f"STATUS precondition missing: {required}")

# Advance phase once.
s = s.replace(
    "current_phase: FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE",
    "current_phase: FINAL_REPORT_AUTHORING_AND_QA",
    1,
)

# Replace the scientific-freeze header block while preserving implementation below.
start = s.index("scientific_freeze:\n")
end = s.index("implementation:\n", start)
new_freeze = """scientific_freeze:\n  thesis: TF-v1.0\n  constitution: ART-027_FREEZE_v1.0\n  final_truth: FST-v1.0\n  current_truth: CT-v4.0\n  submission_freeze: SF-v3.0\n  submission_freeze_previous_stage: SF-v2.0\n  status: PASS_FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_WITH_DISCLOSED_EPS_RESIDUAL_1\nfinal_submission_freeze:\n  status: PASS_FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_WITH_DISCLOSED_EPS_RESIDUAL_1\n  fst_version: FST-v1.0\n  sf_version: SF-v3.0\n  ct_version: CT-v4.0\n  hm_version: HM-v4.0\n  h2_preserved: FAIL_UNDER_FROZEN_EXP07I\n  post_hoc_rescue_permitted: false\n  official_eps_independent_validation: 116/117\n  official_eps_validated_mismatches: 0\n  official_eps_residual: BLSH|2025-09-17\n  residual_is_blocker: false\n  residual_is_material_limitation: true\n  genai_ledger_entries: 11\n  bundle_sha256: %s\n  truth_path: registry/final_scientific_truth.json\n  answers_path: registry/final_submission_answers_sf_v3.json\n  claims_path: registry/final_submission_claims.csv\n  numbers_path: registry/final_submission_numbers.csv\n  manifest_path: registry/final_submission_manifest.json\n  validation_path: registry/final_submission_freeze_validation.json\n  report_path: docs/29_final_scientific_truth_submission_freeze.md\n  current_truth_drive_id: 1MRWhaYaVkEwBVJTWTWtwziK7qQtFOtxJsvabzUV5Msw\n  hypothesis_matrix_drive_id: 1h1JAzYdqFurIP17_69c1ZWqcKI1NzrAbChi-DGLC8io\n  source_registry_drive_id: 12dGCC306uEVNC62qU8nUKL_jT__WKSD1jhzBT-VHXHk\n""" % validation["bundle_sha256"]
s = s[:start] + new_freeze + s[end:]

# Close the freeze critical-path marker and advance to authoring/QA.
old_cp = "  - FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE\n"
if old_cp in s:
    s = s.replace(
        old_cp,
        "  - FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_COMPLETED\n  - FINAL_REPORT_AUTHORING_AND_QA\n",
        1,
    )
elif "  - FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_COMPLETED\n" not in s:
    raise RuntimeError("final freeze critical-path marker missing")

# No scientific blocker remains for report authoring. BLSH stays in limitations.
if "blockers:\n" not in s or "limitations:\n" not in s:
    raise RuntimeError("blocker/limitation sections missing")
b0 = s.index("blockers:\n")
b1 = s.index("limitations:\n", b0)
s = s[:b0] + "blockers: []\n" + s[b1:]

# Final readback invariants.
for required in (
    "current_phase: FINAL_REPORT_AUTHORING_AND_QA",
    "final_truth: FST-v1.0",
    "current_truth: CT-v4.0",
    "submission_freeze: SF-v3.0",
    "post_hoc_rescue_permitted: false",
    "official_eps_residual: BLSH|2025-09-17",
    "blockers: []",
    "  - FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_COMPLETED",
    "  - FINAL_REPORT_AUTHORING_AND_QA",
):
    if required not in s:
        raise RuntimeError(f"STATUS final invariant missing: {required}")
for forbidden in (
    "FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_NOT_EXECUTED",
    "OFFICIAL_EPS_INDEPENDENT_RECONSTRUCTION_RESIDUAL_1_BLSH_2025_09_17\n  -",
):
    if forbidden in s:
        raise RuntimeError(f"stale blocker survived: {forbidden}")

p.write_text(s, encoding="utf-8")
print("PASS_STATUS_FINAL_REPORT_AUTHORING_AND_QA")

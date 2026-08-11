#!/usr/bin/env python3
"""Fail-closed hygiene checks for the post-freeze ARGOS repository.

This validator does not re-run science. It verifies that the active navigation layer
reflects FST-v1.0/SF-v3.0 and that historical evidence remains clearly separated.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "README.md",
    "STATUS.yaml",
    ".gitignore",
    ".gitattributes",
    "docs/README.md",
    "docs/00_current_truth.md",
    "docs/01_challenge_requirements.md",
    "docs/02_thesis_governance.md",
    "docs/03_data_provenance.md",
    "docs/04_experiments_results.md",
    "docs/05_claim_registry.md",
    "docs/06_final_report_plan.md",
    "docs/07_audit_gaps.md",
    "docs/08_source_index.md",
    "docs/09_project_history.md",
    "docs/10_genai_ledger.md",
    "docs/29_final_scientific_truth_submission_freeze.md",
    "registry/README.md",
    "registry/final_scientific_truth.json",
    "registry/final_submission_answers_sf_v3.json",
    "registry/final_submission_claims.csv",
    "registry/final_submission_numbers.csv",
    "registry/final_submission_manifest.json",
    "registry/final_submission_freeze_validation.json",
    "scripts/README.md",
    ".github/workflows/README.md",
]

ACTIVE_DOCS = [
    "README.md",
    "docs/00_current_truth.md",
    "docs/03_data_provenance.md",
    "docs/04_experiments_results.md",
    "docs/05_claim_registry.md",
    "docs/06_final_report_plan.md",
    "docs/07_audit_gaps.md",
    "docs/08_source_index.md",
    "docs/09_project_history.md",
    "docs/10_genai_ledger.md",
]

STALE_PATTERNS = [
    "h2: pendente",
    "h2 ainda não executada",
    "66 permanecem pendentes",
    "principal gate atual",
    "próximo caminho crítico: `art-028",
    "esse é o experimento decisivo que falta",
    "bloqueado para uso final até reconciliação",
]


def read_text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def record(checks: list[dict], name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "pass": bool(passed), "detail": detail})


def main() -> int:
    checks: list[dict] = []

    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).exists()]
    record(checks, "required_paths", not missing, "missing=" + ",".join(missing) if missing else "all present")

    try:
        fst = json.loads(read_text("registry/final_scientific_truth.json"))
        record(checks, "fst_version", fst.get("version") == "FST-v1.0", str(fst.get("version")))
        record(
            checks,
            "fst_h2",
            fst.get("scientific_state", {}).get("H2") == "FAIL_UNDER_FROZEN_EXP07I",
            str(fst.get("scientific_state", {}).get("H2")),
        )
        record(
            checks,
            "fst_no_post_hoc_reopen",
            "post-hoc" in fst.get("reopen_rule", "").lower(),
            fst.get("reopen_rule", ""),
        )
    except Exception as exc:  # fail closed
        record(checks, "fst_parse", False, repr(exc))

    try:
        freeze = json.loads(read_text("registry/final_submission_freeze_validation.json"))
        record(
            checks,
            "freeze_decision",
            freeze.get("decision") == "PASS_FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_WITH_DISCLOSED_EPS_RESIDUAL_1",
            str(freeze.get("decision")),
        )
        record(checks, "freeze_h2", freeze.get("h2_preserved") == "FAIL_UNDER_FROZEN_EXP07I", str(freeze.get("h2_preserved")))
        record(checks, "freeze_no_rescue", freeze.get("post_hoc_rescue_permitted") is False, str(freeze.get("post_hoc_rescue_permitted")))
        record(checks, "freeze_seven_fields", freeze.get("seven_submission_fields") == 7, str(freeze.get("seven_submission_fields")))
        record(
            checks,
            "freeze_next_phase",
            freeze.get("authorized_next_phase") == "FINAL_REPORT_AUTHORING_AND_QA",
            str(freeze.get("authorized_next_phase")),
        )
    except Exception as exc:
        record(checks, "freeze_parse", False, repr(exc))

    status = read_text("STATUS.yaml") if (ROOT / "STATUS.yaml").exists() else ""
    for key, needle in {
        "status_phase": "current_phase: FINAL_REPORT_AUTHORING_AND_QA",
        "status_h2": "H2: FAIL_UNDER_FROZEN_EXP07I",
        "status_fst": "final_truth: FST-v1.0",
        "status_sf": "submission_freeze: SF-v3.0",
        "status_bundle": "c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885",
    }.items():
        record(checks, key, needle in status, needle)

    stale_hits: list[str] = []
    for rel in ACTIVE_DOCS:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for pattern in STALE_PATTERNS:
            if pattern in text:
                stale_hits.append(f"{rel}: {pattern}")
    record(checks, "active_docs_no_stale_state", not stale_hits, "; ".join(stale_hits) if stale_hits else "no stale patterns")

    readme = read_text("README.md") if (ROOT / "README.md").exists() else ""
    for name, needle in {
        "readme_h2_fail": "FAIL_UNDER_FROZEN_EXP07I",
        "readme_no_trade": "C0_NO_TRADE",
        "readme_phase": "FINAL_REPORT_AUTHORING_AND_QA",
        "readme_authority": "registry/final_scientific_truth.json",
    }.items():
        record(checks, name, needle in readme, needle)

    claims = read_text("registry/final_submission_claims.csv") if (ROOT / "registry/final_submission_claims.csv").exists() else ""
    record(checks, "claims_has_permitted", ",PERMITTED," in claims, "PERMITTED class present")
    record(checks, "claims_has_prohibited", ",PROHIBITED," in claims, "PROHIBITED class present")
    record(checks, "claims_h2_fail_boundary", "H2 falhou" in claims or "H2 failed" in claims, "explicit H2 failure boundary")

    numbers = read_text("registry/final_submission_numbers.csv") if (ROOT / "registry/final_submission_numbers.csv").exists() else ""
    record(checks, "numbers_h2_n", "FNUM-010,H2,Scored events,75" in numbers, "75 scored events")
    record(checks, "numbers_eps_116_117", "116/117" in numbers, "116/117 EPS validation")

    passed = all(c["pass"] for c in checks)
    result = {
        "artifact": "REPOSITORY_HYGIENE_VALIDATION",
        "decision": "PASS_REPOSITORY_HYGIENE" if passed else "FAIL_REPOSITORY_HYGIENE",
        "checks_total": len(checks),
        "checks_pass": sum(1 for c in checks if c["pass"]),
        "checks_fail": sum(1 for c in checks if not c["pass"]),
        "science_reopened": False,
        "expected_phase": "FINAL_REPORT_AUTHORING_AND_QA",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

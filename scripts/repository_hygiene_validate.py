#!/usr/bin/env python3
"""Fail-closed hygiene checks for the post-freeze ARGOS repository.

This validator is intentionally post-finalization aware. It does not re-run or mutate
science; it verifies that the frozen bundle is byte-identical to its manifest and that
the active navigation layer reflects FST-v1.0/SF-v3.0.
"""

from __future__ import annotations

import csv
import hashlib
import io
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
    "registry/art030_summary.json",
    "registry/final_evidence_reconciliation_summary.json",
    "registry/genai_usage_summary.json",
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

EXPECTED_BUNDLE = "c83b0868f3b397832e16bbeaab00da5f6a0d7be3b0e29c40be9fea351b43d885"


def read_bytes(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def read_text(rel: str) -> str:
    return read_bytes(rel).decode("utf-8")


def read_json(rel: str):
    return json.loads(read_text(rel))


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def record(checks: list[dict], name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "pass": bool(passed), "detail": detail})


def main() -> int:
    checks: list[dict] = []

    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).exists()]
    record(checks, "required_paths", not missing, "missing=" + ",".join(missing) if missing else "all present")

    try:
        fst = read_json("registry/final_scientific_truth.json")
        expected_state = {
            "H1": "SUPPORTED_IN_TESTED_SAMPLE",
            "H2": "FAIL_UNDER_FROZEN_EXP07I",
            "H3": "BLOCKED_BY_H2_FAIL_NO_RESCUE",
            "H4": "BLOCKED_BY_H2_FAIL",
            "H5": "BLOCKED_BY_H4",
        }
        record(checks, "fst_version", fst.get("version") == "FST-v1.0", str(fst.get("version")))
        record(checks, "fst_state", fst.get("scientific_state") == expected_state, str(fst.get("scientific_state")))
        record(checks, "fst_no_post_hoc_reopen", "post-hoc" in fst.get("reopen_rule", "").lower(), fst.get("reopen_rule", ""))
    except Exception as exc:
        record(checks, "fst_parse", False, repr(exc))

    try:
        sf = read_json("registry/final_submission_answers_sf_v3.json")
        record(checks, "sf_version", sf.get("version") == "SF-v3.0", str(sf.get("version")))
        record(checks, "sf_status", sf.get("status") == "FINAL_TRUTH_ALIGNED_H2_FAIL", str(sf.get("status")))
        record(checks, "sf_seven_fields", len(sf.get("fields", [])) == 7, str(len(sf.get("fields", []))))
    except Exception as exc:
        record(checks, "sf_parse", False, repr(exc))

    try:
        art030 = read_json("registry/art030_summary.json")
        record(checks, "art030_fail_h2", art030.get("decision") == "FAIL_H2", str(art030.get("decision")))
        record(checks, "art030_stop_rule", art030.get("stop_rule_applied") is True, str(art030.get("stop_rule_applied")))
        record(checks, "art030_n", art030.get("scored_events") == 75 and art030.get("scored_date_clusters") == 54, f"n={art030.get('scored_events')}, clusters={art030.get('scored_date_clusters')}")
    except Exception as exc:
        record(checks, "art030_parse", False, repr(exc))

    try:
        fer = read_json("registry/final_evidence_reconciliation_summary.json")
        eps = fer.get("official_eps", {})
        record(checks, "eps_116_117", eps.get("independently_validated") == 116, str(eps.get("independently_validated")))
        record(checks, "eps_zero_mismatch", eps.get("validated_mismatches") == 0, str(eps.get("validated_mismatches")))
        record(checks, "eps_blsH_residual", eps.get("remaining_event_keys") == ["BLSH|2025-09-17"], str(eps.get("remaining_event_keys")))
    except Exception as exc:
        record(checks, "fer_parse", False, repr(exc))

    try:
        genai = read_json("registry/genai_usage_summary.json")
        record(checks, "genai_sync", genai.get("decision") == "PASS_GENAI_LEDGER_FINAL_EVIDENCE_SYNC", str(genai.get("decision")))
        record(checks, "genai_entries", genai.get("entries") == 11, str(genai.get("entries")))
    except Exception as exc:
        record(checks, "genai_parse", False, repr(exc))

    try:
        manifest = read_json("registry/final_submission_manifest.json")
        blob_failures: list[str] = []
        for item in manifest.get("github_artifacts", []):
            path = item["path"]
            actual = git_blob_sha(read_bytes(path))
            if actual != item["git_blob_sha"]:
                blob_failures.append(f"{path}:{actual}!={item['git_blob_sha']}")
        record(checks, "manifest_git_blobs", not blob_failures and len(manifest.get("github_artifacts", [])) == 8, ";".join(blob_failures) if blob_failures else "8/8 verified")

        bundle_paths = sorted(item["path"] for item in manifest.get("github_artifacts", []))
        h = hashlib.sha256()
        for path in bundle_paths:
            data = read_bytes(path)
            h.update(path.encode("utf-8") + b"\0" + len(data).to_bytes(8, "big") + data)
        bundle = h.hexdigest()
        record(checks, "manifest_bundle_sha256", bundle == EXPECTED_BUNDLE, bundle)
        record(checks, "manifest_next_phase", manifest.get("authorized_next_phase") == "FINAL_REPORT_AUTHORING_AND_QA", str(manifest.get("authorized_next_phase")))
    except Exception as exc:
        record(checks, "manifest_parse", False, repr(exc))

    try:
        freeze = read_json("registry/final_submission_freeze_validation.json")
        record(checks, "freeze_pass", freeze.get("decision") == "PASS_FINAL_SCIENTIFIC_TRUTH_SUBMISSION_FREEZE_WITH_DISCLOSED_EPS_RESIDUAL_1", str(freeze.get("decision")))
        record(checks, "freeze_bundle", freeze.get("bundle_sha256") == EXPECTED_BUNDLE, str(freeze.get("bundle_sha256")))
        record(checks, "freeze_no_rescue", freeze.get("post_hoc_rescue_permitted") is False, str(freeze.get("post_hoc_rescue_permitted")))
        record(checks, "freeze_next_phase", freeze.get("authorized_next_phase") == "FINAL_REPORT_AUTHORING_AND_QA", str(freeze.get("authorized_next_phase")))
    except Exception as exc:
        record(checks, "freeze_parse", False, repr(exc))

    status = read_text("STATUS.yaml") if (ROOT / "STATUS.yaml").exists() else ""
    for key, needle in {
        "status_phase": "current_phase: FINAL_REPORT_AUTHORING_AND_QA",
        "status_h2": "H2: FAIL_UNDER_FROZEN_EXP07I",
        "status_fst": "final_truth: FST-v1.0",
        "status_sf": "submission_freeze: SF-v3.0",
        "status_bundle": EXPECTED_BUNDLE,
        "status_no_blockers": "blockers: []",
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

    claims_text = read_text("registry/final_submission_claims.csv") if (ROOT / "registry/final_submission_claims.csv").exists() else ""
    claims = list(csv.DictReader(io.StringIO(claims_text))) if claims_text else []
    record(checks, "claims_has_permitted", any(r.get("classification") == "PERMITTED" for r in claims), "PERMITTED class")
    record(checks, "claims_has_prohibited", any(r.get("classification") == "PROHIBITED" for r in claims), "PROHIBITED class")
    record(checks, "claims_negative_h2", any(r.get("classification") == "PERMITTED" and "não acrescentou" in r.get("claim_text", "").lower() for r in claims), "explicit negative H2 claim")

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
        "frozen_bundle_sha256": EXPECTED_BUNDLE,
        "science_reopened": False,
        "expected_phase": "FINAL_REPORT_AUTHORING_AND_QA",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

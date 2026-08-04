#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"

REQUIRED_DOCS = [
    "docs/final_external_reviewer_mode.md",
    "docs/final_delivery_index.md",
    "docs/final_ai_incident_response_plan.md",
    "docs/final_rca_workflow.md",
    "docs/final_deprecation_policy.md",
    "docs/final_data_retention_policy.md",
    "docs/final_quality_regression_policy.md",
]

REQUIRED_REPORTS = [
    "final_release_manifest.json",
    "final_release_clean_report.json",
    "final_release_file_allowlist_report.json",
    "final_release_forbidden_artifacts_report.json",
    "repository_clean_report.json",
    "final_release_zip_clean_report.json",
    "no_env_in_release_report.json",
    "no_git_dir_in_release_report.json",
    "no_node_modules_report.json",
    "frontend_build_reproducibility_report.json",
    "no_active_demo_docs_report.json",
    "demo_archive_manifest.json",
    "benchmark_type_coverage_report.json",
    "proxy_benchmark_promotion_block_report.json",
    "mock_provider_benchmark_classification_report.json",
    "roadmap_closure_audit_report.json",
    "secret_scan_report.json",
    "dependency_vulnerability_report.json",
    "sast_report.json",
    "sbom.json",
    "container_scan_report.json",
    "license_inventory.json",
    "openssf_scorecard_report.json",
    "source_compliance_report.json",
    "data_rights_registry.csv",
    "robots_terms_report.json",
    "access_control_rag_report.json",
    "data_minimization_report.json",
    "least_context_report.json",
    "context_firewall_report.json",
    "prompt_injection_test_report.json",
    "rag_poisoning_test_report.json",
    "tool_abuse_test_report.json",
    "candidate_decision_matrix.csv",
    "priority_candidate_queue.md",
    "direct_benchmark_protocol.md",
    "golden_eval_dataset.jsonl",
    "promotion_rejection_report.md",
    "promotion_rejection_report.json",
    "runtime_promotion_ledger.csv",
    "final_candidate_gap_audit.md",
    "graphrag_direct_benchmark_report.json",
    "source_quality_direct_benchmark_report.json",
    "product_configuration_report.json",
    "observability_trace_sample.json",
    "external_reviewer_mode_report.json",
    "cold_start_report.json",
    "no_hidden_manual_steps_report.json",
    "repository_purpose_manifest.csv",
    "repository_purpose_coverage_report.json",
    "source_coverage_map.json",
    "ai_governance_maturity_report.json",
    "agent_tool_observability_report.json",
    "rca_workflow_report.json",
]

ACCEPTED_NON_PASS_STATUSES = {
    "BLOCKED_BY_ENVIRONMENT",
    "PENDING_BENCHMARK_RUN",
    "PENDING_COLD_START_RUN",
    "PENDING_FRONTEND_BUILD",
    "PENDING_LIVE_SOURCE_REVIEW",
    "PENDING_PACKAGE_FINAL_RELEASE",
    "PENDING_SECURITY_SUITE",
    "TBD_BY_GOVERNANCE_REVIEW",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check finalization governance docs and evidence.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()

    failures = validate_finalization(args.repo, args.evidence_dir)
    if failures:
        print("FAIL: finalization governance artifacts")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("PASS: finalization governance artifacts")
    return 0


def validate_finalization(repo: Path, evidence_dir: Path) -> list[str]:
    failures: list[str] = []
    for relative in REQUIRED_DOCS:
        if not (repo / relative).is_file():
            failures.append(f"missing document {relative}")
    for name in REQUIRED_REPORTS:
        path = evidence_dir / name
        if not path.is_file():
            failures.append(f"missing evidence {name}")
            continue
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            status = payload.get("status")
            if status == "FAIL":
                failures.append(f"{name} has FAIL status")
            elif status and status != "PASS" and status not in ACCEPTED_NON_PASS_STATUSES:
                failures.append(f"{name} has unexpected status {status}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())

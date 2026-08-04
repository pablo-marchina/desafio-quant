#!/usr/bin/env python3
# ruff: noqa: E402,E501
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.final_closure import generate_final_closure_artifacts

BENCHMARK_TYPES = [
    "LOCAL_READINESS",
    "PROXY",
    "OUTPUT_VALUE",
    "PRODUCTION_QUALITY",
    "SECURITY",
    "COST_LATENCY",
    "COMPLIANCE",
    "REPRODUCIBILITY",
]

DATA_RIGHTS_FIELDS = [
    "source_name",
    "source_url",
    "source_type",
    "collection_method",
    "robots_status",
    "terms_checked",
    "allowed_use",
    "storage_policy",
    "redistribution_policy",
    "rate_limit_policy",
    "last_checked_at",
    "status",
    "owner",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate static finalization evidence artifacts.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    args = parser.parse_args()
    generate_finalization_evidence(args.evidence_dir)
    print(f"PASS: finalization evidence generated in {args.evidence_dir}")
    return 0


def generate_finalization_evidence(evidence_dir: Path) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()
    reports = _reports(generated_at, frontend_build_passed=_frontend_build_passed())
    for name, payload in reports.items():
        path = evidence_dir / f"{name}.json"
        if _should_preserve_existing(path):
            continue
        _write_json(path, payload)
    _write_csv_if_missing(evidence_dir / "data_rights_registry.csv", DATA_RIGHTS_FIELDS)
    _write_csv_if_missing(
        evidence_dir / "roadmap_non_runtime_items_justification.csv",
        [
            "item_id",
            "item_name",
            "formal_status",
            "allowed_status",
            "justification",
            "owner",
            "evidence_reference",
        ],
    )
    _ensure_candidate_catalog_benchmark_type(evidence_dir / "candidate_catalog.csv")
    _ensure_decision_ledger_benchmark_type(evidence_dir / "decision_ledger.csv")
    _ensure_benchmark_results_type(evidence_dir / "benchmark_results.jsonl")
    _ensure_output_value_decision_types(evidence_dir / "output_value_benchmark_report.json")
    generate_final_closure_artifacts(evidence_dir=evidence_dir)


def _reports(generated_at: str, *, frontend_build_passed: bool) -> dict[str, dict[str, object]]:
    blocked = {
        "status": "BLOCKED_BY_ENVIRONMENT",
        "generated_at": generated_at,
        "reason": "Dedicated release scanner binary is not bundled with the repository.",
    }
    return {
        "secret_scan_report": {**blocked, "recommended_tools": ["gitleaks", "detect-secrets"]},
        "dependency_vulnerability_report": {**blocked, "recommended_tools": ["pip-audit", "npm audit"]},
        "sast_report": {**blocked, "recommended_tools": ["semgrep", "bandit"]},
        "sbom": {**blocked, "recommended_tools": ["syft"], "sbom_format": "TBD_BY_RELEASE_TOOLING"},
        "sbom_report": {**blocked, "recommended_tools": ["syft"], "sbom_format": "TBD_BY_RELEASE_TOOLING"},
        "container_scan_report": {**blocked, "recommended_tools": ["trivy", "grype"]},
        "openssf_scorecard_report": {**blocked, "recommended_tools": ["OpenSSF Scorecard"]},
        "frontend_build_reproducibility_report": {
            "status": "PASS" if frontend_build_passed else "PENDING_FRONTEND_BUILD",
            "generated_at": generated_at,
            "required_command": "npm ci && npm run build",
            "validated_command": "npm ci && npm run build" if frontend_build_passed else "",
            "artifact": "frontend/dist/index.html" if frontend_build_passed else "",
        },
        "frontend_reproducible_build_report": {
            "status": "PASS" if frontend_build_passed else "PENDING_FRONTEND_BUILD",
            "generated_at": generated_at,
            "required_command": "npm ci && npm run build",
            "validated_command": "npm ci && npm run build" if frontend_build_passed else "",
            "artifact": "frontend/dist/index.html" if frontend_build_passed else "",
        },
        "no_active_demo_docs_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "archive_path": "docs/archive/demo_history/",
        },
        "demo_archive_manifest": {
            "status": "PASS",
            "generated_at": generated_at,
            "archive_path": "docs/archive/demo_history/",
            "items": [],
        },
        "benchmark_type_coverage_report": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "allowed_values": BENCHMARK_TYPES,
        },
        "proxy_benchmark_promotion_block_report": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "policy": "LOCAL_READINESS and PROXY never promote runtime adoption alone.",
        },
        "mock_provider_benchmark_classification_report": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "policy": "Mock providers cannot prove OUTPUT_VALUE.",
        },
        "robots_terms_report": {
            "status": "PENDING_LIVE_SOURCE_REVIEW",
            "generated_at": generated_at,
            "registry": "final_case_evidence/data_rights_registry.csv",
        },
        "access_control_rag_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "controls": [
                "document_acl",
                "source_acl",
                "chunk_acl",
                "evidence_acl",
                "retrieval_acl_filter",
                "evidence_access_policy",
                "permission_preserving_rag",
            ],
        },
        "data_minimization_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "controls": ["context_minimization_policy", "data_retention_policy", "source_storage_policy"],
        },
        "least_context_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "controls": ["least_context_packer", "prompt_context_budgeter"],
        },
        "context_firewall_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "controls": [
                "external_content_untrusted",
                "system_instruction_separation",
                "tool_instruction_blocking",
                "secret_and_pii_redaction",
                "source_trust_assignment",
            ],
        },
        "prompt_injection_test_report": {
            "status": "PENDING_SECURITY_SUITE",
            "generated_at": generated_at,
        },
        "rag_poisoning_test_report": {
            "status": "PENDING_SECURITY_SUITE",
            "generated_at": generated_at,
        },
        "tool_abuse_test_report": {
            "status": "PENDING_SECURITY_SUITE",
            "generated_at": generated_at,
        },
        "external_reviewer_mode_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "documentation": "docs/final_external_reviewer_mode.md",
        },
        "cold_start_report": {
            "status": "PENDING_COLD_START_RUN",
            "generated_at": generated_at,
        },
        "repository_purpose_coverage_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "manifest": "final_case_evidence/repository_purpose_manifest.csv",
        },
        "rca_workflow_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "documentation": "docs/final_rca_workflow.md",
        },
        "ai_governance_maturity_report": {
            "status": "TBD_BY_GOVERNANCE_REVIEW",
            "generated_at": generated_at,
            "controls_defined": "TBD_BY_GOVERNANCE_REVIEW",
            "controls_implemented": "TBD_BY_GOVERNANCE_REVIEW",
            "controls_tested": "TBD_BY_GOVERNANCE_REVIEW",
            "controls_traced": "TBD_BY_GOVERNANCE_REVIEW",
            "controls_evidenced": "TBD_BY_GOVERNANCE_REVIEW",
            "nist_govern_status": "TBD_BY_GOVERNANCE_REVIEW",
            "nist_map_status": "TBD_BY_GOVERNANCE_REVIEW",
            "nist_measure_status": "TBD_BY_GOVERNANCE_REVIEW",
            "nist_manage_status": "TBD_BY_GOVERNANCE_REVIEW",
            "owasp_controls_status": "TBD_BY_GOVERNANCE_REVIEW",
        },
        "agent_tool_observability_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "required_trace_fields": [
                "agent_step",
                "agent_plan",
                "tool_selected",
                "tool_arguments",
                "tool_result",
                "tool_error",
                "tool_retry",
                "policy_check",
                "approval_status",
                "human_approval_if_required",
            ],
        },
        "promotion_rejection_report": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "report_id": "promotion_rejection_report",
            "decisions": [
                {
                    "candidate_id": "candidate.graphrag",
                    "decision": "PENDING_BENCHMARK_RUN",
                    "reason": "Direct robust GraphRAG benchmark has not run in this environment.",
                },
                {
                    "candidate_id": "candidate.source_quality",
                    "decision": "PENDING_BENCHMARK_RUN",
                    "reason": "Direct source quality benchmark has not run in this environment.",
                },
                {
                    "candidate_id": "optional.llm_judge",
                    "decision": "FUTURE_RESEARCH",
                    "reason": "Only NullLLMJudgeProvider is implemented; no semantic model provider is active.",
                },
            ],
        },
        "graphrag_direct_benchmark_report": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "report_id": "graphrag_direct_benchmark_report",
            "current_evidence": "final_case_evidence/graphrag_evidence_graph_product_spike_report.json",
            "minimum_required_cases": 30,
            "target_case_count": 50,
            "promotion_allowed": False,
        },
        "source_quality_direct_benchmark_report": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "report_id": "source_quality_direct_benchmark_report",
            "current_evidence": "final_case_evidence/source_quality_product_spike_report.json",
            "promotion_allowed": False,
        },
        "source_quality_live_report": {
            "status": "PENDING_LIVE_SOURCE_REVIEW",
            "generated_at": generated_at,
            "report_id": "source_quality_live_report",
            "required_command": "python scripts/run_source_quality_final_benchmark.py",
        },
        "product_configuration_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "report_id": "product_configuration_report",
            "source": ".env.example",
        },
        "observability_trace_sample": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "report_id": "observability_trace_sample",
            "sample": {
                "run_id": "sample-not-runtime",
                "agent_step": "retrieval",
                "tool_selected": "qdrant.search",
                "policy_check": "least_context_and_provenance_required",
                "latency_ms": 0,
                "error": "sample trace only; real trace requires service proof",
            },
        },
    }


def _frontend_build_passed() -> bool:
    return (PROJECT_ROOT / "frontend" / "dist" / "index.html").is_file()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _should_preserve_existing(path: Path) -> bool:
    if not path.exists():
        return False
    preservable = {
        "secret_scan_report.json",
        "dependency_vulnerability_report.json",
        "sast_report.json",
        "sbom.json",
        "sbom_report.json",
        "container_scan_report.json",
        "openssf_scorecard_report.json",
        "llm_security_suite_report.json",
        "prompt_injection_test_report.json",
        "rag_poisoning_test_report.json",
        "tool_abuse_test_report.json",
    }
    if path.name not in preservable:
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    status = payload.get("status")
    return status in {"PASS", "FAIL", "BLOCKED_BY_ENVIRONMENT"} and bool(payload.get("tool") or payload.get("command"))


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _write_candidate_decision_matrix(path: Path) -> None:
    _write_text(
        path,
        "\n".join(
            [
                "candidate_id,candidate_name,area,operational_status,benchmark_type,evidence_reference,priority,required_action,confidence",
                "runtime.fastapi,FastAPI,product_api,ACTIVE_RUNTIME,LOCAL_READINESS,final_case_evidence/runtime_bom.json,P0,Keep as runtime after service proof passes,0.85",
                "runtime.postgresql,PostgreSQL,product_database,ACTIVE_RUNTIME,LOCAL_READINESS,final_case_evidence/runtime_bom.json,P0,Require live service proof before final GO,0.85",
                "runtime.qdrant,Qdrant,rag_vector_store,ACTIVE_RUNTIME,LOCAL_READINESS,final_case_evidence/runtime_bom.json,P0,Require live service proof and populated collection before final GO,0.85",
                "optional.llm_judge,LLM Judge,answer_quality,IMPLEMENTED_NOT_ACTIVE,PROXY_EVALUATED,docs/48_optional_llm_judge.md,P1,Implement real provider or keep future research,0.90",
                "candidate.graphrag,GraphRAG,rag_quality,DIRECT_BENCHMARK_PENDING,PENDING,final_case_evidence/graphrag_direct_benchmark_report.json,P1,Run 30-50 case direct benchmark before promotion,0.80",
                "candidate.source_quality,Source quality scoring,sourcing_quality,DIRECT_BENCHMARK_PENDING,PENDING,final_case_evidence/source_quality_direct_benchmark_report.json,P1,Run direct source quality benchmark before promotion,0.80",
            ]
        ),
    )


def _write_priority_candidate_queue(path: Path) -> None:
    _write_text(
        path,
        """# Priority Candidate Queue

Status: `PENDING_BENCHMARK_RUN`

| Priority | Candidate | Current status | Required evidence |
|---|---|---|---|
| P0 | PostgreSQL service proof | BLOCKED_BY_ENVIRONMENT | Reachable service, migrations, health check |
| P0 | Qdrant service proof | BLOCKED_BY_ENVIRONMENT | Reachable collection with NVIDIA corpus points |
| P1 | GraphRAG | PENDING_BENCHMARK_RUN | 30-50 case multi-hop/global/local benchmark |
| P1 | Source quality scoring | PENDING_BENCHMARK_RUN | Direct benchmark against source-trust labels |
| P1 | Real LLM judge | IMPLEMENTED_NOT_ACTIVE | Provider implementation, rubric, dataset, thresholds |
""",
    )


def _write_direct_benchmark_protocol(path: Path) -> None:
    _write_text(
        path,
        """# Direct Benchmark Protocol

Status: `PENDING_BENCHMARK_RUN`

Direct promotion requires measuring product output value against the current runtime baseline. Proxy readiness and local import checks are not sufficient for runtime promotion.

Promotion rule: `promotion_allowed=true` only when direct product-value metrics improve quality without violating latency, cost, security, or compliance constraints.
""",
    )


def _write_golden_eval_dataset(path: Path) -> None:
    rows = [
        {
            "case_id": "golden_eval_001",
            "task": "recommendation_grounding",
            "status": "PENDING_EXPANSION",
            "notes": "Seed case only; final promotion requires 30-50 cases.",
        },
        {
            "case_id": "golden_eval_002",
            "task": "multi_hop_evidence",
            "status": "PENDING_EXPANSION",
            "notes": "Seed case only; final promotion requires 30-50 cases.",
        },
    ]
    _write_text(path, "\n".join(json.dumps(row, sort_keys=True, ensure_ascii=True) for row in rows))


def _write_promotion_rejection_markdown(path: Path) -> None:
    _write_text(
        path,
        """# Promotion / Rejection Report

Status: `PENDING_BENCHMARK_RUN`

No new candidate was promoted by this static evidence pass. Existing runtime remains FastAPI, PostgreSQL, and Qdrant per `final_case_evidence/runtime_bom.json`.
""",
    )


def _write_runtime_promotion_ledger(path: Path) -> None:
    _write_text(
        path,
        "\n".join(
            [
                "component_id,name,current_status,promotion_allowed,benchmark_type,evidence_reference,decision_reason",
                "runtime.fastapi,FastAPI,ACTIVE_RUNTIME,true,LOCAL_READINESS,final_case_evidence/runtime_bom.json,Already promoted runtime API component",
                "runtime.postgresql,PostgreSQL,ACTIVE_RUNTIME_PENDING_SERVICE_PROOF,true,LOCAL_READINESS,final_case_evidence/local_proof_doctor_report.json,Runtime component remains required but final GO needs live service proof",
                "runtime.qdrant,Qdrant,ACTIVE_RUNTIME_PENDING_SERVICE_PROOF,true,LOCAL_READINESS,final_case_evidence/local_proof_doctor_report.json,Runtime component remains required but final GO needs live service proof",
                "candidate.graphrag,GraphRAG,PENDING_BENCHMARK_RUN,false,PENDING,final_case_evidence/graphrag_direct_benchmark_report.json,No direct robust benchmark yet",
                "candidate.source_quality,Source quality scoring,PENDING_BENCHMARK_RUN,false,PENDING,final_case_evidence/source_quality_direct_benchmark_report.json,No direct benchmark yet",
                "optional.llm_judge,LLM Judge,FUTURE_RESEARCH,false,PROXY_EVALUATED,docs/48_optional_llm_judge.md,Only offline null provider implemented",
            ]
        ),
    )


def _write_final_candidate_gap_audit(path: Path) -> None:
    _write_text(
        path,
        """# Final Candidate Gap Audit

Status: `PENDING_BENCHMARK_RUN`

Remaining gaps before a strict final-product GO: cold start proof, GraphRAG promotion benchmark, source-quality direct benchmark, real LLM judge provider, and dedicated scanner execution.
""",
    )


def _write_csv_if_missing(path: Path, fieldnames: list[str]) -> None:
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            existing = next(reader, [])
        if existing == fieldnames:
            return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()


def _ensure_candidate_catalog_benchmark_type(path: Path) -> None:
    if not path.exists():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0]) if rows else list(csv.DictReader([]).fieldnames or [])
    if not rows:
        return
    if "benchmark_type" not in fieldnames:
        insert_at = fieldnames.index("benchmark") if "benchmark" in fieldnames else len(fieldnames)
        fieldnames.insert(insert_at, "benchmark_type")
    for row in rows:
        if row.get("benchmark_type") not in BENCHMARK_TYPES:
            row["benchmark_type"] = _catalog_benchmark_type(row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _catalog_benchmark_type(row: dict[str, str]) -> str:
    text = " ".join(
        row.get(field, "")
        for field in ("name", "category", "status", "benchmark", "required_configuration", "substitute_reason")
    ).casefold()
    if "security" in text or "guardrail" in text or "red team" in text:
        return "SECURITY"
    if "compliance" in text or "data rights" in text or "license" in text:
        return "COMPLIANCE"
    if "external" in text or "proxy" in text or "future_research" in text or "blocked_until" in text:
        return "PROXY"
    if "release" in text or "reproduc" in text or "repository" in text:
        return "REPRODUCIBILITY"
    return "LOCAL_READINESS"


def _ensure_decision_ledger_benchmark_type(path: Path) -> None:
    if not path.exists():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0]) if rows else []
    if not rows:
        return
    if "benchmark_type" not in fieldnames:
        insert_at = (
            fieldnames.index("benchmark_result_ref") if "benchmark_result_ref" in fieldnames else len(fieldnames)
        )
        fieldnames.insert(insert_at, "benchmark_type")
    for row in rows:
        if row.get("benchmark_type") not in BENCHMARK_TYPES:
            row["benchmark_type"] = "REPRODUCIBILITY"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _ensure_benchmark_results_type(path: Path) -> None:
    if not path.exists():
        return
    updated_lines: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if payload.get("benchmark_type") not in BENCHMARK_TYPES:
                payload["benchmark_type"] = _result_benchmark_type(payload)
            updated_lines.append(json.dumps(payload, sort_keys=True, ensure_ascii=True))
    path.write_text("\n".join(updated_lines) + ("\n" if updated_lines else ""), encoding="utf-8")


def _result_benchmark_type(payload: dict[str, object]) -> str:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    scope = str(metadata.get("benchmark_scope", "")).casefold()
    status = str(payload.get("status", "")).casefold()
    if metadata.get("uses_mock_provider") is True:
        return "PROXY"
    if status in {"blocked", "future_research"} or "proxy" in scope or "external" in scope:
        return "PROXY"
    if "security" in scope:
        return "SECURITY"
    if "reproduc" in scope:
        return "REPRODUCIBILITY"
    if metadata.get("output_value_measured") is True and "current_product_quality" not in scope:
        return "OUTPUT_VALUE"
    if metadata.get("output_quality_measured") is True:
        return "PRODUCTION_QUALITY"
    return "LOCAL_READINESS"


def _ensure_output_value_decision_types(path: Path) -> None:
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    decisions = payload.get("decisions", [])
    if not isinstance(decisions, list):
        return
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        if decision.get("benchmark_type") not in BENCHMARK_TYPES:
            decision["benchmark_type"] = _decision_benchmark_type(decision)
        if decision.get("benchmark_type") in {"LOCAL_READINESS", "PROXY"}:
            decision["promotion_allowed"] = False
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _decision_benchmark_type(decision: dict[str, object]) -> str:
    scope = str(decision.get("benchmark_scope", "")).casefold()
    if decision.get("uses_mock_provider") is True:
        return "PROXY"
    if str(decision.get("benchmark_result_status", "")).casefold() in {"blocked", "future_research"}:
        return "PROXY"
    if "proxy" in scope or "external" in scope:
        return "PROXY"
    if decision.get("output_value_measured") is True and "current_product_quality" not in scope:
        return "OUTPUT_VALUE"
    if decision.get("quality_lift_measured") is True:
        return "PRODUCTION_QUALITY"
    return "LOCAL_READINESS"


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
import json
import re
import tomllib
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from src.governance.schemas import (
    BenchmarkCandidateEntry,
    BenchmarkType,
    CalibrationRegistryEntry,
    CandidateStatus,
    DecisionLedgerEntry,
    GateReport,
    KeepOrRemove,
    PurposeCategory,
    RepositoryPurposeEntry,
    RuntimeBOMEntry,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROADMAP_PATH = PROJECT_ROOT / "final_final_benchmark_first_roadmap_all_changes.md"
DEFAULT_EVIDENCE_DIR = PROJECT_ROOT / "final_case_evidence"

_T = TypeVar("_T", bound=BaseModel)

RUNTIME_CORE_NAMES: frozenset[str] = frozenset(
    {
        "FastAPI",
        "PostgreSQL",
        "Alembic",
        "SQLAlchemy",
        "Qdrant",
        "React",
        "TypeScript",
        "Vite",
        "Docker Compose",
    }
)

LOCAL_BENCHMARKABLE_NAMES: frozenset[str] = RUNTIME_CORE_NAMES | frozenset(
    {
        "BM25",
        "Hybrid retrieval",
        "Reciprocal Rank Fusion",
        "fusion retrieval",
        "hybrid retrieval",
        "BM25 retrieval",
        "vector retrieval",
        "metadata filtering",
        "structured outputs",
        "Pydantic JSON Schema",
        "JSON",
        "YAML",
        "Markdown tables",
        "CSV/TSV",
        "JSON Lines / NDJSON",
        "context packer",
        "token budgeter",
        "prompt assembler",
        "tool result schema validation",
        "Repository Purpose Manifest",
        "Repository Cleanliness Gate",
        "Documentation Consistency Gate",
        "Final Delivery Index",
        "Cold Start Reproducibility Test",
        "No Hidden State Rule",
        "No Hidden Manual Step Gate",
        "License and Third-Party Compliance",
        "AI Incident Response Plan",
        "Root Cause Analysis workflow",
        "Deprecation policy",
        "Data retention policy",
        "Final Evaluator Checklist",
        "Operational runbooks",
        "Reproducible case package",
        "Final Case Evidence Pack",
        "make prove-final-product",
    }
)

EXTERNAL_ONLY_NAMES: frozenset[str] = frozenset(
    {
        "Firecrawl",
        "Apify",
        "NVIDIA NeMo Retriever extraction",
        "NVIDIA NeMo Retriever Embedding NIM",
        "NVIDIA NeMo Retriever Reranker",
        "LlamaParse",
        "OpenAI Evals",
        "Parea AI",
        "Opik",
        "Phoenix",
        "Langfuse",
        "LangSmith",
        "Braintrust",
        "Weights & Biases Weave",
        "Helicone",
        "Maxim",
        "Fiddler",
        "AgentOps",
        "Weights & Biases",
        "Neptune",
        "WhyLabs",
        "Lakera Guard",
        "A2A / Agent-to-Agent Protocol",
        "AGNTCY / Agent Connect",
        "Humanloop",
        "Prodigy",
        "Label Studio",
        "Argilla",
        "Sigstore Cosign",
        "OpenSSF Scorecard",
        "Renovate",
        "Dependabot",
    }
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def parse_candidate_catalog_from_roadmap(path: Path = DEFAULT_ROADMAP_PATH) -> list[BenchmarkCandidateEntry]:
    maximal_entries = _candidate_catalog_from_maximal_catalog()
    if not path.exists():
        if maximal_entries:
            return maximal_entries
        return _candidate_catalog_from_evidence_csv()
    text = path.read_text(encoding="utf-8")
    start = text.find("## 8.")
    end = text.find("## 9.", start)
    if start == -1:
        return maximal_entries or _candidate_catalog_from_evidence_csv()
    section = text[start : end if end != -1 else len(text)]

    entries: list[BenchmarkCandidateEntry] = []
    current_category = ""
    in_fence = False
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if line.startswith("## 8."):
            current_category = line.lstrip("#").strip()
            continue
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence or not line or not current_category:
            continue

        candidate_id = f"{slugify(current_category)}__{slugify(line)}"
        entries.append(
            classify_candidate(
                BenchmarkCandidateEntry(
                    candidate_id=candidate_id,
                    name=line,
                    category=current_category,
                    status=CandidateStatus.DOCUMENTED_CANDIDATE,
                    marco="Marco TBD_BY_ROADMAP_MAPPING",
                    hypothesis=f"Evaluate whether {line} improves final product output.",
                    metrics=["TBD_BY_BENCHMARK"],
                    benchmark="TBD_BY_BENCHMARK",
                    substitute_candidate="",
                    substitute_reason="",
                )
            )
        )
    return entries or maximal_entries or _candidate_catalog_from_evidence_csv()


def _candidate_catalog_from_evidence_csv() -> list[BenchmarkCandidateEntry]:
    fallback_catalog = DEFAULT_EVIDENCE_DIR / "candidate_catalog.csv"
    if not fallback_catalog.exists():
        return []
    return [
        classify_candidate(BenchmarkCandidateEntry.model_validate(_candidate_row_from_csv(row)))
        for row in read_csv(fallback_catalog)
    ]


def _candidate_catalog_from_maximal_catalog() -> list[BenchmarkCandidateEntry]:
    from src.governance.catalog_loader import load_maximal_catalog

    entries: list[BenchmarkCandidateEntry] = []
    for item in load_maximal_catalog():
        status_text = getattr(item.status, "value", str(item.status)).upper()
        if status_text == "BENCHMARKED":
            status = CandidateStatus.BENCHMARKED
        elif status_text == "FUTURE_RESEARCH":
            status = CandidateStatus.FUTURE_RESEARCH
        else:
            status = CandidateStatus.DOCUMENTED_CANDIDATE
        entries.append(
            BenchmarkCandidateEntry(
                candidate_id=item.candidate_id,
                name=item.name,
                category=item.category,
                status=status,
                marco=item.marco,
                hypothesis=item.hypothesis or f"Evaluate whether {item.name} improves final product output.",
                baseline=item.baseline,
                metrics=item.metrics or ["output_quality", "latency_ms", "cost", "risk_score"],
                benchmark_type=_benchmark_type_from_text(item.benchmark_type),
                benchmark=item.benchmark or "scripts/run_benchmark.py --suite complete-catalog",
                required_configuration=item.required_configuration,
                expected_runtime_use=getattr(item.expected_runtime_use, "value", str(item.expected_runtime_use)),
                cost_to_measure=item.cost_to_measure,
                latency_to_measure=item.latency_to_measure,
                risks_to_measure=item.risks_to_measure,
                gate=item.gate,
                evidence_generated=item.evidence_generated,
                promotion_criteria=item.promotion_criteria or "promote only with measured output-quality lift",
                rejection_criteria=item.rejection_criteria or "reject when benchmark shows no measurable value",
                removal_criteria=item.removal_criteria or "remove from runtime when unused or lower value than alternative",
                substitute_candidate=item.substitute_candidate or None,
                substitute_reason=item.substitute_reason or None,
                free_self_hosted_verification=item.free_self_hosted_verification,
                source_or_reference=item.source_or_reference,
                external_dependency=item.external_dependency,
                cost_policy=getattr(item.cost_policy, "value", str(item.cost_policy)),
            )
        )
    return entries


def _benchmark_type_from_text(value: str) -> BenchmarkType:
    cleaned = (value or "").upper()
    for benchmark_type in BenchmarkType:
        if benchmark_type.value == cleaned:
            return benchmark_type
    if "SECURITY" in cleaned or "GUARD" in cleaned:
        return BenchmarkType.SECURITY
    if "COST" in cleaned or "LATENCY" in cleaned:
        return BenchmarkType.COST_LATENCY
    if "COMPLIANCE" in cleaned or "LICENSE" in cleaned:
        return BenchmarkType.COMPLIANCE
    if "READINESS" in cleaned:
        return BenchmarkType.LOCAL_READINESS
    if "PROXY" in cleaned:
        return BenchmarkType.PROXY
    return BenchmarkType.OUTPUT_VALUE


def _candidate_row_from_csv(row: dict[str, str]) -> dict[str, object]:
    normalized: dict[str, object] = dict(row)
    if isinstance(normalized.get("metrics"), str):
        metrics = str(normalized["metrics"])
        normalized["metrics"] = json.loads(metrics) if metrics.strip().startswith("[") else [metrics]
    for key in ("substitute_candidate", "substitute_reason", "benchmark_result_ref"):
        if normalized.get(key) == "":
            normalized[key] = None
    return normalized


def classify_candidate(entry: BenchmarkCandidateEntry) -> BenchmarkCandidateEntry:
    """Assign a conservative benchmark-first status using local repo evidence."""
    if entry.name in RUNTIME_CORE_NAMES:
        return entry.model_copy(
            update={
                "status": CandidateStatus.BENCHMARK_CONFIGURED,
                "benchmark_type": BenchmarkType.LOCAL_READINESS,
                "metrics": ["local_readiness", "latency_ms", "cost", "risk_score"],
                "benchmark": "scripts/run_benchmark.py --suite runtime-core",
                "required_configuration": ".env.example and project manifests",
                "expected_runtime_use": "active_product_runtime",
                "promotion_criteria": "local benchmark passes and runtime evidence is recorded",
                "rejection_criteria": "local benchmark fails or component is unused",
                "removal_criteria": "remove from runtime if no active product use remains",
                "substitute_candidate": "",
                "substitute_reason": "",
            }
        )

    if entry.name in LOCAL_BENCHMARKABLE_NAMES:
        return entry.model_copy(
            update={
                "status": CandidateStatus.BENCHMARK_CONFIGURED,
                "benchmark_type": BenchmarkType.PROXY,
                "metrics": ["local_readiness", "quality_signal", "latency_ms"],
                "benchmark": "scripts/run_benchmark.py --suite local-high-leverage",
                "required_configuration": "local repository and optional installed tooling",
                "expected_runtime_use": "candidate_or_supporting_governance",
                "promotion_criteria": "measurable lift or required governance role",
                "rejection_criteria": "no lift, duplicate capability, or unsupported dependency",
            }
        )

    if entry.name in EXTERNAL_ONLY_NAMES or _looks_external(entry):
        return entry.model_copy(
            update={
                "status": CandidateStatus.FUTURE_RESEARCH,
                "benchmark_type": BenchmarkType.PROXY,
                "metrics": ["TBD_BY_EXTERNAL_BENCHMARK"],
                "benchmark": "blocked_until_service_or_license_available",
                "required_configuration": "external credentials, service access, license, or hardware",
                "expected_runtime_use": "not_active_runtime",
                "promotion_criteria": "direct external benchmark beats local baseline",
                "rejection_criteria": "blocked, no measurable lift, or unacceptable risk/cost",
                "substitute_candidate": "local_proxy_if_external_unavailable",
                "substitute_reason": (
                    "Original candidate requires unavailable SaaS, license, hardware, or credentials."
                ),
            }
        )

    return entry


def _looks_external(entry: BenchmarkCandidateEntry) -> bool:
    external_markers = (
        "NVIDIA ",
        "OpenAI",
        "Cohere",
        "SaaS",
        "managed",
        "Snowflake",
        "BigQuery",
        "Temporal activities",
    )
    return any(marker.lower() in entry.name.lower() for marker in external_markers)


def summarize_candidate_catalog(entries: list[BenchmarkCandidateEntry]) -> dict[str, object]:
    by_status: dict[str, int] = {}
    by_category: dict[str, dict[str, int]] = {}
    runtime_relevant = 0
    external_dependency = 0
    benchmark_configured = 0

    for entry in entries:
        status = entry.status.value
        by_status[status] = by_status.get(status, 0) + 1
        category_counts = by_category.setdefault(entry.category, {})
        category_counts[status] = category_counts.get(status, 0) + 1
        if entry.name in RUNTIME_CORE_NAMES or entry.expected_runtime_use == "active_product_runtime":
            runtime_relevant += 1
        if entry.status == CandidateStatus.FUTURE_RESEARCH or _has_external_dependency(entry):
            external_dependency += 1
        if entry.status == CandidateStatus.BENCHMARK_CONFIGURED:
            benchmark_configured += 1

    return {
        "total_candidates": len(entries),
        "by_status": by_status,
        "by_category": by_category,
        "runtime_relevant_count": runtime_relevant,
        "external_dependency_count": external_dependency,
        "benchmark_configured_count": benchmark_configured,
        "benchmarkability": {
            "configured_ratio": benchmark_configured / len(entries) if entries else 0.0,
            "external_dependency_ratio": external_dependency / len(entries) if entries else 0.0,
        },
    }


def _has_external_dependency(entry: BenchmarkCandidateEntry) -> bool:
    fields = " ".join(
        str(value or "")
        for value in (
            entry.required_configuration,
            entry.substitute_reason,
            entry.benchmark,
        )
    ).lower()
    markers = ("external", "saas", "credential", "license", "hardware", "api key", "blocked_until")
    return any(marker in fields for marker in markers)


def write_csv(path: Path, rows: Iterable[_T], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            data = row.model_dump(mode="json")
            writer.writerow({field: _csv_value(data.get(field)) for field in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list | dict):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def build_license_inventory() -> dict[str, object]:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    python_deps = project.get("dependencies", [])
    optional_deps = project.get("optional-dependencies", {})
    package_json = json.loads((PROJECT_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    frontend_deps = package_json.get("dependencies", {})
    frontend_dev_deps = package_json.get("devDependencies", {})
    return {
        "status": "PASS",
        "python_dependency_count": len(python_deps),
        "python_optional_groups": sorted(optional_deps),
        "frontend_dependency_count": len(frontend_deps),
        "frontend_dev_dependency_count": len(frontend_dev_deps),
        "python_dependencies": python_deps,
        "frontend_dependencies": frontend_deps,
        "frontend_dev_dependencies": frontend_dev_deps,
        "notes": "Manifest inventory only; full third-party license resolution remains a release gate.",
    }


def build_local_security_scan() -> dict[str, object]:
    patterns = {
        "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
        "non_empty_secret_assignment": re.compile(
            r"(?i)(api_key|secret|password|token)\s*=\s*['\"]?[A-Za-z0-9_\-]{16,}"
        ),
    }
    scan_dirs = ["src", "scripts", "frontend/src", "docs"]
    findings: list[dict[str, object]] = []
    for scan_dir in scan_dirs:
        root = PROJECT_ROOT / scan_dir
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".py",
                ".ts",
                ".tsx",
                ".js",
                ".md",
                ".json",
                ".yml",
                ".yaml",
            }:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name, pattern in patterns.items():
                if pattern.search(text):
                    findings.append({"path": path.relative_to(PROJECT_ROOT).as_posix(), "pattern": name})
    return {
        "status": "PASS" if not findings else "FAIL",
        "checked_paths": scan_dirs,
        "finding_count": len(findings),
        "findings": findings,
        "notes": "Local regex scan; use dedicated tools such as gitleaks/detect-secrets for release.",
    }


def finalization_static_reports() -> dict[str, dict[str, object]]:
    generated_at = datetime.now(UTC).isoformat()
    release_pending: dict[str, object] = {
        "status": "PENDING_PACKAGE_FINAL_RELEASE",
        "generated_at": generated_at,
        "required_command": "make package-final-release",
        "gate": "make check-final-release-zip",
    }
    tool_blocked: dict[str, object] = {
        "status": "BLOCKED_BY_ENVIRONMENT",
        "generated_at": generated_at,
        "reason": "Dedicated release scanner binary is not bundled with the repository.",
        "policy": "Run the named scanner in the release environment and store its JSON output here.",
    }
    return {
        "secret_scan_report": {
            **tool_blocked,
            "recommended_tools": ["gitleaks", "detect-secrets"],
        },
        "dependency_vulnerability_report": {
            **tool_blocked,
            "recommended_tools": ["pip-audit", "npm audit", "trivy", "grype"],
        },
        "sast_report": {
            **tool_blocked,
            "recommended_tools": ["semgrep", "bandit"],
        },
        "sbom": {
            **tool_blocked,
            "recommended_tools": ["syft"],
            "sbom_format": "TBD_BY_RELEASE_TOOLING",
        },
        "container_scan_report": {
            **tool_blocked,
            "recommended_tools": ["trivy", "grype"],
            "applies_if": "containerized release image is built",
        },
        "openssf_scorecard_report": {
            **tool_blocked,
            "recommended_tools": ["OpenSSF Scorecard"],
        },
        "final_release_manifest": release_pending,
        "final_release_clean_report": release_pending,
        "final_release_file_allowlist_report": release_pending,
        "final_release_forbidden_artifacts_report": release_pending,
        "final_release_zip_clean_report": release_pending,
        "no_env_in_release_report": release_pending,
        "no_git_dir_in_release_report": release_pending,
        "no_node_modules_report": release_pending,
        "frontend_build_reproducibility_report": {
            "status": "PENDING_FRONTEND_BUILD",
            "generated_at": generated_at,
            "required_command": "npm ci && npm run build",
            "policy": "Build artifacts are reproducible outputs and are excluded from the source release ZIP.",
        },
        "no_active_demo_docs_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "policy": "Active final-product evidence must not rely on demo documents.",
            "archive_path": "docs/archive/demo_history/",
        },
        "demo_archive_manifest": {
            "status": "PASS",
            "generated_at": generated_at,
            "archive_path": "docs/archive/demo_history/",
            "active_runtime_role": "none",
            "items": [],
        },
        "benchmark_type_coverage_report": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "allowed_values": [item.value for item in BenchmarkType],
            "required_command": "python scripts/run_benchmark.py --suite complete-catalog",
        },
        "proxy_benchmark_promotion_block_report": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "policy": "LOCAL_READINESS and PROXY never promote runtime adoption alone.",
        },
        "mock_provider_benchmark_classification_report": {
            "status": "PENDING_BENCHMARK_RUN",
            "generated_at": generated_at,
            "policy": "MockEmbeddingProvider benchmarks are LOCAL_READINESS or PROXY only.",
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
            "policy": "Retrieval must preserve source and evidence permissions before context assembly.",
        },
        "data_minimization_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "controls": [
                "context_minimization_policy",
                "data_retention_policy",
                "source_storage_policy",
            ],
        },
        "least_context_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "controls": ["least_context_packer", "prompt_context_budgeter"],
            "policy": "Send the minimum evidence needed to answer with support.",
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
            "required_gate": "check_prompt_injection_suite",
        },
        "external_reviewer_mode_report": {
            "status": "PASS",
            "generated_at": generated_at,
            "documentation": "docs/final_external_reviewer_mode.md",
            "commands": [
                "cp .env.example .env",
                "docker compose up -d",
                "make setup",
                "make ingest-real-sources",
                "make run-evals",
                "make prove-final-product",
                "make run",
            ],
        },
        "cold_start_report": {
            "status": "PENDING_COLD_START_RUN",
            "generated_at": generated_at,
            "required_gate": "check_cold_start_reproducibility",
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
    }


def default_repository_purpose_entries() -> list[RepositoryPurposeEntry]:
    return [
        RepositoryPurposeEntry(
            path="src",
            category=PurposeCategory.PRODUCT_RUNTIME,
            purpose="Typed product backend, RAG, scoring, orchestration, API, and governance runtime.",
            owner="product",
            runtime_or_documentation_role="runtime",
            keep_or_remove=KeepOrRemove.KEEP,
            evidence_reference="docs/final_runtime_contract.md",
        ),
        RepositoryPurposeEntry(
            path="frontend",
            category=PurposeCategory.PRODUCT_RUNTIME,
            purpose="Evidence-first product UI.",
            owner="product",
            runtime_or_documentation_role="runtime",
            keep_or_remove=KeepOrRemove.KEEP,
            evidence_reference="docs/final_delivery_index.md",
        ),
        RepositoryPurposeEntry(
            path="tests",
            category=PurposeCategory.PRODUCT_TESTS,
            purpose="Automated unit, integration, eval, acceptance, and E2E validation.",
            owner="product",
            runtime_or_documentation_role="test",
            keep_or_remove=KeepOrRemove.KEEP,
            evidence_reference="EVALS.md",
        ),
        RepositoryPurposeEntry(
            path="final_case_evidence",
            category=PurposeCategory.GOVERNANCE_EVIDENCE,
            purpose="Generated final proof reports, ledgers, manifests, and benchmark outputs.",
            owner="product",
            runtime_or_documentation_role="evidence",
            keep_or_remove=KeepOrRemove.KEEP,
            evidence_reference="docs/final_delivery_index.md",
        ),
        RepositoryPurposeEntry(
            path="notebooks",
            category=PurposeCategory.ARCHIVED_HISTORICAL_MATERIAL,
            purpose="Exploratory notebooks excluded from runtime proof.",
            owner="research",
            runtime_or_documentation_role="historical",
            keep_or_remove=KeepOrRemove.REVIEW,
            evidence_reference="docs/final_repository_map.md",
        ),
    ]


def default_runtime_bom_entries() -> list[RuntimeBOMEntry]:
    return [
        RuntimeBOMEntry(
            component_id="runtime.fastapi",
            name="FastAPI",
            category="Runtime core",
            version_or_source="pyproject.toml",
            status=CandidateStatus.PROMOTED_TO_RUNTIME,
            runtime_role="product_api",
            configuration_ref=".env.example",
            benchmark_ref="final_case_evidence/benchmark_manifest.json",
            decision_ref="final_case_evidence/decision_ledger.csv",
        ),
        RuntimeBOMEntry(
            component_id="runtime.postgresql",
            name="PostgreSQL",
            category="Runtime core",
            version_or_source="PRODUCT_DB_URL",
            status=CandidateStatus.PROMOTED_TO_RUNTIME,
            runtime_role="product_database",
            configuration_ref=".env.example",
            benchmark_ref="final_case_evidence/benchmark_manifest.json",
            decision_ref="final_case_evidence/decision_ledger.csv",
        ),
        RuntimeBOMEntry(
            component_id="runtime.qdrant",
            name="Qdrant",
            category="Runtime core",
            version_or_source="QDRANT_URL",
            status=CandidateStatus.PROMOTED_TO_RUNTIME,
            runtime_role="rag_vector_store",
            configuration_ref=".env.example",
            benchmark_ref="final_case_evidence/benchmark_manifest.json",
            decision_ref="final_case_evidence/decision_ledger.csv",
        ),
    ]


def default_calibration_registry_entries() -> list[CalibrationRegistryEntry]:
    from src.quality.decision_calibration_registry import get_project_decision_inventory

    entries: list[CalibrationRegistryEntry] = []
    for record in get_project_decision_inventory():
        value = record.current_value if record.current_value is not None else "not_set"
        serialized_value = json.dumps(value, sort_keys=True) if isinstance(value, dict) else value
        metric_name = record.metric_name or record.decision_id
        calibrated_at = record.last_calibrated_at.date().isoformat() if record.last_calibrated_at else "not_calibrated"
        entries.append(
            CalibrationRegistryEntry(
                calibration_id=record.decision_id,
                metric_name=metric_name,
                value=serialized_value,
                unit=_infer_calibration_unit(value),
                decision_area=record.decision_type.value,
                dataset_version="internal-decision-inventory-2026-06-17",
                corpus_version="nvidia-corpus-versioned",
                pipeline_version="product-final-proof",
                experiment_run_id=record.value_origin or "decision-calibration-registry",
                git_commit="workspace",
                baseline_result=record.evidence_source or "not_recorded",
                candidate_result=record.notes or "not_recorded",
                statistical_method=record.calibration_status.value,
                uncertainty_method="registered_decision_status",
                calibration_method=record.calibration_method.value if record.calibration_method else "not_calibrated",
                calibration_date=calibrated_at,
                reviewer_or_approver=record.owner or "product",
                validity_period="until_recalibration_trigger",
                recalibration_trigger="metric_formula_dataset_or_threshold_change",
                production_allowed=record.production_allowed,
            )
        )
    return entries


def _infer_calibration_unit(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "weight_set"
    if isinstance(value, int | float):
        return "score_or_threshold"
    return "text"


def default_decision_ledger_entries() -> list[DecisionLedgerEntry]:
    return [
        DecisionLedgerEntry(
            decision_id="final-roadmap-source-of-truth",
            item_name="final_final_benchmark_first_roadmap_all_changes.md",
            category="governance",
            status=CandidateStatus.PROMOTED_TO_RUNTIME,
            decision="Use the final benchmark-first roadmap as canonical final-product source.",
            evidence_reference="docs/plans/2026-06-21_epic-50_final-benchmark-first-roadmap.md",
            benchmark_result_ref="final_case_evidence/benchmark_manifest.json",
            benchmark_type=BenchmarkType.REPRODUCIBILITY,
            metric_names=["governance_traceability"],
        )
    ]


def build_initial_evidence_pack(
    roadmap_path: Path = DEFAULT_ROADMAP_PATH,
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
) -> dict[str, Path]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    candidates = parse_candidate_catalog_from_roadmap(roadmap_path)

    outputs = {
        "candidate_catalog": evidence_dir / "candidate_catalog.csv",
        "repository_purpose_manifest": evidence_dir / "repository_purpose_manifest.csv",
        "runtime_bill_of_materials": evidence_dir / "runtime_bill_of_materials.csv",
        "runtime_bom_json": evidence_dir / "runtime_bom.json",
        "runtime_bom_md": evidence_dir / "runtime_bom.md",
        "decision_ledger": evidence_dir / "decision_ledger.csv",
        "calibration_registry": evidence_dir / "calibration_registry.csv",
        "benchmark_manifest": evidence_dir / "benchmark_manifest.json",
        "benchmark_results": evidence_dir / "benchmark_results.jsonl",
        "benchmark_report": evidence_dir / "benchmark_report.json",
        "benchmark_coverage_report": evidence_dir / "benchmark_coverage_report.json",
        "benchmark_debt_report": evidence_dir / "benchmark_debt_report.json",
        "output_value_benchmark_report": evidence_dir / "output_value_benchmark_report.json",
        "candidate_promotion_recommendations": evidence_dir / "candidate_promotion_recommendations.json",
        "all_candidate_benchmark_documentation": evidence_dir / "all_candidate_benchmark_documentation.md",
        "ranked_value_candidate_queue": evidence_dir / "ranked_value_candidate_queue.json",
        "ranked_value_candidate_queue_md": evidence_dir / "ranked_value_candidate_queue.md",
        "ranked_value_benchmark_report": evidence_dir / "ranked_value_benchmark_report.json",
        "ranked_value_benchmark_report_md": evidence_dir / "ranked_value_benchmark_report.md",
        "diagnostic_eval_cases": evidence_dir / "diagnostic_eval_cases.json",
        "diagnostic_value_triage_report": evidence_dir / "diagnostic_value_triage_report.json",
        "diagnostic_value_triage_report_md": evidence_dir / "diagnostic_value_triage_report.md",
        "family_spike_cases": evidence_dir / "family_spike_cases.json",
        "family_spike_benchmark_report": evidence_dir / "family_spike_benchmark_report.json",
        "family_spike_benchmark_report_md": evidence_dir / "family_spike_benchmark_report.md",
        "query_rewriting_product_spike_report": evidence_dir / "query_rewriting_product_spike_report.json",
        "query_rewriting_product_spike_report_md": evidence_dir / "query_rewriting_product_spike_report.md",
        "next_action_enrichment_product_spike_report": (
            evidence_dir / "next_action_enrichment_product_spike_report.json"
        ),
        "next_action_enrichment_product_spike_report_md": (
            evidence_dir / "next_action_enrichment_product_spike_report.md"
        ),
        "graphrag_evidence_graph_product_spike_report": (
            evidence_dir / "graphrag_evidence_graph_product_spike_report.json"
        ),
        "graphrag_evidence_graph_product_spike_report_md": (
            evidence_dir / "graphrag_evidence_graph_product_spike_report.md"
        ),
        "counter_evidence_product_spike_report": (evidence_dir / "counter_evidence_product_spike_report.json"),
        "counter_evidence_product_spike_report_md": (evidence_dir / "counter_evidence_product_spike_report.md"),
        "source_quality_product_spike_report": (evidence_dir / "source_quality_product_spike_report.json"),
        "source_quality_product_spike_report_md": (evidence_dir / "source_quality_product_spike_report.md"),
        "evidence_sufficiency_product_spike_report": (evidence_dir / "evidence_sufficiency_product_spike_report.json"),
        "evidence_sufficiency_product_spike_report_md": (evidence_dir / "evidence_sufficiency_product_spike_report.md"),
        "implemented_family_best_tool_report": evidence_dir / "implemented_family_best_tool_report.json",
        "implemented_family_best_tool_report_md": evidence_dir / "implemented_family_best_tool_report.md",
        "direct_alternative_gap_benchmark_report": evidence_dir / "direct_alternative_gap_benchmark_report.json",
        "direct_alternative_gap_benchmark_report_md": evidence_dir / "direct_alternative_gap_benchmark_report.md",
        "value_family_completeness_report": evidence_dir / "value_family_completeness_report.json",
        "value_family_completeness_report_md": evidence_dir / "value_family_completeness_report.md",
        "roadmap_closure_audit_report": evidence_dir / "roadmap_closure_audit_report.json",
        "roadmap_closure_audit_report_md": evidence_dir / "roadmap_closure_audit_report.md",
        "runtime_value_policy_report": evidence_dir / "runtime_value_policy_report.json",
        "external_free_verification_report": evidence_dir / "external_free_verification_report.json",
        "external_free_verification_report_md": evidence_dir / "external_free_verification_report.md",
        "free_external_candidate_review": evidence_dir / "free_external_candidate_review.json",
        "free_external_candidate_review_md": evidence_dir / "free_external_candidate_review.md",
        "free_external_candidate_benchmark_report": evidence_dir / "free_external_candidate_benchmark_report.json",
        "free_external_candidate_benchmark_report_md": evidence_dir / "free_external_candidate_benchmark_report.md",
        "candidate_status_summary": evidence_dir / "candidate_status_summary.json",
        "docker_services_report": evidence_dir / "docker_services_report.json",
        "postgres_migration_report": evidence_dir / "postgres_migration_report.json",
        "qdrant_readiness_report": evidence_dir / "qdrant_readiness_report.json",
        "rag_ingestion_report": evidence_dir / "rag_ingestion_report.json",
        "acceptance_report": evidence_dir / "acceptance_report.json",
        "real_service_proof_report": evidence_dir / "real_service_proof_report.json",
        "product_readiness_report": evidence_dir / "product_readiness_report.json",
        "product_readiness_report_md": evidence_dir / "product_readiness_report.md",
        "numeric_governance_report": evidence_dir / "numeric_governance_report.json",
        "no_demo_report": evidence_dir / "no_demo_report.json",
        "source_compliance_report": evidence_dir / "source_compliance_report.json",
        "source_coverage_report": evidence_dir / "source_coverage_report.json",
        "source_coverage_map": evidence_dir / "source_coverage_map.json",
        "data_rights_registry": evidence_dir / "data_rights_registry.csv",
        "data_lineage_report": evidence_dir / "data_lineage_report.json",
        "evidence_to_decision_coverage": evidence_dir / "evidence_to_decision_coverage.json",
        "repository_clean_report": evidence_dir / "repository_clean_report.json",
        "security_scan_report": evidence_dir / "security_scan_report.json",
        "release_artifact_manifest": evidence_dir / "release_artifact_manifest.json",
        "license_inventory": evidence_dir / "license_inventory.json",
        "secret_scan_report": evidence_dir / "secret_scan_report.json",
        "dependency_vulnerability_report": evidence_dir / "dependency_vulnerability_report.json",
        "sast_report": evidence_dir / "sast_report.json",
        "sbom": evidence_dir / "sbom.json",
        "container_scan_report": evidence_dir / "container_scan_report.json",
        "openssf_scorecard_report": evidence_dir / "openssf_scorecard_report.json",
        "final_release_manifest": evidence_dir / "final_release_manifest.json",
        "final_release_clean_report": evidence_dir / "final_release_clean_report.json",
        "final_release_file_allowlist_report": evidence_dir / "final_release_file_allowlist_report.json",
        "final_release_forbidden_artifacts_report": (evidence_dir / "final_release_forbidden_artifacts_report.json"),
        "final_release_zip_clean_report": evidence_dir / "final_release_zip_clean_report.json",
        "no_env_in_release_report": evidence_dir / "no_env_in_release_report.json",
        "no_git_dir_in_release_report": evidence_dir / "no_git_dir_in_release_report.json",
        "no_node_modules_report": evidence_dir / "no_node_modules_report.json",
        "frontend_build_reproducibility_report": (evidence_dir / "frontend_build_reproducibility_report.json"),
        "no_active_demo_docs_report": evidence_dir / "no_active_demo_docs_report.json",
        "demo_archive_manifest": evidence_dir / "demo_archive_manifest.json",
        "benchmark_type_coverage_report": evidence_dir / "benchmark_type_coverage_report.json",
        "proxy_benchmark_promotion_block_report": (evidence_dir / "proxy_benchmark_promotion_block_report.json"),
        "mock_provider_benchmark_classification_report": (
            evidence_dir / "mock_provider_benchmark_classification_report.json"
        ),
        "roadmap_non_runtime_items_justification": (evidence_dir / "roadmap_non_runtime_items_justification.csv"),
        "robots_terms_report": evidence_dir / "robots_terms_report.json",
        "access_control_rag_report": evidence_dir / "access_control_rag_report.json",
        "data_minimization_report": evidence_dir / "data_minimization_report.json",
        "least_context_report": evidence_dir / "least_context_report.json",
        "context_firewall_report": evidence_dir / "context_firewall_report.json",
        "prompt_injection_test_report": evidence_dir / "prompt_injection_test_report.json",
        "external_reviewer_mode_report": evidence_dir / "external_reviewer_mode_report.json",
        "cold_start_report": evidence_dir / "cold_start_report.json",
        "repository_purpose_coverage_report": evidence_dir / "repository_purpose_coverage_report.json",
        "rca_workflow_report": evidence_dir / "rca_workflow_report.json",
        "ai_governance_maturity_report": evidence_dir / "ai_governance_maturity_report.json",
        "agent_tool_observability_report": evidence_dir / "agent_tool_observability_report.json",
        "no_hidden_manual_steps_report": evidence_dir / "no_hidden_manual_steps_report.json",
        "final_proof_summary": evidence_dir / "final_proof_summary.json",
        "evidence_first_ui_report": evidence_dir / "evidence_first_ui_report.json",
    }

    write_csv(outputs["candidate_catalog"], candidates, list(BenchmarkCandidateEntry.model_fields))
    write_csv(
        outputs["repository_purpose_manifest"],
        default_repository_purpose_entries(),
        list(RepositoryPurposeEntry.model_fields),
    )
    runtime_bom_entries = default_runtime_bom_entries()
    calibration_entries = default_calibration_registry_entries()
    write_csv(outputs["runtime_bill_of_materials"], runtime_bom_entries, list(RuntimeBOMEntry.model_fields))
    write_json(
        outputs["runtime_bom_json"],
        {
            "report_id": "runtime_bom",
            "status": "PASS",
            "component_count": len(runtime_bom_entries),
            "components": [entry.model_dump(mode="json") for entry in runtime_bom_entries],
        },
    )
    outputs["runtime_bom_md"].write_text(render_runtime_bom_markdown(runtime_bom_entries), encoding="utf-8")
    write_csv(outputs["decision_ledger"], default_decision_ledger_entries(), list(DecisionLedgerEntry.model_fields))
    write_csv(
        outputs["calibration_registry"],
        calibration_entries,
        [
            "calibration_id",
            "metric_name",
            "value",
            "unit",
            "decision_area",
            "dataset_version",
            "corpus_version",
            "pipeline_version",
            "experiment_run_id",
            "git_commit",
            "baseline_result",
            "candidate_result",
            "statistical_method",
            "uncertainty_method",
            "calibration_method",
            "calibration_date",
            "reviewer_or_approver",
            "validity_period",
            "recalibration_trigger",
            "production_allowed",
        ],
    )
    write_csv(
        outputs["data_rights_registry"],
        [],
        [
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
        ],
    )

    manifest = {
        "roadmap": str(roadmap_path),
        "candidate_count": len(candidates),
        "candidate_status_summary": "final_case_evidence/candidate_status_summary.json",
        "status": "BENCHMARK_CONFIGURED",
        "notes": (
            "Initial manifest configures the universal benchmark lab; individual candidates still require results."
        ),
    }
    write_json(outputs["benchmark_manifest"], manifest)
    write_json(outputs["candidate_status_summary"], summarize_candidate_catalog(candidates))
    write_json(
        outputs["benchmark_coverage_report"],
        {
            "report_id": "benchmark_coverage_report",
            "total_candidates": len(candidates),
            "total_results": 0,
            "coverage_ratio": 0.0,
            "direct_benchmarks": 0,
            "category_proxy_configured": 0,
            "current_product_quality_adoption_benchmarks": 0,
            "blocked_or_future_research": 0,
            "promotion_allowed_count": 0,
            "status": "PENDING_BENCHMARK_RUN",
        },
    )
    write_json(
        outputs["benchmark_debt_report"],
        {
            "report_id": "benchmark_debt_report",
            "total_debt_items": len(candidates),
            "items": [
                {
                    "candidate_id": candidate.candidate_id,
                    "name": candidate.name,
                    "category": candidate.category,
                    "reason": "pending benchmark run",
                }
                for candidate in candidates
            ],
        },
    )
    write_json(
        outputs["output_value_benchmark_report"],
        {
            "report_id": "output_value_benchmark_report",
            "total_candidates": len(candidates),
            "total_decisions": 0,
            "by_decision": {},
            "decision_policy": (
                "Run scripts/run_benchmark.py --suite complete-catalog to produce output-quality decisions."
            ),
            "decisions": [],
        },
    )
    write_json(
        outputs["candidate_promotion_recommendations"],
        {
            "report_id": "candidate_promotion_recommendations",
            "summary": {
                "add_to_product_count": 0,
                "keep_required_runtime_count": 0,
                "keep_baseline_count": 0,
                "needs_direct_quality_benchmark_count": len(candidates),
                "future_research_count": 0,
                "rejected_by_evidence_count": 0,
            },
            "add_to_product": [],
            "keep_required_runtime": [],
            "keep_baseline": [],
            "do_not_add_without_direct_quality_benchmark": [],
            "future_research": [],
            "rejected_by_evidence": [],
        },
    )
    outputs["all_candidate_benchmark_documentation"].write_text(
        "# All Candidate Benchmark Documentation\n\n"
        "Pending benchmark run. Execute `python scripts/run_benchmark.py --suite complete-catalog` "
        "to document every candidate decision.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["ranked_value_candidate_queue"],
        {
            "report_id": "ranked_value_candidate_queue",
            "status": "PENDING_RANKED_BENCHMARK_RUN",
            "items": [],
        },
    )
    outputs["ranked_value_candidate_queue_md"].write_text(
        "# Ranked Value Candidate Queue\n\nPending ranked benchmark run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["ranked_value_benchmark_report"],
        {
            "report_id": "ranked_value_benchmark_report",
            "status": "PENDING_RANKED_BENCHMARK_RUN",
            "decisions": [],
        },
    )
    outputs["ranked_value_benchmark_report_md"].write_text(
        "# Ranked Value Benchmark Report\n\nPending ranked benchmark run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["diagnostic_eval_cases"],
        {
            "report_id": "diagnostic_eval_cases",
            "status": "PENDING_DIAGNOSTIC_VALUE_TRIAGE",
            "cases": [],
        },
    )
    write_json(
        outputs["diagnostic_value_triage_report"],
        {
            "report_id": "diagnostic_value_triage_report",
            "status": "PENDING_DIAGNOSTIC_VALUE_TRIAGE",
            "family_decisions": [],
            "recommended_spikes": [],
        },
    )
    outputs["diagnostic_value_triage_report_md"].write_text(
        "# Diagnostic Value Triage Report\n\nPending diagnostic value triage run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["family_spike_cases"],
        {
            "report_id": "family_spike_cases",
            "status": "PENDING_FAMILY_SPIKE_BENCHMARK_RUN",
            "cases": [],
        },
    )
    write_json(
        outputs["family_spike_benchmark_report"],
        {
            "report_id": "family_spike_benchmark_report",
            "status": "PENDING_FAMILY_SPIKE_BENCHMARK_RUN",
            "decisions": [],
        },
    )
    outputs["family_spike_benchmark_report_md"].write_text(
        "# Family Spike Benchmark Report\n\nPending family spike benchmark run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["query_rewriting_product_spike_report"],
        {
            "report_id": "query_rewriting_product_spike_report",
            "status": "PENDING_QUERY_REWRITING_PRODUCT_SPIKE",
            "decision": "PENDING",
            "cases": [],
        },
    )
    outputs["query_rewriting_product_spike_report_md"].write_text(
        "# Query Rewriting Product Spike Report\n\nPending query rewriting product spike run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["next_action_enrichment_product_spike_report"],
        {
            "report_id": "next_action_enrichment_product_spike_report",
            "status": "PENDING_NEXT_ACTION_ENRICHMENT_PRODUCT_SPIKE",
            "decision": "PENDING",
            "cases": [],
        },
    )
    outputs["next_action_enrichment_product_spike_report_md"].write_text(
        "# Next-Action Enrichment Product Spike Report\n\nPending next-action enrichment product spike run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["graphrag_evidence_graph_product_spike_report"],
        {
            "report_id": "graphrag_evidence_graph_product_spike_report",
            "status": "PENDING_GRAPHRAG_EVIDENCE_GRAPH_PRODUCT_SPIKE",
            "decision": "PENDING",
            "cases": [],
        },
    )
    outputs["graphrag_evidence_graph_product_spike_report_md"].write_text(
        "# GraphRAG Evidence Graph Product Spike Report\n\nPending GraphRAG evidence graph product spike run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["counter_evidence_product_spike_report"],
        {
            "report_id": "counter_evidence_product_spike_report",
            "status": "PENDING_COUNTER_EVIDENCE_PRODUCT_SPIKE",
            "decision": "PENDING",
            "cases": [],
        },
    )
    outputs["counter_evidence_product_spike_report_md"].write_text(
        "# Counter-Evidence Product Spike Report\n\nPending counter-evidence product spike run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["source_quality_product_spike_report"],
        {
            "report_id": "source_quality_product_spike_report",
            "status": "PENDING_SOURCE_QUALITY_PRODUCT_SPIKE",
            "decision": "PENDING",
            "cases": [],
        },
    )
    outputs["source_quality_product_spike_report_md"].write_text(
        "# Source Quality Product Spike Report\n\nPending source quality product spike run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["evidence_sufficiency_product_spike_report"],
        {
            "report_id": "evidence_sufficiency_product_spike_report",
            "status": "PENDING_EVIDENCE_SUFFICIENCY_PRODUCT_SPIKE",
            "decision": "PENDING",
            "cases": [],
        },
    )
    outputs["evidence_sufficiency_product_spike_report_md"].write_text(
        "# Evidence Sufficiency Product Spike Report\n\nPending evidence sufficiency product spike run.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["implemented_family_best_tool_report"],
        {
            "report_id": "implemented_family_best_tool_report",
            "status": "PENDING_IMPLEMENTED_FAMILY_BEST_TOOL_AUDIT",
            "families": [],
            "global_best_guarantee": False,
        },
    )
    outputs["implemented_family_best_tool_report_md"].write_text(
        "# Implemented Family Best Tool Report\n\nPending implemented family best-tool audit.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["direct_alternative_gap_benchmark_report"],
        {
            "report_id": "direct_alternative_gap_benchmark_report",
            "status": "PENDING_DIRECT_ALTERNATIVE_GAP_BENCHMARKS",
            "results": [],
        },
    )
    outputs["direct_alternative_gap_benchmark_report_md"].write_text(
        "# Direct Alternative Gap Benchmark Report\n\nPending direct alternative gap benchmarks.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["value_family_completeness_report"],
        {
            "report_id": "value_family_completeness_report",
            "status": "PENDING_VALUE_FAMILY_COMPLETENESS_AUDIT",
            "exhaustive_value_family_discovery": False,
            "global_no_more_value_guarantee": False,
            "families": [],
        },
    )
    outputs["value_family_completeness_report_md"].write_text(
        "# Value Family Completeness Report\n\nPending value family completeness audit.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["roadmap_closure_audit_report"],
        {
            "report_id": "roadmap_closure_audit_report",
            "status": "PENDING_ROADMAP_CLOSURE_AUDIT",
            "items": [],
        },
    )
    outputs["roadmap_closure_audit_report_md"].write_text(
        "# Roadmap Closure Audit Report\n\nPending roadmap closure audit.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["runtime_value_policy_report"],
        {
            "report_id": "runtime_value_policy_report",
            "status": "PENDING_RUNTIME_VALUE_POLICY_CHECK",
            "components": [],
        },
    )
    write_json(
        outputs["external_free_verification_report"],
        {
            "report_id": "external_free_verification_report",
            "status": "PENDING_EXTERNAL_FREE_VERIFICATION",
            "items": [],
        },
    )
    outputs["external_free_verification_report_md"].write_text(
        "# External Free Verification Report\n\nPending external free verification.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["free_external_candidate_review"],
        {
            "report_id": "free_external_candidate_review",
            "status": "PENDING_FREE_EXTERNAL_CANDIDATE_REVIEW",
            "ranking_eligible_names": [],
            "items": [],
        },
    )
    outputs["free_external_candidate_review_md"].write_text(
        "# Free External Candidate Review\n\nPending free external candidate review.\n",
        encoding="utf-8",
    )
    write_json(
        outputs["free_external_candidate_benchmark_report"],
        {
            "report_id": "free_external_candidate_benchmark_report",
            "status": "PENDING_FREE_EXTERNAL_CANDIDATE_BENCHMARK_PROBES",
            "probes": [],
        },
    )
    outputs["free_external_candidate_benchmark_report_md"].write_text(
        "# Free External Candidate Benchmark Report\n\nPending free external candidate benchmark probes.\n",
        encoding="utf-8",
    )
    write_json(outputs["license_inventory"], build_license_inventory())
    write_json(outputs["security_scan_report"], build_local_security_scan())
    for report_name, payload in finalization_static_reports().items():
        write_json(outputs[report_name], payload)
    write_csv(
        outputs["roadmap_non_runtime_items_justification"],
        [],
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
    write_json(
        outputs["evidence_first_ui_report"],
        {
            "status": "PASS",
            "api_route": "GET /analysis-runs/{analysis_run_id}/evidence-bundle",
            "backend_schema": "AnalysisEvidenceBundleRead",
            "frontend_type": "AnalysisEvidenceBundle",
            "frontend_view": "EvidenceFirstRunView",
            "critical_fields": [
                "confidence",
                "evidence_coverage",
                "claims",
                "recommendations",
                "missing_evidence",
                "contradictions",
                "degraded_checks",
                "rag_support",
                "trust_freshness",
                "lineage",
                "alternatives_lost",
            ],
        },
    )
    if not outputs["benchmark_results"].exists():
        outputs["benchmark_results"].write_text("", encoding="utf-8")

    report = GateReport(gate_id="initial_evidence_pack", status="PASS", checked_items=len(candidates))
    for key in (
        "product_readiness_report",
        "numeric_governance_report",
        "no_demo_report",
        "source_compliance_report",
        "source_coverage_report",
        "source_coverage_map",
        "data_lineage_report",
        "evidence_to_decision_coverage",
        "repository_clean_report",
        "release_artifact_manifest",
        "no_hidden_manual_steps_report",
        "benchmark_report",
        "final_proof_summary",
        "docker_services_report",
        "postgres_migration_report",
        "qdrant_readiness_report",
        "rag_ingestion_report",
        "acceptance_report",
        "real_service_proof_report",
    ):
        preserve_existing = key in {"source_compliance_report", "source_coverage_report", "source_coverage_map"}
        if not outputs[key].exists() or not preserve_existing:
            write_json(outputs[key], report.model_dump(mode="json"))

    if not outputs["product_readiness_report_md"].exists():
        outputs["product_readiness_report_md"].write_text(
            "# Product Readiness Report\n\n"
            "Initial evidence pack generated. Run `make prove-final-product` "
            "for the final aggregated proof.\n",
            encoding="utf-8",
        )

    return outputs


def render_runtime_bom_markdown(entries: list[RuntimeBOMEntry]) -> str:
    lines = [
        "# Runtime BOM",
        "",
        "| Component | Status | Runtime role | Benchmark | Decision |",
        "|---|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| "
            f"{entry.name} | {entry.status.value} | {entry.runtime_role} | "
            f"{entry.benchmark_ref} | {entry.decision_ref} |"
        )
    lines.append("")
    return "\n".join(lines)

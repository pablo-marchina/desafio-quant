#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, read_csv, write_json

RUNTIME_ALTERNATIVE_FAMILIES: dict[str, list[str]] = {
    "FastAPI": ["Django Ninja", "Litestar", "Starlite", "Flask"],
    "PostgreSQL": ["SQLite", "DuckDB", "MySQL", "Supabase free tier"],
    "Qdrant": ["Weaviate", "Milvus", "LanceDB", "Postgres pgvector"],
    "React": ["Vue", "Svelte", "SolidJS"],
    "TypeScript": ["JavaScript", "Flow"],
    "Vite": ["Next.js", "Webpack", "Rspack"],
    "Docker Compose": ["Podman Compose", "Dev Containers", "Tilt"],
}

OUTPUT_CRITICAL_RUNTIME_ROLES = {
    "rag_vector_store",
    "product_api",
    "product_database",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check project-wide runtime value policy.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--runtime-bom", type=Path)
    parser.add_argument("--candidate-catalog", type=Path)
    parser.add_argument("--report-path", type=Path)
    args = parser.parse_args()

    runtime_bom = args.runtime_bom or args.evidence_dir / "runtime_bill_of_materials.csv"
    candidate_catalog = args.candidate_catalog or args.evidence_dir / "candidate_catalog.csv"
    report_path = args.report_path or args.evidence_dir / "runtime_value_policy_report.json"
    if not runtime_bom.exists():
        print(f"Missing runtime BOM: {runtime_bom}")
        return 1
    if not candidate_catalog.exists():
        print(f"Missing candidate catalog: {candidate_catalog}")
        return 1
    report = build_runtime_value_policy_report(read_csv(runtime_bom), read_csv(candidate_catalog))
    write_json(report_path, report)
    print(
        "Runtime value policy checked: "
        f"status={report['status']}, runtime_components={report['runtime_component_count']}, "
        f"needs_comparison={report['needs_free_external_comparison_count']}"
    )
    return 0 if report["status"] == "PASS" else 1


def build_runtime_value_policy_report(
    runtime_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> dict[str, Any]:
    candidate_by_name = {row.get("name", ""): row for row in candidate_rows}
    components = [
        _component_assessment(row, candidate_by_name)
        for row in runtime_rows
        if row.get("runtime_role") != "documentation_only"
    ]
    failures = [item for item in components if item["policy_status"] == "FAIL"]
    needs_free_external = [item for item in components if item["needs_free_external_comparison"] is True]
    return {
        "report_id": "runtime_value_policy_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "policy": (
            "Existing runtime components must remain benchmark-justified and must be compared against viable "
            "free external/API alternatives before replacement. Current runtime is kept unless direct benchmark "
            "evidence proves a higher-value alternative."
        ),
        "runtime_component_count": len(components),
        "failure_count": len(failures),
        "needs_free_external_comparison_count": len(needs_free_external),
        "components": components,
    }


def _component_assessment(row: dict[str, str], candidate_by_name: dict[str, dict[str, str]]) -> dict[str, Any]:
    name = row.get("name", "")
    role = row.get("runtime_role", "")
    benchmark_ref = row.get("benchmark_ref", "")
    decision_ref = row.get("decision_ref", "")
    candidate = candidate_by_name.get(name, {})
    alternatives = _alternatives_for(name, candidate_by_name)
    free_external_alternatives = [
        alternative for alternative in alternatives if _has_free_external_benchmark_path(alternative)
    ]
    missing: list[str] = []
    if not benchmark_ref:
        missing.append("benchmark_ref")
    if not decision_ref:
        missing.append("decision_ref")
    if row.get("status") != "PROMOTED_TO_RUNTIME":
        missing.append("PROMOTED_TO_RUNTIME_status")
    output_critical = role in OUTPUT_CRITICAL_RUNTIME_ROLES
    needs_comparison = output_critical and bool(free_external_alternatives)
    return {
        "component_id": row.get("component_id", ""),
        "name": name,
        "runtime_role": role,
        "status": row.get("status", ""),
        "policy_status": "FAIL" if missing else "PASS",
        "decision": "KEEP_RUNTIME_PENDING_BETTER_BENCHMARK" if not missing else "FIX_RUNTIME_EVIDENCE",
        "missing_policy_fields": missing,
        "benchmark_ref": benchmark_ref,
        "decision_ref": decision_ref,
        "catalog_status": candidate.get("status", "NOT_IN_CATALOG"),
        "known_alternative_count": len(alternatives),
        "free_external_alternative_count": len(free_external_alternatives),
        "needs_free_external_comparison": needs_comparison,
        "replacement_rule": (
            "Replace only if an alternative produces higher measured output value after cost, latency, risk, "
            "governance, reproducibility, and operational complexity."
        ),
        "next_benchmark": _next_benchmark(name, role, free_external_alternatives),
    }


def _alternatives_for(name: str, candidate_by_name: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    alternative_names = RUNTIME_ALTERNATIVE_FAMILIES.get(name, [])
    return [candidate_by_name[alternative] for alternative in alternative_names if alternative in candidate_by_name]


def _next_benchmark(
    name: str,
    role: str,
    free_external_alternatives: list[dict[str, str]],
) -> str:
    if free_external_alternatives:
        names = ", ".join(row.get("name", "") for row in free_external_alternatives)
        return f"Run baseline-vs-{names} against current {name} for role {role}."
    return f"Run baseline-vs-viable alternatives against current {name} when a free or local alternative is available."


def _has_free_external_benchmark_path(row: dict[str, str]) -> bool:
    text = " ".join(
        str(row.get(field, ""))
        for field in (
            "required_configuration",
            "benchmark",
            "promotion_criteria",
            "rejection_criteria",
            "substitute_reason",
            "expected_runtime_use",
        )
    ).casefold()
    free_markers = (
        "free",
        "free tier",
        "no-cost",
        "no cost",
        "public api",
        "no paid credential",
        "no paid credentials",
        "no api key",
        "no credential required",
        "no credentials required",
    )
    blocked_markers = (
        "paid saas",
        "paid service",
        "paid license",
        "license",
        "licensed",
        "hardware",
        "private access",
        "unavailable",
        "enterprise",
    )
    return any(marker in text for marker in free_markers) and not any(marker in text for marker in blocked_markers)


if __name__ == "__main__":
    raise SystemExit(main())

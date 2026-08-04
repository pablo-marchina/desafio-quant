#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

PROMOTED_DECISIONS = {"PROMOTE_TO_PRODUCT_SPIKE", "ADOPTED_TO_PRODUCT"}


@dataclass(frozen=True)
class FamilyAuditSpec:
    family_id: str
    display_name: str
    current_component: str
    product_spike_report: str
    alternatives: tuple[str, ...]


FAMILY_AUDITS: tuple[FamilyAuditSpec, ...] = (
    FamilyAuditSpec(
        family_id="query_rewriting_multiquery",
        display_name="Query rewriting and multi-query retrieval",
        current_component="src/rag/query_rewriting.py",
        product_spike_report="query_rewriting_product_spike_report.json",
        alternatives=(
            "query rewriting",
            "query transformation",
            "query expansion",
            "multi-query retrieval",
            "HyDE",
            "RAG Fusion",
            "Reciprocal Rank Fusion",
            "hybrid retrieval",
        ),
    ),
    FamilyAuditSpec(
        family_id="recommendation_specificity_next_action",
        display_name="Recommendation specificity and next action",
        current_component="src/recommendation/next_action_enrichment.py",
        product_spike_report="next_action_enrichment_product_spike_report.json",
        alternatives=(
            "decision theoretic ranking",
            "value of information",
            "expected information gain",
            "missing evidence prediction",
            "learning to rank",
            "next best action",
        ),
    ),
    FamilyAuditSpec(
        family_id="graphrag_evidence_graph",
        display_name="GraphRAG and evidence graph",
        current_component="src/rag/evidence_graph.py",
        product_spike_report="graphrag_evidence_graph_product_spike_report.json",
        alternatives=(
            "GraphRAG",
            "Knowledge Graph",
            "Neo4j",
            "Memgraph",
            "NetworkX",
            "LlamaIndex PropertyGraphIndex",
            "graph retrieval",
            "entity graph",
        ),
    ),
    FamilyAuditSpec(
        family_id="counter_evidence_retrieval",
        display_name="Counter-evidence retrieval and contradiction handling",
        current_component="src/rag/counter_evidence.py",
        product_spike_report="counter_evidence_product_spike_report.json",
        alternatives=(
            "counter-evidence",
            "contradiction detection",
            "claim verification",
            "knowledge conflict resolution",
            "Corrective RAG",
            "Self-RAG",
            "skeptical RAG",
        ),
    ),
    FamilyAuditSpec(
        family_id="source_quality_trust_freshness",
        display_name="Source trust, quality, and freshness",
        current_component="src/rag/source_quality.py",
        product_spike_report="source_quality_product_spike_report.json",
        alternatives=(
            "source trust",
            "source quality",
            "freshness-aware retrieval",
            "freshness-aware reranking",
            "source-trust-aware reranking",
            "data rights",
            "source compliance",
        ),
    ),
    FamilyAuditSpec(
        family_id="evidence_sufficiency_abstention",
        display_name="Evidence sufficiency and abstention",
        current_component="src/rag/evidence_sufficiency.py",
        product_spike_report="evidence_sufficiency_product_spike_report.json",
        alternatives=(
            "evidence sufficiency",
            "answerability detection",
            "abstention",
            "selective prediction",
            "uncertainty estimation",
            "unsupported claim control",
        ),
    ),
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _lower_terms(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value.lower() for value in values)


def _matching_catalog_rows(rows: list[dict[str, str]], alternatives: tuple[str, ...]) -> list[dict[str, str]]:
    terms = _lower_terms(alternatives)
    matches: list[dict[str, str]] = []
    for row in rows:
        haystack = " ".join(
            [
                row.get("name", ""),
                row.get("category", ""),
                row.get("hypothesis", ""),
                row.get("benchmark", ""),
            ]
        ).lower()
        if any(term in haystack for term in terms):
            matches.append(row)
    return matches


def _matching_external_items(report: dict[str, Any], alternatives: tuple[str, ...]) -> list[dict[str, Any]]:
    terms = _lower_terms(alternatives)
    items = report.get("items", [])
    matches: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return matches
    for item in items:
        if not isinstance(item, dict):
            continue
        haystack = " ".join(
            [
                str(item.get("name", "")),
                " ".join(str(category) for category in item.get("categories", []) or []),
            ]
        ).lower()
        if any(term in haystack for term in terms):
            matches.append(item)
    return matches


def _matching_probe_items(report: dict[str, Any], alternatives: tuple[str, ...]) -> list[dict[str, Any]]:
    terms = _lower_terms(alternatives)
    probes = report.get("probes", [])
    matches: list[dict[str, Any]] = []
    if not isinstance(probes, list):
        return matches
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        haystack = " ".join([str(probe.get("name", "")), str(probe.get("status", ""))]).lower()
        if any(term in haystack for term in terms):
            matches.append(probe)
    return matches


def _direct_gap_resolution_map(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    resolution: dict[tuple[str, str], dict[str, Any]] = {}
    for item in report.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        family_id = str(item.get("family_id", ""))
        candidate_name = str(item.get("candidate_name", ""))
        if family_id and candidate_name:
            resolution[(family_id, candidate_name)] = item
    return resolution


def _has_positive_spike_evidence(report: dict[str, Any]) -> bool:
    decision = str(report.get("decision", ""))
    status = str(report.get("status", ""))
    quality_delta = float(report.get("quality_delta", 0) or 0)
    regression_count = int(report.get("regression_count", 0) or 0)
    return status == "PASS" and decision in PROMOTED_DECISIONS and quality_delta > 0 and regression_count == 0


def _audit_family(
    spec: FamilyAuditSpec,
    *,
    evidence_dir: Path,
    catalog_rows: list[dict[str, str]],
    external_report: dict[str, Any],
    external_probe_report: dict[str, Any],
    direct_resolution: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    spike_report = read_json(evidence_dir / spec.product_spike_report)
    component_path = PROJECT_ROOT / spec.current_component
    catalog_matches = _matching_catalog_rows(catalog_rows, spec.alternatives)
    catalog_alternatives = [
        {
            "name": row.get("name"),
            "category": row.get("category"),
            "status": row.get("status"),
            "benchmark": row.get("benchmark"),
            "direct_benchmark_outcome": direct_resolution.get((spec.family_id, str(row.get("name", ""))), {}).get(
                "outcome"
            ),
            "reason": "Catalog candidate was not directly compared against the implemented family output.",
        }
        for row in catalog_matches
        if not direct_resolution.get((spec.family_id, str(row.get("name", ""))), {}).get("resolved_gap")
    ]
    external_matches = _matching_external_items(external_report, spec.alternatives)
    probe_matches = _matching_probe_items(external_probe_report, spec.alternatives)
    eligible_external = [
        item
        for item in external_matches
        if item.get("ranking_eligible") is True
        or str(item.get("verification_status", "")).startswith(("FREE_", "INTERNAL_LOCAL"))
    ]
    executed_probe_names = {
        str(item.get("name"))
        for item in probe_matches
        if str(item.get("status")) in {"PASS", "FAIL", "NO_QUALITY_LIFT", "ADOPTED"}
    }
    untested_free_alternatives = [
        {
            "name": item.get("name"),
            "verification_status": item.get("verification_status"),
            "official_source_url": item.get("official_source_url"),
            "reason": (
                "Free/local/API-eligible alternative has not produced a direct quality benchmark "
                "against this product family."
            ),
        }
        for item in eligible_external
        if str(item.get("name")) not in executed_probe_names
    ]
    positive_evidence = _has_positive_spike_evidence(spike_report)
    component_exists = component_path.exists()

    direct_alternative_gap_count = len(catalog_alternatives) + len(untested_free_alternatives)

    if not component_exists or not spike_report:
        status = "MISSING_CURRENT_EVIDENCE"
        conclusion = "Current family component or product spike report is missing."
    elif positive_evidence and direct_alternative_gap_count:
        status = "BEST_WITH_CURRENT_EVIDENCE_NEEDS_DIRECT_ALTERNATIVE_BENCHMARK"
        conclusion = (
            "Current implementation improved output quality in local product-spike benchmarks, but cataloged "
            "alternatives still need direct family benchmarks before claiming global best."
        )
    elif positive_evidence:
        status = "BEST_WITH_CURRENT_EVIDENCE"
        conclusion = (
            "Current implementation is the best evidenced option among locally implemented and benchmarked choices."
        )
    else:
        status = "NEEDS_CURRENT_IMPLEMENTATION_REVIEW"
        conclusion = "Current implementation does not yet have a passing positive-lift product-spike report."

    return {
        "family_id": spec.family_id,
        "display_name": spec.display_name,
        "status": status,
        "conclusion": conclusion,
        "global_best_guarantee": False,
        "current_component": spec.current_component,
        "current_component_exists": component_exists,
        "product_spike_report": spec.product_spike_report,
        "product_spike_status": spike_report.get("status"),
        "product_spike_decision": spike_report.get("decision"),
        "baseline_score": spike_report.get("baseline_score"),
        "candidate_score": spike_report.get("candidate_score"),
        "quality_delta": spike_report.get("quality_delta"),
        "case_count": spike_report.get("case_count"),
        "regression_count": spike_report.get("regression_count"),
        "catalog_alternative_count": len(catalog_matches),
        "catalog_alternatives_needing_direct_benchmark": catalog_alternatives[:25],
        "external_or_free_alternative_count": len(external_matches),
        "untested_free_alternative_count": len(untested_free_alternatives),
        "untested_free_alternatives": untested_free_alternatives,
        "direct_alternative_gap_count": direct_alternative_gap_count,
        "alternative_terms": list(spec.alternatives),
    }


def build_report(evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> dict[str, Any]:
    catalog_rows = read_csv(evidence_dir / "candidate_catalog.csv")
    external_report = read_json(evidence_dir / "external_free_verification_report.json")
    external_probe_report = read_json(evidence_dir / "free_external_candidate_benchmark_report.json")
    direct_gap_report = read_json(evidence_dir / "direct_alternative_gap_benchmark_report.json")
    direct_resolution = _direct_gap_resolution_map(direct_gap_report)

    families = [
        _audit_family(
            spec,
            evidence_dir=evidence_dir,
            catalog_rows=catalog_rows,
            external_report=external_report,
            external_probe_report=external_probe_report,
            direct_resolution=direct_resolution,
        )
        for spec in FAMILY_AUDITS
    ]
    missing = [family for family in families if family["status"] == "MISSING_CURRENT_EVIDENCE"]
    needs_direct = [
        family
        for family in families
        if family["status"] == "BEST_WITH_CURRENT_EVIDENCE_NEEDS_DIRECT_ALTERNATIVE_BENCHMARK"
    ]
    current_best = [
        family
        for family in families
        if family["status"]
        in {
            "BEST_WITH_CURRENT_EVIDENCE",
            "BEST_WITH_CURRENT_EVIDENCE_NEEDS_DIRECT_ALTERNATIVE_BENCHMARK",
        }
    ]
    gate_status = "FAIL" if missing else "PASS"
    conclusion = (
        "Implemented families have positive local product-spike evidence, but global best is not guaranteed."
        if gate_status == "PASS"
        else "At least one implemented family is missing current product evidence."
    )
    return {
        "report_id": "implemented_family_best_tool_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": gate_status,
        "conclusion": conclusion,
        "global_best_guarantee": False,
        "family_count": len(families),
        "current_best_with_evidence_count": len(current_best),
        "needs_direct_alternative_benchmark_count": len(needs_direct),
        "missing_current_evidence_count": len(missing),
        "families": families,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Implemented Family Best Tool Report",
        "",
        f"Status: {report['status']}",
        f"Conclusion: {report['conclusion']}",
        f"Global best guarantee: {report['global_best_guarantee']}",
        "",
        "| Family | Status | Quality delta | Untested free alternatives |",
        "| --- | --- | ---: | ---: |",
    ]
    for family in report["families"]:
        lines.append(
            "| {display_name} | {status} | {quality_delta} | {untested_free_alternative_count} |".format(**family)
        )
    lines.extend(["", "## Direct Alternative Benchmark Gaps", ""])
    for family in report["families"]:
        gaps = family.get("direct_alternative_gap_count", 0)
        lines.append(f"- {family['display_name']}: {gaps} direct alternative benchmark gap(s).")
    lines.extend(
        [
            "",
            "This report proves best-with-current-evidence only. It does not claim that no external, paid,",
            "newly released, or unbenchmarked tool could improve the product.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit best-tool evidence for implemented product families.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-path", type=Path)
    args = parser.parse_args()

    report_path = args.report_path or args.evidence_dir / "implemented_family_best_tool_report.json"
    markdown_path = args.markdown_path or args.evidence_dir / "implemented_family_best_tool_report.md"
    report = build_report(args.evidence_dir)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    print(
        "Implemented family best-tool audit: "
        f"status={report['status']} "
        f"current_best_with_evidence={report['current_best_with_evidence_count']} "
        f"needs_direct_alternative_benchmark={report['needs_direct_alternative_benchmark_count']} "
        f"global_best_guarantee={report['global_best_guarantee']}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

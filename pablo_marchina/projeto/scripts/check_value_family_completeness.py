#!/usr/bin/env python3
# ruff: noqa: E402,I001
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.governance.artifacts import DEFAULT_EVIDENCE_DIR, write_json

IMPLEMENTED_PRODUCT_FAMILY_IDS: frozenset[str] = frozenset(
    {
        "query_rewriting_multiquery",
        "recommendation_specificity_next_action",
        "graphrag_evidence_graph",
        "counter_evidence_retrieval",
        "source_trust_freshness_ranking",
        "source_trust_freshness",
        "source_quality_trust_freshness",
        "evidence_sufficiency_abstention",
    }
)

FAMILY_ALIASES: dict[str, str] = {
    "source_trust_freshness_ranking": "source_quality_trust_freshness",
    "source_trust_freshness": "source_quality_trust_freshness",
}


def normalize_family_id(family_id: str) -> str:
    return FAMILY_ALIASES.get(family_id, family_id)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _counter(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _diagnostic_family_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    families: dict[str, dict[str, Any]] = {}
    for item in report.get("family_decisions", []) or []:
        if not isinstance(item, dict):
            continue
        family_id = str(item.get("family_id", ""))
        if family_id:
            families[normalize_family_id(family_id)] = item
    return families


def _implemented_family_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    families: dict[str, dict[str, Any]] = {}
    for item in report.get("families", []) or []:
        if not isinstance(item, dict):
            continue
        family_id = str(item.get("family_id", ""))
        if family_id:
            families[normalize_family_id(family_id)] = item
    return families


def _category_summaries(catalog_rows: list[dict[str, str]], output_report: dict[str, Any]) -> list[dict[str, Any]]:
    output_by_category = output_report.get("by_category", {})
    by_category: dict[str, list[dict[str, str]]] = {}
    for row in catalog_rows:
        by_category.setdefault(row.get("category", "UNKNOWN"), []).append(row)

    summaries: list[dict[str, Any]] = []
    for category, rows in sorted(by_category.items()):
        statuses = _counter([row.get("status", "UNKNOWN") for row in rows])
        output_decisions = output_by_category.get(category, {}) if isinstance(output_by_category, dict) else {}
        quality_measured_count = 0
        promotion_allowed_count = 0
        for decision in output_report.get("decisions", []) or []:
            if not isinstance(decision, dict) or decision.get("category") != category:
                continue
            if decision.get("quality_lift_measured") is True:
                quality_measured_count += 1
            if decision.get("promotion_allowed") is True:
                promotion_allowed_count += 1
        summaries.append(
            {
                "category": category,
                "candidate_count": len(rows),
                "catalog_status_counts": statuses,
                "output_decisions": output_decisions,
                "quality_lift_measured_count": quality_measured_count,
                "promotion_allowed_count": promotion_allowed_count,
                "status": "CATALOGED_NOT_EXHAUSTIVELY_VALUE_TESTED",
            }
        )
    return summaries


def build_report(evidence_dir: Path = DEFAULT_EVIDENCE_DIR) -> dict[str, Any]:
    catalog_rows = read_csv(evidence_dir / "candidate_catalog.csv")
    diagnostic_report = read_json(evidence_dir / "diagnostic_value_triage_report.json")
    implemented_report = read_json(evidence_dir / "implemented_family_best_tool_report.json")
    output_report = read_json(evidence_dir / "output_value_benchmark_report.json")

    diagnostic_families = _diagnostic_family_map(diagnostic_report)
    implemented_families = _implemented_family_map(implemented_report)
    category_summaries = _category_summaries(catalog_rows, output_report)

    family_items: list[dict[str, Any]] = []
    all_family_ids = sorted(set(diagnostic_families) | set(implemented_families))
    for family_id in all_family_ids:
        diagnostic = diagnostic_families.get(family_id, {})
        implemented = implemented_families.get(family_id, {})
        has_product_spike = family_id in implemented_families
        has_diagnostic_signal = family_id in diagnostic_families
        direct_gap_count = int(implemented.get("direct_alternative_gap_count", 0) or 0)
        if has_product_spike and direct_gap_count:
            status = "IMPLEMENTED_WITH_UNEXHAUSTED_INTERNAL_TECHNIQUES"
        elif has_product_spike:
            status = "IMPLEMENTED_VALUE_FAMILY"
        else:
            status = "DIAGNOSTIC_SIGNAL_NOT_IMPLEMENTED"
        family_items.append(
            {
                "family_id": family_id,
                "display_name": implemented.get("display_name") or diagnostic.get("display_name") or family_id,
                "status": status,
                "has_diagnostic_signal": has_diagnostic_signal,
                "has_product_spike": has_product_spike,
                "quality_delta": implemented.get("quality_delta") or diagnostic.get("quality_delta"),
                "direct_alternative_gap_count": direct_gap_count,
                "affected_case_count": diagnostic.get("affected_case_count"),
                "matching_candidate_count": len(diagnostic.get("matching_candidates", []) or []),
            }
        )

    implemented_count = sum(1 for item in family_items if item["has_product_spike"])
    diagnostic_only_count = sum(
        1 for item in family_items if item["has_diagnostic_signal"] and not item["has_product_spike"]
    )
    direct_gap_total = sum(int(item["direct_alternative_gap_count"]) for item in family_items)
    categories_without_quality_lift = [
        item["category"] for item in category_summaries if int(item["quality_lift_measured_count"]) == 0
    ]
    exhaustive_value_family_discovery = (
        diagnostic_only_count == 0 and direct_gap_total == 0 and len(categories_without_quality_lift) == 0
    )
    status = "PASS" if catalog_rows and family_items else "FAIL"
    conclusion = (
        "Value discovery is not exhaustive: the product has implemented proven high-value families, "
        "but not every roadmap category and technique has direct output-quality evidence."
    )
    return {
        "report_id": "value_family_completeness_report",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "conclusion": conclusion,
        "exhaustive_value_family_discovery": exhaustive_value_family_discovery,
        "global_no_more_value_guarantee": False,
        "catalog_candidate_count": len(catalog_rows),
        "roadmap_category_count": len(category_summaries),
        "diagnostic_case_count": diagnostic_report.get("case_count", 0),
        "diagnostic_family_count": len(diagnostic_families),
        "implemented_value_family_count": implemented_count,
        "diagnostic_signal_not_implemented_count": diagnostic_only_count,
        "direct_alternative_gap_total": direct_gap_total,
        "categories_without_direct_quality_lift_count": len(categories_without_quality_lift),
        "categories_without_direct_quality_lift": categories_without_quality_lift,
        "families": family_items,
        "category_summaries": category_summaries,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Value Family Completeness Report",
        "",
        f"Status: {report['status']}",
        f"Exhaustive value-family discovery: {report['exhaustive_value_family_discovery']}",
        f"Global no-more-value guarantee: {report['global_no_more_value_guarantee']}",
        f"Conclusion: {report['conclusion']}",
        "",
        "## Summary",
        "",
        f"- Catalog candidates: {report['catalog_candidate_count']}",
        f"- Roadmap categories: {report['roadmap_category_count']}",
        f"- Diagnostic cases: {report['diagnostic_case_count']}",
        f"- Diagnostic families: {report['diagnostic_family_count']}",
        f"- Implemented value families: {report['implemented_value_family_count']}",
        f"- Diagnostic-only families: {report['diagnostic_signal_not_implemented_count']}",
        f"- Direct alternative gaps inside implemented families: {report['direct_alternative_gap_total']}",
        "- Categories without direct quality-lift measurement: "
        f"{report['categories_without_direct_quality_lift_count']}",
        "",
        "## Families",
        "",
        "| Family | Status | Delta | Direct gaps |",
        "| --- | --- | ---: | ---: |",
    ]
    for family in report["families"]:
        lines.append(
            "| {display_name} | {status} | {quality_delta} | {direct_alternative_gap_count} |".format(**family)
        )
    lines.extend(
        [
            "",
            "## Roadmap Categories",
            "",
            "| Category | Candidates | Quality-lift measured | Promotion allowed |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for category in report["category_summaries"]:
        lines.append(
            "| {category} | {candidate_count} | {quality_lift_measured_count} | {promotion_allowed_count} |".format(
                **category
            )
        )
    lines.extend(
        [
            "",
            "This report intentionally avoids claiming completeness. Completeness requires direct output-quality",
            "benchmarks across every roadmap category and direct comparisons inside each implemented family.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether value-generating families are exhaustively covered.")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--report-path", type=Path)
    parser.add_argument("--markdown-path", type=Path)
    args = parser.parse_args()

    report_path = args.report_path or args.evidence_dir / "value_family_completeness_report.json"
    markdown_path = args.markdown_path or args.evidence_dir / "value_family_completeness_report.md"
    report = build_report(args.evidence_dir)
    write_json(report_path, report)
    write_markdown(markdown_path, report)
    print(
        "Value family completeness audit: "
        f"status={report['status']} "
        f"exhaustive={report['exhaustive_value_family_discovery']} "
        f"implemented={report['implemented_value_family_count']} "
        f"direct_alternative_gaps={report['direct_alternative_gap_total']}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

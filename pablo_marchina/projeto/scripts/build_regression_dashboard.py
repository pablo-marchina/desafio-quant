#!/usr/bin/env python3
"""Build a local regression dashboard from corpus maintenance reports."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAINTENANCE_ROOT = PROJECT_ROOT / "reports" / "corpus-maintenance"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "regression_reports"
DEFAULT_ANSWER_QUALITY_JUNIT = DEFAULT_OUTPUT_DIR / "answer_quality_eval_junit.xml"
DEFAULT_LLM_JUDGE_REPORT = DEFAULT_OUTPUT_DIR / "answer_quality_llm_judge_report.json"

STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"

METRIC_DEFAULTS: dict[str, int | float | bool | str | None] = {
    "documents_seen": 0,
    "documents_valid": 0,
    "documents_skipped": 0,
    "chunks_created": 0,
    "chunks_upserted": 0,
    "sources_failed": 0,
    "validation_errors": 0,
    "stale_sources": 0,
    "expired_sources": 0,
    "deprecated_sources": 0,
    "rag_eval_passed": None,
    "rag_eval_failed_cases": 0,
    "golden_eval_passed": None,
    "golden_eval_failed_cases": 0,
    "answer_quality_junit_present": False,
    "answer_quality_tests": 0,
    "answer_quality_failures": 0,
    "answer_quality_errors": 0,
    "answer_quality_skipped": 0,
    "answer_quality_passed": None,
    "answer_quality_failed_cases": 0,
    "unsupported_claim_count": 0,
    "required_sections_missing": 0,
    "citation_coverage": 0.0,
    "answer_quality_status": "not run",
    "llm_judge_report_present": False,
    "llm_judge_status": "INFO",
    "llm_judge_provider": "not run",
    "llm_judge_total_cases": 0,
    "llm_judge_completed_cases": 0,
    "llm_judge_error_cases": 0,
    "llm_judge_mean_score": 0.0,
    "llm_judge_mean_faithfulness_score": 0.0,
    "llm_judge_mean_answer_relevancy_score": 0.0,
    "llm_judge_mean_groundedness_score": 0.0,
    "llm_judge_mean_completeness_score": 0.0,
    "llm_judge_mean_uncertainty_honesty_score": 0.0,
    "llm_judge_mean_executive_usefulness_score": 0.0,
    "action_brief_required_sections_passed": None,
    "missing_context_count": 0,
    "missing_evidence_count": 0,
}

REQUIRED_MARKDOWN_SECTIONS = [
    "Overview",
    "Ingestion",
    "Freshness",
    "RAG Evals",
    "Golden Evals & Action Brief Checks",
    "Answer Quality",
    "Optional LLM Judge",
    "Warnings",
    "Failures",
]


@dataclass
class DashboardInput:
    name: str
    path: str | None
    status: str
    message: str = ""


@dataclass
class Dashboard:
    dashboard_version: str
    generated_at: str
    status: str
    metrics: dict[str, int | float | bool | str | None]
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    inputs: list[DashboardInput] = field(default_factory=list)
    failed_cases: dict[str, list[str]] = field(
        default_factory=lambda: {"rag_eval": [], "golden_eval": [], "answer_quality": []}
    )
    failure_details: dict[str, list[str]] = field(
        default_factory=lambda: {"rag_eval": [], "golden_eval": [], "answer_quality": []}
    )
    reports_dir: str | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the RAG/Action Brief regression dashboard.",
    )
    parser.add_argument(
        "--reports-dir",
        default=None,
        help=(
            "Directory containing maintenance reports. If omitted, the latest "
            "reports/corpus-maintenance run is used when present."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for latest_dashboard.md and latest_dashboard.json.",
    )
    parser.add_argument(
        "--no-fail-on-status",
        action="store_true",
        help="Always exit 0 after writing files; useful before artifact upload in CI.",
    )
    return parser.parse_args(argv)


def build_dashboard(reports_dir: Path | None = None) -> Dashboard:
    resolved_reports_dir = _resolve_reports_dir(reports_dir)
    dashboard = Dashboard(
        dashboard_version="1.0",
        generated_at=datetime.now(UTC).isoformat(),
        status=STATUS_PASS,
        metrics=dict(METRIC_DEFAULTS),
        reports_dir=str(resolved_reports_dir) if resolved_reports_dir else None,
    )

    if resolved_reports_dir is None:
        dashboard.warnings.append("No corpus maintenance reports directory found.")

    _read_source_sync_report(dashboard, resolved_reports_dir)
    _read_freshness_report(dashboard, resolved_reports_dir)
    _read_ingestion_report(dashboard, resolved_reports_dir)
    _read_eval_junit(dashboard, resolved_reports_dir, "rag_eval_junit.xml", "rag_eval")
    _read_eval_junit(dashboard, resolved_reports_dir, "golden_eval_junit.xml", "golden_eval")
    answer_quality_fallback = DEFAULT_ANSWER_QUALITY_JUNIT if reports_dir is None else None
    _read_eval_junit(
        dashboard,
        resolved_reports_dir,
        "answer_quality_eval_junit.xml",
        "answer_quality",
        fallback_path=answer_quality_fallback,
    )
    llm_judge_fallback = DEFAULT_LLM_JUDGE_REPORT if reports_dir is None else None
    _read_optional_llm_judge_report(dashboard, resolved_reports_dir, llm_judge_fallback)
    _derive_action_brief_checks(dashboard)
    _evaluate_status(dashboard)
    return dashboard


def write_dashboard(
    dashboard: Dashboard,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "latest_dashboard.md"
    json_path = output_dir / "latest_dashboard.json"

    md_path.write_text(render_markdown(dashboard), encoding="utf-8")
    json_path.write_text(
        json.dumps(_dashboard_to_dict(dashboard), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return md_path, json_path


def render_markdown(dashboard: Dashboard) -> str:
    metrics = dashboard.metrics
    lines = [
        "# RAG / Action Brief Regression Dashboard",
        "",
        "## Overview",
        "",
        f"- Status: **{dashboard.status}**",
        f"- Generated at: `{dashboard.generated_at}`",
        f"- Reports dir: `{dashboard.reports_dir or 'not found'}`",
        "",
        "## Ingestion",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| documents_seen | {metrics['documents_seen']} |",
        f"| documents_valid | {metrics['documents_valid']} |",
        f"| documents_skipped | {metrics['documents_skipped']} |",
        f"| chunks_created | {metrics['chunks_created']} |",
        f"| chunks_upserted | {metrics['chunks_upserted']} |",
        f"| sources_failed | {metrics['sources_failed']} |",
        f"| validation_errors | {metrics['validation_errors']} |",
        "",
        "## Freshness",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| stale_sources | {metrics['stale_sources']} |",
        f"| expired_sources | {metrics['expired_sources']} |",
        f"| deprecated_sources | {metrics['deprecated_sources']} |",
        "",
        "## RAG Evals",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| rag_eval_passed | {_format_value(metrics['rag_eval_passed'])} |",
        f"| rag_eval_failed_cases | {metrics['rag_eval_failed_cases']} |",
        f"| missing_context_count | {metrics['missing_context_count']} |",
        "",
        "## Golden Evals & Action Brief Checks",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| golden_eval_passed | {_format_value(metrics['golden_eval_passed'])} |",
        f"| golden_eval_failed_cases | {metrics['golden_eval_failed_cases']} |",
        (
            "| action_brief_required_sections_passed | "
            f"{_format_value(metrics['action_brief_required_sections_passed'])} |"
        ),
        f"| missing_evidence_count | {metrics['missing_evidence_count']} |",
        "",
        "## Answer Quality",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| answer_quality_passed | {_format_value(metrics['answer_quality_passed'])} |",
        ("| answer_quality_junit_present | " f"{_format_value(metrics['answer_quality_junit_present'])} |"),
        f"| answer_quality_tests | {metrics['answer_quality_tests']} |",
        f"| answer_quality_failures | {metrics['answer_quality_failures']} |",
        f"| answer_quality_errors | {metrics['answer_quality_errors']} |",
        f"| answer_quality_skipped | {metrics['answer_quality_skipped']} |",
        f"| answer_quality_failed_cases | {metrics['answer_quality_failed_cases']} |",
        f"| unsupported_claim_count | {metrics['unsupported_claim_count']} |",
        f"| required_sections_missing | {metrics['required_sections_missing']} |",
        f"| citation_coverage | {metrics['citation_coverage']} |",
        f"| answer_quality_status | {metrics['answer_quality_status']} |",
        "",
        "## Optional LLM Judge",
        "",
        "Informational only. This optional judge is not a CI gate.",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| llm_judge_status | {metrics['llm_judge_status']} |",
        f"| llm_judge_report_present | {_format_value(metrics['llm_judge_report_present'])} |",
        f"| llm_judge_provider | {metrics['llm_judge_provider']} |",
        f"| llm_judge_total_cases | {metrics['llm_judge_total_cases']} |",
        f"| llm_judge_completed_cases | {metrics['llm_judge_completed_cases']} |",
        f"| llm_judge_error_cases | {metrics['llm_judge_error_cases']} |",
        f"| llm_judge_mean_score | {metrics['llm_judge_mean_score']} |",
        f"| llm_judge_mean_faithfulness_score | {metrics['llm_judge_mean_faithfulness_score']} |",
        ("| llm_judge_mean_answer_relevancy_score | " f"{metrics['llm_judge_mean_answer_relevancy_score']} |"),
        f"| llm_judge_mean_groundedness_score | {metrics['llm_judge_mean_groundedness_score']} |",
        f"| llm_judge_mean_completeness_score | {metrics['llm_judge_mean_completeness_score']} |",
        ("| llm_judge_mean_uncertainty_honesty_score | " f"{metrics['llm_judge_mean_uncertainty_honesty_score']} |"),
        ("| llm_judge_mean_executive_usefulness_score | " f"{metrics['llm_judge_mean_executive_usefulness_score']} |"),
        "",
        "## Warnings",
        "",
    ]
    if dashboard.warnings:
        lines.extend(f"- {item}" for item in dashboard.warnings)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Failures",
            "",
        ]
    )
    if dashboard.failures:
        lines.extend(f"- {item}" for item in dashboard.failures)
    else:
        lines.append("- None.")

    if any(dashboard.failed_cases.values()):
        lines.extend(["", "## Failed Cases", ""])
        for label, cases in dashboard.failed_cases.items():
            if cases:
                lines.append(f"### {label}")
                lines.extend(f"- `{case}`" for case in cases)
                lines.append("")

    if any(dashboard.failure_details.values()):
        lines.extend(["", "## Failure Details", ""])
        for label, details in dashboard.failure_details.items():
            if details:
                lines.append(f"### {label}")
                lines.extend(f"- {detail}" for detail in details[:10])
                if len(details) > 10:
                    lines.append(f"- ... and {len(details) - 10} more")
                lines.append("")

    lines.extend(["", "## Inputs", ""])
    for item in dashboard.inputs:
        path = item.path or "not found"
        message = f" - {item.message}" if item.message else ""
        lines.append(f"- `{item.name}`: {item.status} (`{path}`){message}")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    reports_dir = Path(args.reports_dir) if args.reports_dir else None
    output_dir = Path(args.output_dir)
    dashboard = build_dashboard(reports_dir)
    md_path, json_path = write_dashboard(dashboard, output_dir)
    print(f"Dashboard status: {dashboard.status}")
    print(f"Markdown: {md_path}")
    print(f"JSON: {json_path}")
    if args.no_fail_on_status:
        return 0
    return 1 if dashboard.status == STATUS_FAIL else 0


def _read_source_sync_report(dashboard: Dashboard, reports_dir: Path | None) -> None:
    path = _find_report(
        reports_dir,
        ["source_sync_dry_run.json", "source_sync_promote.json"],
        fallback_glob=PROJECT_ROOT / "data" / "nvidia_corpus" / "sync_reports" / "*.json",
    )
    data = _load_json_input(dashboard, "source_sync", path)
    if not data:
        return
    dashboard.metrics["sources_failed"] = max(
        int(dashboard.metrics["sources_failed"] or 0),
        _count_value(data.get("sources_failed")),
    )
    dashboard.metrics["validation_errors"] = max(
        int(dashboard.metrics["validation_errors"] or 0),
        _count_value(data.get("validation_errors")),
    )
    dashboard.metrics["missing_context_count"] += _count_value(data.get("missing_context"))
    dashboard.metrics["missing_evidence_count"] += _count_value(data.get("missing_evidence"))


def _read_freshness_report(dashboard: Dashboard, reports_dir: Path | None) -> None:
    path = _find_report(
        reports_dir,
        ["freshness_audit.json", "freshness_audit.md"],
        fallback_glob=PROJECT_ROOT / "data" / "ingestion_reports" / "freshness*.md",
    )
    if path is None:
        dashboard.inputs.append(DashboardInput("freshness", None, "missing"))
        dashboard.warnings.append("Freshness audit report not found.")
        return
    dashboard.inputs.append(DashboardInput("freshness", str(path), "found"))
    if path.suffix == ".json":
        data = _load_json_file(path)
        if data is None:
            dashboard.warnings.append(f"Could not parse freshness report: {path}")
            return
        for key in ("stale_sources", "expired_sources", "deprecated_sources"):
            dashboard.metrics[key] = int(data.get(key, 0) or 0)
        dashboard.metrics["missing_context_count"] += _count_value(data.get("missing_context"))
        dashboard.metrics["missing_evidence_count"] += _count_value(data.get("missing_evidence"))
        return

    text = path.read_text(encoding="utf-8")
    for key in ("stale_sources", "expired_sources", "deprecated_sources"):
        dashboard.metrics[key] = _extract_markdown_counter(text, key)


def _read_ingestion_report(dashboard: Dashboard, reports_dir: Path | None) -> None:
    path = _find_report(
        reports_dir,
        ["qdrant_ingestion.json", "qdrant_ingest_dry_run.json"],
        fallback_glob=PROJECT_ROOT / "data" / "ingestion_reports" / "qdrant*.json",
    )
    data = _load_json_input(dashboard, "ingestion", path)
    if not data:
        return
    for key in (
        "documents_seen",
        "documents_valid",
        "documents_skipped",
        "chunks_created",
        "chunks_upserted",
    ):
        dashboard.metrics[key] = int(data.get(key, 0) or 0)
    dashboard.metrics["sources_failed"] = max(
        int(dashboard.metrics["sources_failed"] or 0),
        _count_value(data.get("sources_failed")),
    )
    dashboard.metrics["validation_errors"] = max(
        int(dashboard.metrics["validation_errors"] or 0),
        _count_value(data.get("validation_errors")),
    )
    dashboard.metrics["missing_context_count"] += _count_value(data.get("missing_context"))
    dashboard.metrics["missing_evidence_count"] += _count_value(data.get("missing_evidence"))


def _read_eval_junit(
    dashboard: Dashboard,
    reports_dir: Path | None,
    filename: str,
    metric_prefix: str,
    *,
    warn_when_missing: bool = True,
    fallback_path: Path | None = None,
) -> None:
    path = reports_dir / filename if reports_dir else None
    if (path is None or not path.is_file()) and fallback_path is not None:
        path = fallback_path if fallback_path.is_file() else path
    if path is None or not path.is_file():
        dashboard.inputs.append(DashboardInput(metric_prefix, str(path) if path else None, "missing"))
        if warn_when_missing:
            dashboard.warnings.append(f"{filename} not found.")
        if metric_prefix == "answer_quality":
            dashboard.metrics["answer_quality_junit_present"] = False
            dashboard.metrics["answer_quality_status"] = STATUS_WARN
        return

    dashboard.inputs.append(DashboardInput(metric_prefix, str(path), "found"))
    parsed = _parse_junit(path)
    if parsed is None:
        dashboard.warnings.append(f"Could not parse {filename}.")
        if metric_prefix == "answer_quality":
            dashboard.metrics["answer_quality_junit_present"] = True
            dashboard.metrics["answer_quality_status"] = STATUS_WARN
        return

    passed_key = f"{metric_prefix}_passed"
    failed_key = f"{metric_prefix}_failed_cases"
    failed_count = parsed["failures"] + parsed["errors"]
    dashboard.metrics[passed_key] = failed_count == 0
    dashboard.metrics[failed_key] = failed_count
    dashboard.failed_cases[metric_prefix] = parsed["failed_cases"]
    dashboard.failure_details[metric_prefix] = parsed["failure_details"]
    if metric_prefix == "answer_quality":
        dashboard.metrics["answer_quality_junit_present"] = True
        dashboard.metrics["answer_quality_tests"] = int(parsed["tests"])
        dashboard.metrics["answer_quality_failures"] = int(parsed["failures"])
        dashboard.metrics["answer_quality_errors"] = int(parsed["errors"])
        dashboard.metrics["answer_quality_skipped"] = int(parsed["skipped"])
        dashboard.metrics["unsupported_claim_count"] = int(parsed["unsupported_claim_count"])
        dashboard.metrics["required_sections_missing"] = int(parsed["required_sections_missing"])
        dashboard.metrics["citation_coverage"] = parsed["citation_coverage"]
        dashboard.metrics["answer_quality_status"] = STATUS_PASS if failed_count == 0 else STATUS_FAIL
    dashboard.metrics["missing_context_count"] = max(
        int(dashboard.metrics["missing_context_count"] or 0),
        int(parsed["missing_context_count"]),
    )
    dashboard.metrics["missing_evidence_count"] = max(
        int(dashboard.metrics["missing_evidence_count"] or 0),
        int(parsed["missing_evidence_count"]),
    )


def _derive_action_brief_checks(dashboard: Dashboard) -> None:
    golden_passed = dashboard.metrics["golden_eval_passed"]
    if golden_passed is None:
        dashboard.metrics["action_brief_required_sections_passed"] = None
        return
    failed_cases = dashboard.failed_cases["golden_eval"]
    action_brief_failures = [case for case in failed_cases if "action_brief" in case.lower() or "brief" in case.lower()]
    dashboard.metrics["action_brief_required_sections_passed"] = golden_passed is True and not action_brief_failures


def _read_optional_llm_judge_report(
    dashboard: Dashboard,
    reports_dir: Path | None,
    fallback_path: Path | None,
) -> None:
    path = reports_dir / "answer_quality_llm_judge_report.json" if reports_dir else None
    if (path is None or not path.is_file()) and fallback_path is not None:
        path = fallback_path if fallback_path.is_file() else path
    if path is None or not path.is_file():
        dashboard.inputs.append(
            DashboardInput(
                "answer_quality_llm_judge",
                str(path) if path else None,
                "info",
                "optional report not run",
            )
        )
        dashboard.metrics["llm_judge_status"] = "INFO"
        dashboard.metrics["llm_judge_report_present"] = False
        return

    data = _load_json_file(path)
    dashboard.inputs.append(DashboardInput("answer_quality_llm_judge", str(path), "found", "optional report"))
    dashboard.metrics["llm_judge_report_present"] = True
    dashboard.metrics["llm_judge_status"] = "INFO"
    if data is None:
        dashboard.metrics["llm_judge_provider"] = "malformed"
        return

    provider = data.get("provider", {})
    summary = data.get("summary", {})
    dashboard.metrics["llm_judge_provider"] = str(provider.get("provider_name", "unknown"))
    dashboard.metrics["llm_judge_total_cases"] = int(data.get("total_cases", 0) or 0)
    dashboard.metrics["llm_judge_completed_cases"] = int(data.get("completed_cases", 0) or 0)
    dashboard.metrics["llm_judge_error_cases"] = int(data.get("error_cases", 0) or 0)
    dashboard.metrics["llm_judge_mean_score"] = float(summary.get("mean_score", 0.0) or 0.0)
    for source_key, metric_key in (
        ("mean_faithfulness_score", "llm_judge_mean_faithfulness_score"),
        ("mean_answer_relevancy_score", "llm_judge_mean_answer_relevancy_score"),
        ("mean_groundedness_score", "llm_judge_mean_groundedness_score"),
        ("mean_completeness_score", "llm_judge_mean_completeness_score"),
        ("mean_uncertainty_honesty_score", "llm_judge_mean_uncertainty_honesty_score"),
        ("mean_executive_usefulness_score", "llm_judge_mean_executive_usefulness_score"),
    ):
        dashboard.metrics[metric_key] = float(summary.get(source_key, 0.0) or 0.0)


def _evaluate_status(dashboard: Dashboard) -> None:
    metrics = dashboard.metrics
    fail_rules = [
        ("validation_errors", "validation_errors > 0"),
        ("sources_failed", "sources_failed > 0"),
        ("expired_sources", "expired_sources > 0"),
    ]
    for key, reason in fail_rules:
        if int(metrics[key] or 0) > 0:
            dashboard.failures.append(reason)

    if metrics["rag_eval_passed"] is False:
        dashboard.failures.append("RAG eval failed.")
    if metrics["golden_eval_passed"] is False:
        dashboard.failures.append("Golden eval failed.")
    if metrics["answer_quality_passed"] is False:
        dashboard.failures.append("Answer quality eval failed.")
    if metrics["answer_quality_status"] == STATUS_WARN:
        dashboard.warnings.append("answer_quality_eval_junit.xml not found.")

    warn_rules = [
        ("stale_sources", "stale_sources > 0"),
        ("missing_context_count", "missing_context_count > 0"),
        ("missing_evidence_count", "missing_evidence_count > 0"),
    ]
    for key, reason in warn_rules:
        if int(metrics[key] or 0) > 0:
            dashboard.warnings.append(reason)

    if dashboard.failures:
        dashboard.status = STATUS_FAIL
    elif dashboard.warnings:
        dashboard.status = STATUS_WARN
    else:
        dashboard.status = STATUS_PASS


def _resolve_reports_dir(reports_dir: Path | None) -> Path | None:
    if reports_dir is not None:
        candidate = reports_dir if reports_dir.is_absolute() else PROJECT_ROOT / reports_dir
        return candidate if candidate.is_dir() else None
    if not DEFAULT_MAINTENANCE_ROOT.is_dir():
        return None
    candidates = [p for p in DEFAULT_MAINTENANCE_ROOT.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _find_report(
    reports_dir: Path | None,
    names: list[str],
    *,
    fallback_glob: Path,
) -> Path | None:
    if reports_dir:
        for name in names:
            candidate = reports_dir / name
            if candidate.is_file():
                return candidate
    candidates = [p for p in fallback_glob.parent.glob(fallback_glob.name) if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _load_json_input(dashboard: Dashboard, name: str, path: Path | None) -> dict[str, Any] | None:
    if path is None:
        dashboard.inputs.append(DashboardInput(name, None, "missing"))
        dashboard.warnings.append(f"{name} report not found.")
        return None
    dashboard.inputs.append(DashboardInput(name, str(path), "found"))
    data = _load_json_file(path)
    if data is None:
        dashboard.warnings.append(f"Could not parse {name} report: {path}")
    return data


def _load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _parse_junit(path: Path) -> dict[str, Any] | None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None

    testcases = list(root.iter("testcase"))
    tests_total = _junit_int_attr(root, "tests", len(testcases))
    failures = _junit_int_attr(root, "failures", 0)
    errors = _junit_int_attr(root, "errors", 0)
    skipped = _junit_int_attr(root, "skipped", 0)
    failures_are_aggregated = _junit_has_attr(root, "failures")
    errors_are_aggregated = _junit_has_attr(root, "errors")
    skipped_is_aggregated = _junit_has_attr(root, "skipped")
    failed_cases: list[str] = []
    failure_details: list[str] = []
    missing_context_count = 0
    missing_evidence_count = 0
    unsupported_claim_count = 0
    required_sections_missing = 0
    citation_coverage = 0.0
    for case in testcases:
        failure_nodes = list(case.findall("failure"))
        error_nodes = list(case.findall("error"))
        skipped_nodes = list(case.findall("skipped"))
        if skipped_nodes and not skipped_is_aggregated:
            skipped += len(skipped_nodes)
        if failure_nodes or error_nodes:
            if not failures_are_aggregated:
                failures += len(failure_nodes)
            if not errors_are_aggregated:
                errors += len(error_nodes)
            classname = case.attrib.get("classname", "")
            name = case.attrib.get("name", "unknown")
            case_name = f"{classname}.{name}".strip(".")
            failed_cases.append(case_name)
            node_text = "\n".join(_junit_node_text(node) for node in [*failure_nodes, *error_nodes])
            failure_details.extend(_summarize_junit_failure(case_name, node_text))
            missing_context_count = max(
                missing_context_count,
                _sum_regex_counts(node_text, r"missing_context_count=(\d+)"),
            )
            missing_evidence_count = max(
                missing_evidence_count,
                _sum_regex_counts(node_text, r"missing_evidence_count=(\d+)"),
            )
            unsupported_claim_count = max(
                unsupported_claim_count,
                _sum_regex_counts(node_text, r"unsupported_claim_count=(\d+)"),
            )
            required_sections_missing = max(
                required_sections_missing,
                _sum_regex_counts(node_text, r"required_sections_missing=(\d+)"),
            )
            citation_coverage = max(
                citation_coverage,
                _max_regex_float(node_text, r"citation_coverage=([0-9.]+)"),
            )

    return {
        "tests": tests_total,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "failed_cases": failed_cases,
        "failure_details": failure_details,
        "missing_context_count": missing_context_count,
        "missing_evidence_count": missing_evidence_count,
        "unsupported_claim_count": unsupported_claim_count,
        "required_sections_missing": required_sections_missing,
        "citation_coverage": round(citation_coverage, 4),
    }


def _extract_markdown_counter(text: str, key: str) -> int:
    pattern = re.compile(rf"{re.escape(key)}:\s*`?(\d+)`?", re.IGNORECASE)
    match = pattern.search(text)
    return int(match.group(1)) if match else 0


def _junit_node_text(node: ET.Element) -> str:
    return "\n".join(part for part in [node.attrib.get("message", ""), node.text or ""] if part)


def _junit_int_attr(root: ET.Element, attr: str, default: int) -> int:
    if attr in root.attrib:
        return int(root.attrib.get(attr, "0") or 0)
    if root.tag == "testsuites":
        total = 0
        found = False
        for suite in root.findall("testsuite"):
            if attr in suite.attrib:
                found = True
                total += int(suite.attrib.get(attr, "0") or 0)
        if found:
            return total
    return default


def _junit_has_attr(root: ET.Element, attr: str) -> bool:
    if attr in root.attrib:
        return True
    if root.tag == "testsuites":
        return any(attr in suite.attrib for suite in root.findall("testsuite"))
    return False


def _sum_regex_counts(text: str, pattern: str) -> int:
    return sum(int(match) for match in re.findall(pattern, text))


def _max_regex_float(text: str, pattern: str) -> float:
    values = [float(match) for match in re.findall(pattern, text)]
    return max(values) if values else 0.0


def _summarize_junit_failure(case_name: str, text: str) -> list[str]:
    details: list[str] = []
    patterns = [
        r"failed cases: \[(.*?)\]",
        r"failed gates: \[(.*?)\]",
        r"unsupported_claim_count=\d+",
        r"required_sections_missing=\d+",
        r"citation_coverage=[0-9.]+",
        r"critical case [^:\n]+:[^\n]+",
        r"case '[^']+': missing_context_count=\d+ [^\n]+",
        r"case [^:\n]+: [^\n]+",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.DOTALL):
            cleaned = " ".join(str(match).split())
            if cleaned:
                details.append(f"`{case_name}`: {cleaned[:500]}")
    if not details and text.strip():
        cleaned = " ".join(text.strip().split())
        details.append(f"`{case_name}`: {cleaned[:500]}")
    return details


def _count_value(value: Any) -> int:
    if value is None or value is False:
        return 0
    if value is True:
        return 1
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return 1 if value else 0
    if isinstance(value, list | tuple | set | dict):
        return len(value)
    return 0


def _format_value(value: int | float | bool | str | None) -> str:
    if value is None:
        return "not run"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _dashboard_to_dict(dashboard: Dashboard) -> dict[str, Any]:
    data = asdict(dashboard)
    data["inputs"] = [asdict(item) for item in dashboard.inputs]
    return data


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

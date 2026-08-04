from __future__ import annotations

from pathlib import Path

import pytest

from src.governance.artifacts import (
    DEFAULT_ROADMAP_PATH,
    build_initial_evidence_pack,
    build_license_inventory,
    build_local_security_scan,
    parse_candidate_catalog_from_roadmap,
    read_csv,
    summarize_candidate_catalog,
)
from src.governance.schemas import CandidateStatus

ROADMAP_EXISTS = DEFAULT_ROADMAP_PATH.is_file()


@pytest.mark.skipif(not ROADMAP_EXISTS, reason="Roadmap file not found")
def test_parse_candidate_catalog_from_final_roadmap() -> None:
    entries = parse_candidate_catalog_from_roadmap()
    names = {entry.name for entry in entries}
    assert len(entries) > 100
    assert "FastAPI" in names
    assert "Qdrant" in names
    assert "TOON" in names
    assert "Repository Purpose Manifest" in names
    by_name = {entry.name: entry for entry in entries}
    assert by_name["FastAPI"].status == CandidateStatus.BENCHMARK_CONFIGURED
    assert by_name["Firecrawl"].status == CandidateStatus.FUTURE_RESEARCH
    assert by_name["Repository Purpose Manifest"].status == CandidateStatus.BENCHMARK_CONFIGURED


@pytest.mark.skipif(not ROADMAP_EXISTS, reason="Roadmap file not found")
def test_candidate_status_summary_counts_statuses() -> None:
    entries = parse_candidate_catalog_from_roadmap()
    summary = summarize_candidate_catalog(entries)
    by_status = summary["by_status"]
    assert summary["total_candidates"] == len(entries)
    assert by_status["BENCHMARK_CONFIGURED"] > 0
    assert by_status["FUTURE_RESEARCH"] > 0
    assert summary["runtime_relevant_count"] >= 9


@pytest.mark.skipif(not ROADMAP_EXISTS, reason="Roadmap file not found")
def test_build_initial_evidence_pack_writes_required_artifacts(tmp_path: Path) -> None:
    outputs = build_initial_evidence_pack(evidence_dir=tmp_path)
    required = {
        "candidate_catalog",
        "repository_purpose_manifest",
        "runtime_bill_of_materials",
        "decision_ledger",
        "calibration_registry",
        "benchmark_manifest",
        "benchmark_report",
        "candidate_status_summary",
        "data_lineage_report",
        "evidence_to_decision_coverage",
        "license_inventory",
        "security_scan_report",
        "implemented_family_best_tool_report",
        "implemented_family_best_tool_report_md",
        "direct_alternative_gap_benchmark_report",
        "direct_alternative_gap_benchmark_report_md",
        "value_family_completeness_report",
        "value_family_completeness_report_md",
        "roadmap_closure_audit_report",
        "roadmap_closure_audit_report_md",
    }
    assert required.issubset(outputs)
    for key in required:
        assert outputs[key].is_file()

    rows = read_csv(outputs["candidate_catalog"])
    assert len(rows) > 100
    statuses = {row["status"] for row in rows}
    assert "BENCHMARK_CONFIGURED" in statuses
    assert "FUTURE_RESEARCH" in statuses


def test_license_inventory_and_security_scan_are_structured() -> None:
    license_inventory = build_license_inventory()
    assert license_inventory["python_dependency_count"] > 0
    assert license_inventory["frontend_dependency_count"] > 0

    security_scan = build_local_security_scan()
    assert security_scan["status"] in {"PASS", "FAIL"}
    assert "finding_count" in security_scan

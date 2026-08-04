from __future__ import annotations

import json
from pathlib import Path

from scripts.check_implemented_family_best_tool import FAMILY_AUDITS, build_report


def _write_promoted_spike_reports(evidence_dir: Path) -> None:
    for spec in FAMILY_AUDITS:
        (evidence_dir / spec.product_spike_report).write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "decision": "PROMOTE_TO_PRODUCT_SPIKE",
                    "quality_delta": 0.25,
                    "regression_count": 0,
                    "case_count": 2,
                }
            ),
            encoding="utf-8",
        )


def test_best_tool_audit_passes_but_does_not_claim_global_best(tmp_path: Path) -> None:
    _write_promoted_spike_reports(tmp_path)
    (tmp_path / "candidate_catalog.csv").write_text("candidate_id,name,category,status\n", encoding="utf-8")
    (tmp_path / "external_free_verification_report.json").write_text('{"items": []}', encoding="utf-8")
    (tmp_path / "free_external_candidate_benchmark_report.json").write_text('{"probes": []}', encoding="utf-8")

    report = build_report(tmp_path)

    assert report["status"] == "PASS"
    assert report["family_count"] == len(FAMILY_AUDITS)
    assert report["current_best_with_evidence_count"] == len(FAMILY_AUDITS)
    assert report["global_best_guarantee"] is False


def test_best_tool_audit_flags_untested_free_alternative(tmp_path: Path) -> None:
    _write_promoted_spike_reports(tmp_path)
    (tmp_path / "candidate_catalog.csv").write_text(
        "candidate_id,name,category,status\n" "neo4j,Neo4j,8.11 GraphRAG and Knowledge Graph,FUTURE_RESEARCH\n",
        encoding="utf-8",
    )
    (tmp_path / "external_free_verification_report.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "name": "Neo4j",
                        "categories": ["8.11 GraphRAG and Knowledge Graph"],
                        "ranking_eligible": True,
                        "verification_status": "FREE_EXTERNAL_BENCHMARKABLE",
                        "official_source_url": "https://neo4j.com/",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "free_external_candidate_benchmark_report.json").write_text('{"probes": []}', encoding="utf-8")

    report = build_report(tmp_path)
    graph_family = next(item for item in report["families"] if item["family_id"] == "graphrag_evidence_graph")

    assert report["status"] == "PASS"
    assert graph_family["status"] == "BEST_WITH_CURRENT_EVIDENCE_NEEDS_DIRECT_ALTERNATIVE_BENCHMARK"
    assert graph_family["untested_free_alternative_count"] == 1

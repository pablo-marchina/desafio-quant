from __future__ import annotations

import json
from pathlib import Path

from scripts.check_implemented_family_best_tool import build_report as build_best_tool_report
from scripts.run_direct_alternative_gap_benchmarks import build_report


def test_direct_alternative_gap_benchmarks_resolve_covered_and_no_lift_items(tmp_path: Path) -> None:
    (tmp_path / "implemented_family_best_tool_report.json").write_text(
        json.dumps(
            {
                "families": [
                    {
                        "family_id": "query_rewriting_multiquery",
                        "display_name": "Query rewriting",
                        "quality_delta": 0.425,
                        "catalog_alternatives_needing_direct_benchmark": [
                            {"name": "query rewriting", "category": "8.5"},
                            {"name": "HyDE", "category": "8.5"},
                        ],
                    },
                    {
                        "family_id": "graphrag_evidence_graph",
                        "display_name": "GraphRAG",
                        "quality_delta": 0.8,
                        "candidate_score": 1.0,
                        "catalog_alternatives_needing_direct_benchmark": [
                            {"name": "Neo4j", "category": "8.4"},
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path)
    by_name = {item["candidate_name"]: item for item in report["results"]}

    assert report["total_alternatives"] == 3
    assert report["resolved_alternative_count"] == 3
    assert report["remaining_direct_gap_count"] == 0
    assert by_name["query rewriting"]["outcome"] == "CURRENT_IMPLEMENTATION_COVERS_TECHNIQUE"
    assert by_name["HyDE"]["outcome"] == "DIRECT_BENCHMARK_NO_LIFT"
    assert by_name["Neo4j"]["outcome"] == "DIRECT_IMPLEMENTATION_NO_LIFT"


def test_best_tool_audit_consumes_resolved_direct_gap_report(tmp_path: Path) -> None:
    (tmp_path / "query_rewriting_product_spike_report.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "decision": "PROMOTE_TO_PRODUCT_SPIKE",
                "quality_delta": 0.425,
                "regression_count": 0,
                "case_count": 2,
            }
        ),
        encoding="utf-8",
    )
    for report_name in [
        "next_action_enrichment_product_spike_report.json",
        "graphrag_evidence_graph_product_spike_report.json",
        "counter_evidence_product_spike_report.json",
        "source_quality_product_spike_report.json",
        "evidence_sufficiency_product_spike_report.json",
    ]:
        (tmp_path / report_name).write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "decision": "PROMOTE_TO_PRODUCT_SPIKE",
                    "quality_delta": 0.2,
                    "regression_count": 0,
                    "case_count": 1,
                }
            ),
            encoding="utf-8",
        )
    (tmp_path / "candidate_catalog.csv").write_text(
        "candidate_id,name,category,status,benchmark,hypothesis\n"
        "query,query rewriting,8.5 RAG/retrieval techniques,BENCHMARKED,scripts/run_benchmark.py,\n"
        "hyde,HyDE,8.5 RAG/retrieval techniques,BENCHMARKED,scripts/run_benchmark.py,\n",
        encoding="utf-8",
    )
    (tmp_path / "external_free_verification_report.json").write_text('{"items": []}', encoding="utf-8")
    (tmp_path / "free_external_candidate_benchmark_report.json").write_text('{"probes": []}', encoding="utf-8")
    (tmp_path / "direct_alternative_gap_benchmark_report.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "family_id": "query_rewriting_multiquery",
                        "candidate_name": "query rewriting",
                        "resolved_gap": True,
                        "outcome": "CURRENT_IMPLEMENTATION_COVERS_TECHNIQUE",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = build_best_tool_report(tmp_path)
    query_family = next(item for item in report["families"] if item["family_id"] == "query_rewriting_multiquery")

    assert query_family["direct_alternative_gap_count"] == 1
    assert query_family["catalog_alternatives_needing_direct_benchmark"][0]["name"] == "HyDE"

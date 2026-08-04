from __future__ import annotations

import json
from pathlib import Path

from scripts.check_value_family_completeness import build_report


def test_value_family_completeness_is_false_when_direct_gaps_exist(tmp_path: Path) -> None:
    (tmp_path / "candidate_catalog.csv").write_text(
        "candidate_id,name,category,status\n"
        "a,query rewriting,8.5 RAG/retrieval techniques,BENCHMARKED\n"
        "b,observability,8.14 Observability, LLMOps and experiment tracking,BENCHMARKED\n",
        encoding="utf-8",
    )
    (tmp_path / "diagnostic_value_triage_report.json").write_text(
        json.dumps(
            {
                "case_count": 1,
                "family_decisions": [
                    {
                        "family_id": "query_rewriting_multiquery",
                        "display_name": "Query rewriting",
                        "quality_delta": 0.2,
                        "matching_candidates": [{"name": "query rewriting"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "implemented_family_best_tool_report.json").write_text(
        json.dumps(
            {
                "families": [
                    {
                        "family_id": "query_rewriting_multiquery",
                        "display_name": "Query rewriting",
                        "quality_delta": 0.4,
                        "direct_alternative_gap_count": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "output_value_benchmark_report.json").write_text(
        json.dumps({"by_category": {}, "decisions": []}),
        encoding="utf-8",
    )

    report = build_report(tmp_path)

    assert report["status"] == "PASS"
    assert report["exhaustive_value_family_discovery"] is False
    assert report["global_no_more_value_guarantee"] is False
    assert report["direct_alternative_gap_total"] == 1
    assert report["categories_without_direct_quality_lift_count"] == 2


def test_value_family_completeness_flags_diagnostic_signal_not_implemented(tmp_path: Path) -> None:
    (tmp_path / "candidate_catalog.csv").write_text(
        "candidate_id,name,category,status\n"
        "a,cost-aware routing,8.10 Recommendation, ranking and scoring,BENCHMARKED\n",
        encoding="utf-8",
    )
    (tmp_path / "diagnostic_value_triage_report.json").write_text(
        json.dumps(
            {
                "case_count": 1,
                "family_decisions": [
                    {
                        "family_id": "cost_latency_reliability_controls",
                        "display_name": "Cost, latency, reliability controls",
                        "quality_delta": 0.1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "implemented_family_best_tool_report.json").write_text(
        json.dumps({"families": []}),
        encoding="utf-8",
    )
    (tmp_path / "output_value_benchmark_report.json").write_text(
        json.dumps({"by_category": {}, "decisions": []}),
        encoding="utf-8",
    )

    report = build_report(tmp_path)

    assert report["diagnostic_signal_not_implemented_count"] == 1
    assert report["families"][0]["status"] == "DIAGNOSTIC_SIGNAL_NOT_IMPLEMENTED"

from __future__ import annotations

import json
from pathlib import Path

from scripts.check_external_free_verification import build_verification_report
from scripts.review_free_external_candidates import build_review_report, write_markdown_report


def test_free_external_review_marks_only_eligible_matched_candidates(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    catalog = tmp_path / "candidate_catalog.csv"
    registry.write_text(
        json.dumps(
            {
                "policy_ref": "docs/final_benchmark_first_policy.md",
                "entries": [
                    {
                        "name": "Free Tool",
                        "status": "FREE_EXTERNAL_BENCHMARKABLE",
                        "benchmark_path": "direct no-cost benchmark",
                    },
                    {
                        "name": "Needs Verification",
                        "status": "NEEDS_FREE_TIER_VERIFICATION",
                        "benchmark_path": "verify free tier first",
                    },
                    {
                        "name": "Free API",
                        "status": "FREE_API_BENCHMARKABLE",
                        "benchmark_path": "direct no-cost API benchmark",
                    },
                    {
                        "name": "Missing From Catalog",
                        "status": "FREE_EXTERNAL_BENCHMARKABLE",
                        "benchmark_path": "direct no-cost benchmark",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    catalog.write_text(
        "candidate_id,name,category,status\n"
        "free,Free Tool,8.1,FUTURE_RESEARCH\n"
        "needs,Needs Verification,8.1,FUTURE_RESEARCH\n"
        "api,Free API,8.1,FUTURE_RESEARCH\n",
        encoding="utf-8",
    )

    report = build_review_report(registry, catalog)

    assert report["status"] == "PASS"
    assert report["summary"]["registry_count"] == 4
    assert report["summary"]["matched_catalog_count"] == 3
    assert report["summary"]["ranking_eligible_count"] == 2
    assert report["summary"]["needs_verification_count"] == 1
    assert report["ranking_eligible_names"] == ["Free API", "Free Tool"]
    missing = next(item for item in report["items"] if item["name"] == "Missing From Catalog")
    assert missing["ranking_eligible"] is False


def test_free_external_review_writes_markdown_summary(tmp_path: Path) -> None:
    path = tmp_path / "review.md"
    report = {
        "status": "PASS",
        "summary": {
            "registry_count": 1,
            "matched_catalog_count": 1,
            "ranking_eligible_count": 1,
            "needs_verification_count": 0,
            "not_in_catalog_count": 0,
        },
        "items": [
            {
                "name": "Free Tool",
                "status": "FREE_EXTERNAL_BENCHMARKABLE",
                "catalog_match": True,
                "ranking_eligible": True,
                "benchmark_path": "direct benchmark",
            }
        ],
    }

    write_markdown_report(path, report)

    text = path.read_text(encoding="utf-8")
    assert "Free External Candidate Review" in text
    assert "Free Tool" in text
    assert "Ranking eligible: 1" in text


def test_external_free_verification_requires_all_future_research_names(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    catalog = tmp_path / "candidate_catalog.csv"
    registry.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "name": "Free Tool",
                        "status": "FREE_EXTERNAL_BENCHMARKABLE",
                        "official_source_url": "https://example.com/free-tool",
                        "benchmark_path": "benchmark",
                        "free_tier_evidence": "source verified",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    catalog.write_text(
        "candidate_id,name,category,status\n"
        "free,Free Tool,8.1,FUTURE_RESEARCH\n"
        "missing,Missing Tool,8.1,FUTURE_RESEARCH\n"
        "local,Local Tool,8.1,BENCHMARKED\n",
        encoding="utf-8",
    )

    report = build_verification_report(registry, catalog)

    assert report["status"] == "FAIL"
    assert report["summary"]["external_unique_count"] == 2
    assert report["summary"]["missing_registry_count"] == 1
    assert report["summary"]["ranking_eligible_count"] == 1


def test_external_free_verification_derives_registry_from_governed_catalog(tmp_path: Path) -> None:
    registry = tmp_path / "missing_registry.json"
    catalog = tmp_path / "candidate_catalog.csv"
    catalog.write_text(
        "candidate_id,name,category,status,required_configuration,benchmark,free_self_hosted_verification,"
        "source_or_reference,cost_policy\n"
        "local,Local Substitute,8.1,FUTURE_RESEARCH,free self-hosted only,benchmark,PASS_BY_FREE_ONLY_FILTER,"
        "https://example.com/source,FREE_ONLY_OR_SELF_HOSTED\n",
        encoding="utf-8",
    )

    report = build_verification_report(registry, catalog)

    assert report["status"] == "PASS"
    assert report["summary"]["external_unique_count"] == 1
    assert report["summary"]["ranking_eligible_count"] == 1
    assert report["items"][0]["official_source_url"] == "https://example.com/source"

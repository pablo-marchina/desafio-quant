from __future__ import annotations

import json
from pathlib import Path

from scripts import run_benchmark
from src.evaluation.dataset_registry import BenchmarkDataset
from src.evaluation.result_store import BenchmarkResult
from src.governance.artifacts import summarize_candidate_catalog
from src.governance.schemas import BenchmarkCandidateEntry, CandidateStatus


def _dataset(tmp_path: Path) -> BenchmarkDataset:
    return BenchmarkDataset(
        dataset_id="unit-catalog",
        name="Unit catalog",
        version="v1",
        path=str(tmp_path / "candidate_catalog.csv"),
        task_type="catalog",
        source_policy_ref="unit",
    )


def test_complete_catalog_uses_future_research_for_external_candidate(tmp_path: Path) -> None:
    row = {
        "candidate_id": "external",
        "name": "OpenAI Evals",
        "category": "8.13 Evaluation frameworks and judges",
        "status": "FUTURE_RESEARCH",
        "required_configuration": "external SaaS",
        "substitute_candidate": "",
        "substitute_reason": "",
    }

    payload = run_benchmark._task_for_row(row, complete_catalog=True)(_dataset(tmp_path))

    assert payload["status"] == "future_research"
    assert payload["metadata"]["promotion_allowed"] is False
    assert payload["metadata"]["benchmark_scope"] == "blocked_external_dependency"


def test_complete_catalog_current_product_benchmark_blocks_runtime_promotion(tmp_path: Path) -> None:
    row = {
        "candidate_id": "proxy",
        "name": "skeptical RAG",
        "category": "8.5 RAG/retrieval techniques",
        "status": "DOCUMENTED_CANDIDATE",
    }

    payload = run_benchmark._task_for_row(row, complete_catalog=True)(_dataset(tmp_path))

    assert payload["status"] == "passed"
    assert payload["metadata"]["benchmark_scope"] == "direct_current_product_quality_adoption"
    assert payload["metadata"]["promotion_allowed"] is False
    assert payload["metadata"]["output_value_measured"] is True
    assert payload["metadata"]["output_quality_measured"] is True
    assert payload["metadata"]["quality_lift"]["quality_delta"] == 0.0


def test_complete_catalog_benchmarked_rows_keep_current_product_benchmark(tmp_path: Path) -> None:
    row = {
        "candidate_id": "proxy",
        "name": "skeptical RAG",
        "category": "8.5 RAG/retrieval techniques",
        "status": "BENCHMARKED",
        "substitute_reason": "This candidate was evaluated through category evidence.",
    }

    payload = run_benchmark._task_for_row(row, complete_catalog=True)(_dataset(tmp_path))

    assert payload["status"] == "passed"
    assert payload["metadata"]["benchmark_scope"] == "direct_current_product_quality_adoption"


def test_complete_catalog_reports_cover_debt_and_coverage(tmp_path: Path) -> None:
    rows = [
        {"candidate_id": "direct", "name": "FastAPI", "category": "8.1 Runtime core"},
        {"candidate_id": "external", "name": "OpenAI Evals", "category": "8.13 Evaluation frameworks and judges"},
    ]
    results = [
        BenchmarkResult(
            run_id="r1",
            candidate_id="direct",
            candidate_name="FastAPI",
            dataset_id="unit",
            status="passed",
            metadata={"benchmark_scope": "direct"},
        ),
        BenchmarkResult(
            run_id="r2",
            candidate_id="external",
            candidate_name="OpenAI Evals",
            dataset_id="unit",
            status="future_research",
            metadata={"benchmark_scope": "blocked_external_dependency", "substitute_reason": "requires SaaS"},
        ),
    ]

    run_benchmark._write_complete_catalog_reports(tmp_path, rows, results)

    coverage = json.loads((tmp_path / "benchmark_coverage_report.json").read_text(encoding="utf-8"))
    debt = json.loads((tmp_path / "benchmark_debt_report.json").read_text(encoding="utf-8"))
    output_value = json.loads((tmp_path / "output_value_benchmark_report.json").read_text(encoding="utf-8"))
    recommendations = json.loads((tmp_path / "candidate_promotion_recommendations.json").read_text(encoding="utf-8"))
    assert coverage["total_candidates"] == 2
    assert coverage["total_results"] == 2
    assert coverage["coverage_ratio"] == 1.0
    assert coverage["direct_benchmarks"] == 1
    assert coverage["blocked_or_future_research"] == 1
    assert debt["total_debt_items"] == 1
    assert output_value["total_decisions"] == 2
    assert output_value["by_decision"]["KEEP_REQUIRED_RUNTIME"] == 1
    assert output_value["by_decision"]["FUTURE_RESEARCH"] == 1
    assert recommendations["summary"]["keep_required_runtime_count"] == 1
    assert (tmp_path / "all_candidate_benchmark_documentation.md").is_file()


def test_category_proxy_substitute_reason_is_not_external_dependency() -> None:
    entries = [
        BenchmarkCandidateEntry(
            candidate_id="proxy",
            name="skeptical RAG",
            category="8.5 RAG/retrieval techniques",
            status=CandidateStatus.BENCHMARK_CONFIGURED,
            benchmark="scripts/run_benchmark.py",
            substitute_candidate="category_proxy_benchmark",
            substitute_reason="This candidate was evaluated through category evidence.",
        ),
        BenchmarkCandidateEntry(
            candidate_id="external",
            name="OpenAI Evals",
            category="8.13 Evaluation frameworks and judges",
            status=CandidateStatus.FUTURE_RESEARCH,
            benchmark="blocked_until_service_or_license_available",
            required_configuration="external credentials, service access, license, or hardware",
        ),
    ]

    summary = summarize_candidate_catalog(entries)

    assert summary["external_dependency_count"] == 1


def test_output_value_decision_keeps_baseline_for_current_product_benchmark() -> None:
    row = {
        "candidate_id": "proxy",
        "name": "skeptical RAG",
        "category": "8.5 RAG/retrieval techniques",
        "status": "BENCHMARK_CONFIGURED",
    }
    result = BenchmarkResult(
        run_id="r1",
        candidate_id="proxy",
        candidate_name="skeptical RAG",
        dataset_id="unit",
        status="passed",
        metadata={
            "benchmark_scope": "direct_current_product_quality_adoption",
            "output_value_measured": True,
            "output_quality_measured": True,
            "quality_lift": {
                "baseline_quality_score": 1.0,
                "candidate_quality_score": 1.0,
                "quality_delta": 0.0,
                "improved_quality": False,
            },
        },
    )

    decision = run_benchmark._output_value_decision(row, result)

    assert decision["decision"] == "KEEP_BASELINE"
    assert decision["promotion_allowed"] is False
    assert decision["quality_lift_measured"] is True


def test_output_value_decision_keeps_baseline_when_quality_does_not_improve() -> None:
    row = {
        "candidate_id": "hybrid",
        "name": "Hybrid retrieval",
        "category": "8.5 RAG/retrieval techniques",
        "status": "BENCHMARKED",
    }
    result = BenchmarkResult(
        run_id="r1",
        candidate_id="hybrid",
        candidate_name="Hybrid retrieval",
        dataset_id="unit",
        status="passed",
        metadata={
            "benchmark_scope": "direct_output_value",
            "output_quality_measured": True,
            "quality_lift": {
                "baseline_quality_score": 1.0,
                "candidate_quality_score": 0.8,
                "quality_delta": -0.2,
                "improved_quality": False,
            },
        },
    )

    decision = run_benchmark._output_value_decision(row, result)

    assert decision["decision"] == "KEEP_BASELINE"
    assert decision["promotion_allowed"] is False
    assert decision["quality_lift_measured"] is True

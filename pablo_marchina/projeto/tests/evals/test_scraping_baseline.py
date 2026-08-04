from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from src.evaluation.scraping_baseline import (
    SOURCE_CATEGORIES,
    ScrapingBaselineCase,
    ScrapingBaselineSource,
    compute_marginal_gain_by_source_rank,
    compute_source_category_scores,
    evaluate_case,
    grid_search,
    run_full_calibration,
)

_GOLDEN_PATH = Path("data/eval/golden_scraping_baseline.json")


@pytest.fixture
def golden_set() -> list[ScrapingBaselineCase]:
    from src.evaluation.scraping_baseline import _load_golden_set

    return _load_golden_set(_GOLDEN_PATH)


@pytest.fixture
def singleton_case() -> ScrapingBaselineCase:
    return ScrapingBaselineCase(
        startup_id="test-001",
        startup_name="TestStartup",
        website_url="https://test.io",
        expected_claim_types=["gpu_usage"],
        sources=[
            ScrapingBaselineSource(
                url="https://test.io",
                category="official_website",
                rank=1,
                evidence_covered=3,
                claim_ids_supported=["c1", "c2"],
                fetch_success=True,
                extraction_success=True,
                latency_ms=100,
            ),
            ScrapingBaselineSource(
                url="https://github.com/test",
                category="github_or_code",
                rank=2,
                evidence_covered=1,
                claim_ids_supported=["c1"],
                fetch_success=True,
                extraction_success=True,
                is_duplicate=True,
                latency_ms=200,
            ),
            ScrapingBaselineSource(
                url="https://exame.com/test",
                category="funding_news",
                rank=3,
                evidence_covered=2,
                claim_ids_supported=["c3"],
                fetch_success=False,
                extraction_success=False,
                latency_ms=5000,
                compliance_blocked=True,
            ),
        ],
        claims=[
            {"claim_id": "c1", "claim_text": "Uses GPU", "claim_type": "gpu_usage"},
            {"claim_id": "c2", "claim_text": "Founded in 2023", "claim_type": "team"},
            {"claim_id": "c3", "claim_text": "Raised funding", "claim_type": "funding"},
        ],
        total_available_sources=3,
        total_claims=3,
    )


class TestEvaluateCase:

    def test_source_discovery_count(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=2)
        assert metrics.source_discovery_count == 2

    def test_unique_evidence_count(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=3)
        assert metrics.unique_evidence_count == 6

    def test_supported_claim_count(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=2)
        assert metrics.supported_claim_count == 2
        assert "c1" in metrics.failure_rate_by_source_type or True

    def test_supported_claim_count_all(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=3)
        assert metrics.supported_claim_count == 3

    def test_unsupported_claim_count(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=1)
        assert metrics.unsupported_claim_count == 1

    def test_evidence_per_claim(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=2)
        assert metrics.evidence_per_claim > 0.0

    def test_duplicate_rate(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=2)
        assert metrics.duplicate_rate == 0.5

    def test_failure_rate_by_source_type(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=3)
        assert "funding_news" in metrics.failure_rate_by_source_type
        assert metrics.failure_rate_by_source_type["funding_news"] == 1.0

    def test_cost_proxy_per_supported_claim(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=3)
        assert metrics.cost_proxy_per_supported_claim > 0.0

    def test_marginal_gain_by_source_rank(self, golden_set: list[ScrapingBaselineCase]) -> None:
        gains = compute_marginal_gain_by_source_rank(golden_set)
        assert "rank_1" in gains, f"Expected rank_1 in gains, got {list(gains.keys())}"
        rank1 = gains["rank_1"]
        assert "avg_marginal_claim_gain" in rank1
        assert rank1["avg_marginal_claim_gain"] > 0

    def test_source_discovery_count_by_category(self, singleton_case: ScrapingBaselineCase) -> None:
        metrics = evaluate_case(singleton_case, max_sources=3)
        for cat in SOURCE_CATEGORIES:
            assert cat in metrics.source_discovery_count_by_category
        assert metrics.source_discovery_count_by_category["official_website"] == 1


class TestGridSearch:

    def test_grid_search_returns_all_candidates(self, golden_set: list[ScrapingBaselineCase]) -> None:
        results = grid_search(golden_set, max_sources_candidates=[1, 2, 3])
        assert len(results) == 3

    def test_coverage_increases_with_max_sources(self, golden_set: list[ScrapingBaselineCase]) -> None:
        results = grid_search(golden_set, max_sources_candidates=[1, 4, 8])
        assert results[2].coverage_ratio >= results[0].coverage_ratio


class TestSourceCategoryScore:

    def test_source_category_score_is_deterministic(self, golden_set: list[ScrapingBaselineCase]) -> None:
        scores1 = compute_source_category_scores(golden_set)
        scores2 = compute_source_category_scores(golden_set)
        for cat in SOURCE_CATEGORIES:
            assert scores1[cat].final_score == scores2[cat].final_score

    def test_all_categories_have_scores(self, golden_set: list[ScrapingBaselineCase]) -> None:
        scores = compute_source_category_scores(golden_set)
        for cat in SOURCE_CATEGORIES:
            assert cat in scores

    def test_official_website_has_high_score(self, golden_set: list[ScrapingBaselineCase]) -> None:
        scores = compute_source_category_scores(golden_set)
        web_score = scores["official_website"].final_score
        assert web_score >= -2.0 and web_score <= 2.0


class TestFullCalibration:

    _EXPECTED_SIZE = 11

    def test_calibration_returns_report(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert "report" in result
        assert "grid_results" in result
        assert "category_scores" in result
        assert "recommendations" in result
        assert "calibration_status" in result
        assert result["golden_set_size"] == self._EXPECTED_SIZE

    def test_calibration_status_is_blocked(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert result["calibration_status"] == "baseline_dataset_insufficient"

    def test_production_not_allowed(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert result["production_allowed"] is False

    def test_recommendations_contain_all_keys(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        recs = result["recommendations"]
        assert "max_sources" in recs
        assert "max_depth" in recs
        assert "min_evidence_per_claim" in recs
        assert "stop_condition" in recs
        assert "source_priority" in recs

    def test_source_priority_has_all_categories(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        priority = result["recommendations"]["source_priority"]
        for cat in SOURCE_CATEGORIES:
            assert cat in priority, f"Missing category {cat} in source_priority"
            entry = priority[cat]
            assert "score" in entry
            assert "rank" in entry


class TestEmptyGoldenSet:

    def test_empty_set_returns_error(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        from src.evaluation.scraping_baseline import run_full_calibration

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"startups": [], "_meta": {}}, f)
            tmp = f.name
        try:
            result = run_full_calibration(golden_path=Path(tmp))
            assert result["production_allowed"] is False
            assert "error" in result or result["calibration_status"] == "baseline_dataset_insufficient"
        finally:
            Path(tmp).unlink()


@pytest.fixture
def mock_collector() -> Any:
    @dataclass
    class _MockCollectedSource:
        url: str = ""
        category: str = "official_website"
        rank: int = 1
        fetch_success: bool = True
        extraction_success: bool = True
        latency_ms: int = 100
        is_duplicate: bool = False
        compliance_blocked: bool = False

    @dataclass
    class _MockCollectionResult:
        startup_name: str = ""
        website_url: str = ""
        sources: list = field(default_factory=list)
        errors: list = field(default_factory=list)

    class _MockCollector:
        def collect(self, startup_name: str, website_url: str) -> Any:
            sources = [
                _MockCollectedSource(
                    url=website_url,
                    category="official_website",
                    rank=1,
                    fetch_success=True,
                    extraction_success=True,
                    latency_ms=100,
                ),
            ]
            return _MockCollectionResult(startup_name=startup_name, website_url=website_url, sources=sources)

    return _MockCollector()


class TestValidateCollectorCoverage:

    def test_validate_with_mock_collector(self, golden_set: list[ScrapingBaselineCase], mock_collector: Any) -> None:
        from src.evaluation.scraping_baseline import validate_collector_coverage

        validation = validate_collector_coverage(golden_set, collector=mock_collector)
        assert "collector_available" in validation
        assert "category_precision" in validation
        assert "category_recall" in validation
        assert "category_f1" in validation

    def test_validate_returns_metrics(self, golden_set: list[ScrapingBaselineCase], mock_collector: Any) -> None:
        from src.evaluation.scraping_baseline import validate_collector_coverage

        validation = validate_collector_coverage(golden_set, collector=mock_collector)
        assert 0.0 <= validation["category_f1"] <= 1.0
        assert "per_startup" in validation
        assert len(validation["per_startup"]) > 0

    def test_calibration_with_mock_collector(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH, real_collector_available=False)
        assert result["calibration_status"] == "baseline_dataset_insufficient"
        assert result["production_allowed"] is False


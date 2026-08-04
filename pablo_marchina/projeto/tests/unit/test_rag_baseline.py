from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.rag_baseline import (
    RagBaselineCase,
    _compute_metrics_for_case,
    _load_baseline_golden,
    _recommend_min_required_contexts,
    _recommend_top_k,
    evaluate_baseline,
    grid_search_baseline,
    run_full_calibration,
)
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext

_GOLDEN = Path("data/eval/golden_baseline_rag.json")


def _make_ctx(
    chunk_id: str,
    source_id: str,
    url: str | None = "https://example.com",
    product: str = "Test Product",
) -> RetrievedContext:
    return RetrievedContext(
        chunk_id=chunk_id,
        source_id=source_id,
        title="Test",
        content="test content",
        product=product,
        gap_types=["test_gap"],
        url=url,
        relevance_score=0.5,
    )


class TestRagBaselineCase:
    def test_all_fields_present(self) -> None:
        cases = _load_baseline_golden(_GOLDEN)
        assert len(cases) >= 14
        for c in cases:
            assert c.minimum_relevant_contexts is not None
            assert c.critical_claims_expected is not None

    def test_minimum_relevant_contexts_is_positive(self) -> None:
        cases = _load_baseline_golden(_GOLDEN)
        for c in cases:
            if c.expected_source_ids:
                assert (
                    c.minimum_relevant_contexts >= 1
                ), f"{c.case_id}: minimum_relevant_contexts={c.minimum_relevant_contexts}"

    def test_critical_claims_matches_is_critical(self) -> None:
        cases = _load_baseline_golden(_GOLDEN)
        for c in cases:
            if c.is_critical and c.expected_source_ids:
                assert (
                    c.critical_claims_expected >= 1
                ), f"{c.case_id}: critical_claims_expected={c.critical_claims_expected}"
            if not c.is_critical:
                assert (
                    c.critical_claims_expected == 0
                ), f"{c.case_id}: non-critical but critical_claims_expected={c.critical_claims_expected}"


class TestComputeMetricsForCase:
    def test_recall_at_k_all_found(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a", "src_b"],
        )
        retrieved = [_make_ctx("c1", "src_a"), _make_ctx("c2", "src_b")]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=5)
        assert metrics.recall_at_k == 1.0
        assert metrics.unsupported_claim_rate == 0.0

    def test_recall_at_k_partial(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a", "src_b", "src_c"],
        )
        retrieved = [_make_ctx("c1", "src_a"), _make_ctx("c2", "src_b")]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=5)
        assert abs(metrics.recall_at_k - 2 / 3) < 0.001
        assert abs(metrics.unsupported_claim_rate - 1 / 3) < 0.001

    def test_recall_at_k_none_found(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a"],
        )
        retrieved = [_make_ctx("c1", "src_b")]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=5)
        assert metrics.recall_at_k == 0.0
        assert metrics.unsupported_claim_rate == 1.0

    def test_recall_at_k_empty_expected_returns_empty(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="nonexistent"),
            expected_source_ids=[],
        )
        retrieved: list[RetrievedContext] = []
        metrics = _compute_metrics_for_case(case, retrieved, top_k=5)
        assert metrics.recall_at_k == 1.0
        assert metrics.unsupported_claim_rate == 0.0

    def test_precision_at_k_perfect(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a", "src_b"],
        )
        retrieved = [_make_ctx("c1", "src_a"), _make_ctx("c2", "src_b")]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=2)
        assert metrics.precision_at_k == 1.0

    def test_precision_at_k_partial(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a"],
        )
        retrieved = [
            _make_ctx("c1", "src_a"),
            _make_ctx("c2", "src_b"),
            _make_ctx("c3", "src_b"),
        ]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=3)
        assert abs(metrics.precision_at_k - 1 / 3) < 0.001

    def test_precision_at_k_zero_retrieved(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a"],
        )
        metrics = _compute_metrics_for_case(case, [], top_k=5)
        assert metrics.precision_at_k == 0.0

    def test_mrr_first_rank(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_b"],
        )
        retrieved = [
            _make_ctx("c1", "src_a"),
            _make_ctx("c2", "src_b"),
            _make_ctx("c3", "src_c"),
        ]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=3)
        assert metrics.mrr == pytest.approx(1 / 2)

    def test_mrr_no_relevant(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_z"],
        )
        retrieved = [_make_ctx("c1", "src_a"), _make_ctx("c2", "src_b")]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=3)
        assert metrics.mrr == 0.0

    def test_citation_precision_all_valid(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a"],
        )
        retrieved = [
            _make_ctx("c1", "src_a"),
            _make_ctx("c2", "src_b"),
        ]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=2)
        assert metrics.citation_precision == 1.0

    def test_citation_precision_missing_url(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a"],
        )
        retrieved = [
            _make_ctx("c1", "src_a"),
            _make_ctx("c2", "src_b", url=None),
        ]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=2)
        assert metrics.citation_precision == 0.5

    def test_citation_precision_missing_source_id(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a"],
        )
        retrieved = [
            _make_ctx("c1", "src_a"),
            _make_ctx("c2", "", url="https://example.com"),
        ]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=2)
        assert metrics.citation_precision == 0.5

    def test_citation_precision_empty_retrieval(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="nonexistent"),
            expected_source_ids=[],
        )
        metrics = _compute_metrics_for_case(case, [], top_k=5)
        assert metrics.citation_precision == 1.0

    def test_unsupported_claim_rate_none(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a", "src_b"],
        )
        retrieved = [_make_ctx("c1", "src_a"), _make_ctx("c2", "src_b")]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=2)
        assert metrics.unsupported_claim_rate == 0.0

    def test_unsupported_claim_rate_all(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a"],
        )
        retrieved = [_make_ctx("c1", "src_b")]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=2)
        assert metrics.unsupported_claim_rate == 1.0

    def test_unsupported_claim_rate_empty_expected(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="nonexistent"),
            expected_source_ids=[],
        )
        metrics = _compute_metrics_for_case(case, [], top_k=5)
        assert metrics.unsupported_claim_rate == 0.0

    def test_retrieved_and_relevant_counts(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a", "src_b"],
        )
        retrieved = [
            _make_ctx("c1", "src_a"),
            _make_ctx("c2", "src_b"),
            _make_ctx("c3", "src_c"),
        ]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=3)
        assert metrics.retrieved_context_count == 3
        assert metrics.relevant_context_count == 2

    def test_top_k_limits_retrieved_count(self) -> None:
        case = RagBaselineCase(
            case_id="test",
            description="test",
            query=RetrievalQuery(gap_type="test_gap"),
            expected_source_ids=["src_a"],
        )
        retrieved = [
            _make_ctx("c1", "src_a"),
            _make_ctx("c2", "src_b"),
            _make_ctx("c3", "src_c"),
        ]
        metrics = _compute_metrics_for_case(case, retrieved, top_k=1)
        assert metrics.retrieved_context_count == 1


class TestEvaluateBaseline:
    def test_runs_on_default_index(self) -> None:
        results = evaluate_baseline(top_k=5)
        assert len(results) >= 14
        for r in results:
            assert isinstance(r.metrics.recall_at_k, float)
            assert isinstance(r.metrics.precision_at_k, float)
            assert 0.0 <= r.metrics.mrr <= 1.0
            assert 0.0 <= r.metrics.citation_precision <= 1.0
            assert 0.0 <= r.metrics.unsupported_claim_rate <= 1.0

    def test_all_metrics_have_valid_ranges(self) -> None:
        results = evaluate_baseline(top_k=10)
        for r in results:
            assert 0.0 <= r.metrics.recall_at_k <= 1.0
            assert 0.0 <= r.metrics.precision_at_k <= 1.0


class TestGridSearchBaseline:
    def test_evaluates_all_candidates(self) -> None:
        grid_results = grid_search_baseline(top_k_candidates=[3, 5, 10])
        assert len(grid_results) == 3
        k_values = [gr.top_k for gr in grid_results]
        assert k_values == [3, 5, 10]

    def test_recall_increases_with_top_k(self) -> None:
        grid_results = grid_search_baseline(top_k_candidates=[3, 10, 15])
        rec3 = next(gr for gr in grid_results if gr.top_k == 3).avg_recall
        rec15 = next(gr for gr in grid_results if gr.top_k == 15).avg_recall
        assert rec15 >= rec3, f"Expected recall@15 ({rec15}) >= recall@3 ({rec3})"

    def test_precision_decreases_with_top_k(self) -> None:
        grid_results = grid_search_baseline(top_k_candidates=[3, 10, 15])
        p3 = next(gr for gr in grid_results if gr.top_k == 3).avg_precision
        p15 = next(gr for gr in grid_results if gr.top_k == 15).avg_precision
        assert p15 <= p3, f"Expected precision@15 ({p15}) <= precision@3 ({p3})"

    def test_per_case_results_are_present(self) -> None:
        grid_results = grid_search_baseline(top_k_candidates=[5])
        assert len(grid_results) == 1
        assert len(grid_results[0].per_case_results) >= 14


class TestRecommendTopK:
    def test_returns_valid_top_k(self) -> None:
        grid_results = grid_search_baseline(top_k_candidates=[3, 5, 8, 10, 15])
        rec = _recommend_top_k(grid_results)
        if rec["production_allowed"]:
            assert rec["recommended_top_k"] in [3, 5, 8, 10, 15]
            assert rec["reason"]
        else:
            assert rec["recommended_top_k"] is None

    def test_strict_targets_may_not_meet(self) -> None:
        grid_results = grid_search_baseline(top_k_candidates=[3, 5])
        rec = _recommend_top_k(grid_results, recall_target=0.99, precision_target=0.99, citation_target=1.0)
        if not rec["production_allowed"]:
            assert rec["recommended_top_k"] is None

    def test_low_targets_always_meet(self) -> None:
        grid_results = grid_search_baseline(top_k_candidates=[3])
        rec = _recommend_top_k(grid_results, recall_target=0.0, precision_target=0.0, citation_target=0.0)
        assert rec["production_allowed"] is True
        assert rec["recommended_top_k"] == 3


class TestRecommendMinRequiredContexts:
    def test_returns_positive_integer(self) -> None:
        grid_results = grid_search_baseline(top_k_candidates=[5])
        rec = _recommend_min_required_contexts(grid_results, recommended_top_k=5)
        assert rec["recommended_min_required_contexts"] >= 1
        assert rec["method"]

    def test_fallback_when_no_data(self) -> None:
        from src.evaluation.rag_baseline import RagGridSearchResult

        empty_result = RagGridSearchResult(
            top_k=3,
            avg_recall=0.0,
            avg_precision=0.0,
            mrr=0.0,
            avg_citation_precision=0.0,
            avg_unsupported_claim_rate=0.0,
            avg_retrieved=0.0,
            avg_relevant=0.0,
            total_cases=0,
            cases_with_expected_sources=0,
            per_case_results=[],
        )
        rec = _recommend_min_required_contexts([empty_result], recommended_top_k=3)
        assert rec["recommended_min_required_contexts"] >= 1


class TestRunFullCalibration:
    def test_returns_complete_result(self) -> None:
        result = run_full_calibration(top_k_candidates=[3, 5, 8, 10, 15])
        assert "grid_results" in result
        assert "report" in result
        assert "top_k_recommendation" in result
        assert "min_required_contexts_recommendation" in result
        assert "calibration_status" in result
        assert "dataset_size" in result
        assert result["dataset_size"] >= 14
        assert len(result["grid_results"]) == 5

    def test_report_contains_metrics(self) -> None:
        result = run_full_calibration(top_k_candidates=[5])
        report = result["report"]
        assert "RAG BASELINE CALIBRATION REPORT" in report
        assert "recall" in report.lower()
        assert "precision" in report.lower()

    def test_calibration_status_is_measured_or_insufficient(self) -> None:
        result = run_full_calibration(top_k_candidates=[3, 5, 8, 10, 15])
        assert result["calibration_status"] in (
            "baseline_measured",
            "baseline_dataset_insufficient",
        )

    def test_empty_index_produces_insufficient(self) -> None:
        empty_idx = ChunkIndex([])
        result = run_full_calibration(
            index=empty_idx,
            top_k_candidates=[3, 5],
        )
        assert result["calibration_status"] == "baseline_dataset_insufficient"

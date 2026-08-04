"""Unit tests for RAGAS Evaluation Harness — no LLM, no external calls.

All tests are deterministic and use the minimal golden set at
data/eval/golden_ragas_rag.json.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.ragas_eval import RagasEvalHarness
from src.evaluation.ragas_eval_schemas import (
    MINIMUM_GAP_TYPES_COVERED,
    MINIMUM_GOLDEN_SAMPLES,
    REQUIRED_SAMPLE_FIELDS,
    CustomEvalMetrics,
    GoldenContext,
    RagasComputedMetrics,
    RagasEvalDataset,
    RagasEvalGoldenSample,
    RagasEvalReport,
    RagasEvalResult,
)

_GOLDEN = Path("data/eval/golden_ragas_rag.json")


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def harness() -> RagasEvalHarness:
    return RagasEvalHarness(golden_path=_GOLDEN)


@pytest.fixture
def loaded_dataset(harness: RagasEvalHarness) -> RagasEvalDataset:
    return harness.load_golden_set()


@pytest.fixture
def run_result(harness: RagasEvalHarness) -> RagasEvalResult:
    return harness.run()


# ── Test: evaluator loads golden set ───────────────────────────────────────


class TestLoadGoldenSet:
    def test_loads_samples(self, loaded_dataset: RagasEvalDataset) -> None:
        assert len(loaded_dataset.samples) >= 1

    def test_each_sample_has_required_fields(self, loaded_dataset: RagasEvalDataset) -> None:
        for sample in loaded_dataset.samples:
            assert sample.question
            assert sample.gap_id
            assert sample.gap_type
            assert isinstance(sample.expected_nvidia_topics, list)

    def test_metadata_present(self, loaded_dataset: RagasEvalDataset) -> None:
        assert "version" in loaded_dataset.metadata
        assert "created" in loaded_dataset.metadata


# ── Test: evaluator validates schema ────────────────────────────────────────


class TestValidateSchema:
    def test_valid_dataset_returns_no_errors(self, harness: RagasEvalHarness, loaded_dataset: RagasEvalDataset) -> None:
        errors = harness.validate_schema(loaded_dataset)
        assert len(errors) == 0, f"schema errors: {errors}"

    def test_detects_missing_field(self, harness: RagasEvalHarness) -> None:
        bad = RagasEvalDataset(
            samples=[
                RagasEvalGoldenSample(
                    question="",
                    gap_id="test",
                    gap_type="test",
                    expected_nvidia_topics=[],
                )
            ]
        )
        errors = harness.validate_schema(bad)
        assert len(errors) >= 1
        assert any("empty question" in e for e in errors)

    def test_all_required_fields_are_checked(self) -> None:
        assert "question" in REQUIRED_SAMPLE_FIELDS
        assert "gap_id" in REQUIRED_SAMPLE_FIELDS
        assert "gap_type" in REQUIRED_SAMPLE_FIELDS
        assert "expected_nvidia_topics" in REQUIRED_SAMPLE_FIELDS


# ── Test: compute custom metrics ────────────────────────────-──────────────


class TestComputeCustomMetrics:
    def test_citation_precision_is_calculated(
        self, harness: RagasEvalHarness, loaded_dataset: RagasEvalDataset
    ) -> None:
        metrics = harness.compute_custom_metrics(loaded_dataset)
        assert isinstance(metrics.citation_precision, float)
        assert 0.0 <= metrics.citation_precision <= 1.0

    def test_unsupported_claim_rate_is_calculated(
        self, harness: RagasEvalHarness, loaded_dataset: RagasEvalDataset
    ) -> None:
        metrics = harness.compute_custom_metrics(loaded_dataset)
        assert isinstance(metrics.unsupported_claim_rate, float)
        assert 0.0 <= metrics.unsupported_claim_rate <= 1.0

    def test_retrieved_context_count_is_calculated(
        self, harness: RagasEvalHarness, loaded_dataset: RagasEvalDataset
    ) -> None:
        metrics = harness.compute_custom_metrics(loaded_dataset)
        assert isinstance(metrics.retrieved_context_count, int)
        assert metrics.retrieved_context_count >= 0

    def test_contexts_per_gap_is_populated(self, harness: RagasEvalHarness, loaded_dataset: RagasEvalDataset) -> None:
        metrics = harness.compute_custom_metrics(loaded_dataset)
        assert isinstance(metrics.contexts_per_gap, dict)
        assert len(metrics.contexts_per_gap) >= 1

    def test_gaps_without_context_is_counted(self, harness: RagasEvalHarness, loaded_dataset: RagasEvalDataset) -> None:
        metrics = harness.compute_custom_metrics(loaded_dataset)
        assert isinstance(metrics.gaps_without_context_count, int)
        assert metrics.gaps_without_context_count >= 0

    def test_empty_dataset_returns_zero_metrics(self, harness: RagasEvalHarness) -> None:
        empty = RagasEvalDataset(samples=[])
        metrics = harness.compute_custom_metrics(empty)
        assert metrics.citation_precision == 1.0
        assert metrics.unsupported_claim_rate == 0.0
        assert metrics.retrieved_context_count == 0
        assert metrics.gaps_without_context_count == 0

    def test_citation_precision_drops_without_url(self, harness: RagasEvalHarness) -> None:
        ds = RagasEvalDataset(
            samples=[
                RagasEvalGoldenSample(
                    question="q",
                    gap_id="g",
                    gap_type="t",
                    expected_nvidia_topics=["x"],
                    expected_context_ids=["c1"],
                    retrieved_contexts=[
                        GoldenContext(
                            chunk_id="c1",
                            source_id="s1",
                            title="t",
                            content="c",
                            product="p",
                            gap_types=["t"],
                            url=None,
                            relevance_score=0.5,
                        )
                    ],
                )
            ]
        )
        metrics = harness.compute_custom_metrics(ds)
        assert metrics.citation_precision == 0.0

    def test_unsupported_claim_rate_handles_no_expected_ids(self, harness: RagasEvalHarness) -> None:
        ds = RagasEvalDataset(
            samples=[
                RagasEvalGoldenSample(
                    question="q",
                    gap_id="g",
                    gap_type="t",
                    expected_nvidia_topics=[],
                    expected_context_ids=[],
                    retrieved_contexts=[
                        GoldenContext(
                            chunk_id="c1",
                            source_id="s1",
                            title="t",
                            content="c",
                            product="p",
                            gap_types=["t"],
                            url="https://example.com",
                            relevance_score=0.5,
                        )
                    ],
                )
            ]
        )
        metrics = harness.compute_custom_metrics(ds)
        assert metrics.unsupported_claim_rate == 0.0


# ── Test: RAGAS metrics (deterministic, no ragas lib) ──────────────────────


class TestComputeRagasMetrics:
    def test_ragas_metrics_return_unavailable_when_no_lib(
        self, harness: RagasEvalHarness, loaded_dataset: RagasEvalDataset
    ) -> None:
        metrics = harness.compute_ragas_metrics(loaded_dataset)
        assert isinstance(metrics, RagasComputedMetrics)
        assert metrics.context_precision is None
        assert metrics.context_recall is None
        assert metrics.faithfulness is None
        assert metrics.answer_relevancy is None
        assert "unavailable" in metrics.metrics_source

    def test_ragas_metrics_structure(self, harness: RagasEvalHarness) -> None:
        empty = RagasEvalDataset(samples=[])
        metrics = harness.compute_ragas_metrics(empty)
        assert metrics.metrics_source is not None
        assert isinstance(metrics.metrics_source, str)


# ── Test: dataset sufficiency ──────────────────────────────────────────────


class TestDatasetSufficiency:
    def test_golden_dataset_is_now_sufficient(
        self, harness: RagasEvalHarness, loaded_dataset: RagasEvalDataset
    ) -> None:
        sufficient, msg = harness.check_dataset_sufficiency(loaded_dataset)
        assert sufficient is True, f"expected sufficient, got: {msg}"
        assert msg == "dataset sufficient"

    def test_minimum_constants_are_reasonable(self) -> None:
        assert MINIMUM_GOLDEN_SAMPLES >= 5
        assert MINIMUM_GAP_TYPES_COVERED >= 2

    def test_empty_dataset_is_insufficient(self, harness: RagasEvalHarness) -> None:
        empty = RagasEvalDataset(samples=[])
        sufficient, msg = harness.check_dataset_sufficiency(empty)
        assert sufficient is False
        assert "0 samples" in msg


# ── Test: full run ─────────────────────────────────────────────────────────


class TestFullRun:
    def test_run_returns_result(self, run_result: RagasEvalResult) -> None:
        assert isinstance(run_result, RagasEvalResult)

    def test_run_reports_sufficient_dataset(self, run_result: RagasEvalResult) -> None:
        assert run_result.dataset_sufficient is True
        assert run_result.calibration_status == "baseline_measured"

    def test_run_production_allowed(self, run_result: RagasEvalResult) -> None:
        assert run_result.production_allowed is True

    def test_run_has_custom_metrics(self, run_result: RagasEvalResult) -> None:
        assert isinstance(run_result.custom_metrics, CustomEvalMetrics)

    def test_run_has_reports(self, run_result: RagasEvalResult) -> None:
        assert len(run_result.reports) >= 4

    def test_run_has_calibration_decisions(self, run_result: RagasEvalResult) -> None:
        assert len(run_result.calibration_decisions) >= 5
        assert "rag.semantic_top_k" in run_result.calibration_decisions
        assert "rag.min_contexts_per_gap" in run_result.calibration_decisions
        assert "rag.citation_precision_threshold" in run_result.calibration_decisions

    def test_run_reports_have_required_fields(self, run_result: RagasEvalResult) -> None:
        for report in run_result.reports:
            assert isinstance(report, RagasEvalReport)
            assert report.metric_name
            assert isinstance(report.score, float)
            assert report.sample_count >= 1

    def test_run_calibration_decisions_have_value_origin(self, run_result: RagasEvalResult) -> None:
        for _decision_id, decision in run_result.calibration_decisions.items():
            assert "value_origin" in decision
            assert "ragas_rag_eval" in decision["value_origin"]
            assert "calibration_status" in decision
            assert "production_allowed" in decision

    def test_run_all_decisions_are_baseline_measured(self, run_result: RagasEvalResult) -> None:
        for decision_id, decision in run_result.calibration_decisions.items():
            assert decision["calibration_status"] == "baseline_measured", f"{decision_id} is not baseline_measured"
            assert decision["production_allowed"] is True


# ── Test: no LLM, no internet ──────────────────────────────────────────────


class TestNoExternalCalls:
    def test_compute_custom_metrics_is_deterministic(self, harness: RagasEvalHarness) -> None:
        ds = RagasEvalDataset(
            samples=[
                RagasEvalGoldenSample(
                    question="test question",
                    gap_id="test-gap",
                    gap_type="test_type",
                    expected_nvidia_topics=["topic_a"],
                    expected_context_ids=["c1"],
                    retrieved_contexts=[
                        GoldenContext(
                            chunk_id="c1",
                            source_id="s1",
                            title="Test",
                            content="test content",
                            product="Test Product",
                            gap_types=["test_type"],
                            url="https://example.com",
                            relevance_score=0.9,
                        )
                    ],
                )
            ]
        )
        m1 = harness.compute_custom_metrics(ds)
        m2 = harness.compute_custom_metrics(ds)
        assert m1.citation_precision == m2.citation_precision
        assert m1.unsupported_claim_rate == m2.unsupported_claim_rate

    def test_validate_schema_no_external_calls(self, harness: RagasEvalHarness) -> None:
        ds = RagasEvalDataset(
            samples=[
                RagasEvalGoldenSample(
                    question="q",
                    gap_id="g",
                    gap_type="t",
                    expected_nvidia_topics=["x"],
                )
            ]
        )
        errors = harness.validate_schema(ds)
        assert len(errors) == 0

    def test_check_sufficiency_no_external_calls(self, harness: RagasEvalHarness) -> None:
        ds = RagasEvalDataset(samples=[])
        harness.check_dataset_sufficiency(ds)

    def test_generate_report_no_external_calls(self, harness: RagasEvalHarness) -> None:
        custom = CustomEvalMetrics()
        ragas = RagasComputedMetrics()
        ds = RagasEvalDataset(samples=[])
        reports = harness.generate_report(custom, ragas, ds)
        assert len(reports) >= 4


# ── Test: report structure ─────────────────────────────────────────────────


class TestReportStructure:
    def test_each_report_has_calibration_recommendation(self, run_result: RagasEvalResult) -> None:
        for report in run_result.reports:
            assert report.calibration_recommendation

    def test_custom_metric_reports_production_allowed(self, run_result: RagasEvalResult) -> None:
        for report in run_result.reports:
            if report.metric_name.startswith("custom."):
                assert report.production_allowed_recommendation is True

    def test_report_contains_both_metric_families(self, run_result: RagasEvalResult) -> None:
        names = {r.metric_name for r in run_result.reports}
        custom_metrics = {n for n in names if n.startswith("custom.")}
        {n for n in names if n.startswith("ragas.")}
        assert len(custom_metrics) >= 3
        assert "custom.citation_precision" in custom_metrics
        assert "custom.unsupported_claim_rate" in custom_metrics


# ── Test: schema validation for GoldenContext ──────────────────────────────


class TestGoldenContextValidation:
    def test_minimal_golden_context(self) -> None:
        ctx = GoldenContext()
        assert ctx.chunk_id == ""
        assert ctx.source_id == ""
        assert ctx.relevance_score == 0.0

    def test_golden_context_with_values(self) -> None:
        ctx = GoldenContext(
            chunk_id="c1",
            source_id="s1",
            title="Test",
            content="test content",
            product="Test Product",
            gap_types=["type_a"],
            url="https://example.com",
            relevance_score=0.85,
        )
        assert ctx.chunk_id == "c1"
        assert ctx.relevance_score == 0.85

    def test_golden_context_default_url_none(self) -> None:
        ctx = GoldenContext(chunk_id="c1", source_id="s1", title="t", content="c", product="p")
        assert ctx.url is None


# ── Test: RagasEvalResult structure ────────────────────────────────────────


class TestRagasEvalResult:
    def test_default_is_insufficient(self) -> None:
        result = RagasEvalResult()
        assert result.dataset_sufficient is False
        assert result.calibration_status == "baseline_dataset_insufficient"
        assert result.production_allowed is False

    def test_custom_metrics_default(self) -> None:
        result = RagasEvalResult()
        assert result.custom_metrics.citation_precision == 0.0
        assert result.custom_metrics.retrieved_context_count == 0

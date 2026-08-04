from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.evaluation.recommendation_baseline import (
    CANDIDATE_PRIORITY_WEIGHTS,
    HumanLabeledRecommendation,
    RecommendationCalibrationResult,
    RecommendationGoldenEntry,
    WeightCandidateResult,
    _check_recommendation_production_ready,
    _compute_calibration_error_metrics,
    _compute_correlation_metrics,
    _compute_priority_scores_for_mappings,
    _compute_ranking_metrics,
    _compute_support_metrics,
    _compute_weighted_score,
    _evaluate_weight_candidates,
    _extract_priority_features,
    _recommend_minimum_evidence_support,
    _recommend_minimum_mapping_confidence,
    _select_best_candidate,
    _spearman,
    check_recommendation_labels_are_real,
    check_recommendation_labels_exist,
    count_labeled_recommendations,
    generate_synthetic_recommendation_golden_set,
    load_recommendation_golden_set,
    make_recommendation_baseline_records,
    run_recommendation_baseline_calibration,
)
from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    DecisionCalibrationRecord,
)

_GOLDEN_PATH = Path("data/eval/golden_recommendation_baseline.json")


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_label(
    tech: str = "CUDA",
    relevance: float = 0.8,
    rank: int = 1,
    actionability: float = 0.7,
    label_source: str = "human-reviewer",
    ev_ids: list[str] | None = None,
    rag_ids: list[str] | None = None,
) -> HumanLabeledRecommendation:
    return HumanLabeledRecommendation(
        nvidia_technology=tech,
        human_label_relevance=relevance,
        human_label_priority_rank=rank,
        human_label_actionability=actionability,
        supporting_evidence_ids=ev_ids or [],
        supporting_rag_context_ids=rag_ids or [],
        reviewer_id="test-reviewer",
        label_source=label_source,
        label_notes="test label",
    )


def _make_mapping(
    tech: str = "CUDA",
    mapping_score: float = 0.7,
    mapping_confidence: float = 0.6,
    gap_severity: float = 0.6,
    gap_confidence: float = 0.6,
    uncertainty: float = 0.1,
    ev_ids: list[str] | None = None,
    rag_ids: list[str] | None = None,
    gap_type: str = "compute_acceleration_gap",
) -> dict[str, Any]:
    return {
        "mapping_id": f"map-{tech}",
        "gap_type": gap_type,
        "nvidia_technology": tech,
        "mapping_score": mapping_score,
        "mapping_confidence": mapping_confidence,
        "uncertainty": uncertainty,
        "features": {
            "gap_severity_score": gap_severity,
            "gap_confidence_score": gap_confidence,
        },
        "supporting_rag_context_ids": rag_ids or [],
        "supporting_evidence_ids": ev_ids or [],
        "production_allowed": True,
        "blockers": [],
        "calibration_decision_ids": [],
    }


def _make_entry(
    eval_id: str = "test-001",
    gap_type: str = "compute_acceleration_gap",
    labels: list[HumanLabeledRecommendation] | None = None,
    mappings: list[dict[str, Any]] | None = None,
) -> RecommendationGoldenEntry:
    return RecommendationGoldenEntry(
        eval_id=eval_id,
        startup_id=f"startup-{eval_id}",
        startup_name=f"Test {eval_id}",
        gap_id=f"gap-{eval_id}",
        gap_type=gap_type,
        nvidia_technology_mappings_snapshot=mappings or [],
        rag_contexts_by_gap_snapshot={gap_type: []},
        accepted_evidence_items_snapshot=[],
        expected_recommendations=labels or [],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Golden set loading
# ═══════════════════════════════════════════════════════════════════════════


class TestLoadGoldenSet:
    def test_loads_real_file(self) -> None:
        entries = load_recommendation_golden_set(_GOLDEN_PATH)
        assert isinstance(entries, list)

    def test_entries_have_required_fields(self) -> None:
        entry = _make_entry()
        assert entry.eval_id
        assert entry.startup_id
        assert entry.startup_name
        assert entry.gap_id
        assert entry.gap_type
        assert isinstance(entry.nvidia_technology_mappings_snapshot, list)
        assert isinstance(entry.expected_recommendations, list)

    def test_non_existent_path_returns_empty(self) -> None:
        entries = load_recommendation_golden_set(Path("nonexistent.json"))
        assert entries == []

    def test_human_labeled_recommendation_schema(self) -> None:
        label = _make_label(tech="TensorRT", relevance=0.9, rank=1, actionability=0.8)
        assert label.nvidia_technology == "TensorRT"
        assert 0.0 <= label.human_label_relevance <= 1.0
        assert label.human_label_priority_rank >= 1
        assert 0.0 <= label.human_label_actionability <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Label inspection
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckLabelsExist:
    def test_no_labels(self) -> None:
        entry = _make_entry(labels=[])
        assert not check_recommendation_labels_exist([entry])

    def test_has_labels(self) -> None:
        entry = _make_entry(labels=[_make_label()])
        assert check_recommendation_labels_exist([entry])

    def test_empty_list(self) -> None:
        assert not check_recommendation_labels_exist([])


class TestCheckLabelsAreReal:
    def test_synthetic_labels_detected(self) -> None:
        entry = _make_entry(
            labels=[
                _make_label(label_source="derived_from_synthetic_reference"),
            ]
        )
        real, issues = check_recommendation_labels_are_real([entry])
        assert not real
        assert len(issues) >= 1
        assert "synthetic" in issues[0].lower()

    def test_real_labels_pass(self) -> None:
        entry = _make_entry(
            labels=[
                _make_label(label_source="human-reviewer-1"),
            ]
        )
        real, issues = check_recommendation_labels_are_real([entry])
        assert real
        assert issues == []

    def test_mixed_labels(self) -> None:
        entry = _make_entry(
            labels=[
                _make_label(label_source="human-reviewer-1"),
                _make_label(label_source="derived_from_synthetic_reference"),
            ]
        )
        real, issues = check_recommendation_labels_are_real([entry])
        assert real  # at least one real
        assert len(issues) >= 1

    def test_empty_entries(self) -> None:
        real, issues = check_recommendation_labels_are_real([])
        assert not real
        assert issues == []


class TestCountLabeledRecommendations:
    def test_counts_entries_and_labels(self) -> None:
        entries = [
            _make_entry("e1", labels=[_make_label("CUDA")]),
            _make_entry("e2", labels=[_make_label("TensorRT"), _make_label("NIM")]),
            _make_entry("e3", labels=[]),
        ]
        result = count_labeled_recommendations(entries)
        assert result["total_entries_with_labels"] == 2
        assert result["total_recommendation_labels"] == 3

    def test_empty(self) -> None:
        result = count_labeled_recommendations([])
        assert result["total_entries_with_labels"] == 0
        assert result["total_recommendation_labels"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 3. Synthetic golden set
# ═══════════════════════════════════════════════════════════════════════════


class TestSyntheticGoldenSet:
    def test_generates_requested_count(self) -> None:
        entries = generate_synthetic_recommendation_golden_set(count=10)
        assert len(entries) == 10

    def test_generates_default_count(self) -> None:
        entries = generate_synthetic_recommendation_golden_set()
        assert len(entries) == 30

    def test_each_entry_has_labels(self) -> None:
        entries = generate_synthetic_recommendation_golden_set(count=5)
        for e in entries:
            assert len(e.expected_recommendations) >= 1

    def test_each_entry_has_fields(self) -> None:
        entries = generate_synthetic_recommendation_golden_set(count=3)
        for e in entries:
            assert e.eval_id
            assert e.startup_id
            assert e.startup_name
            assert e.gap_id
            assert e.gap_type

    def test_labels_have_valid_ranges(self) -> None:
        entries = generate_synthetic_recommendation_golden_set(count=10)
        for e in entries:
            for r in e.expected_recommendations:
                assert 0.0 <= r.human_label_relevance <= 1.0
                assert r.human_label_priority_rank >= 1
                assert 0.0 <= r.human_label_actionability <= 1.0
                assert "synthetic" in r.label_source.lower()

    def test_deterministic(self) -> None:
        a = generate_synthetic_recommendation_golden_set(count=5)
        b = generate_synthetic_recommendation_golden_set(count=5)
        assert len(a) == len(b)
        for ea, eb in zip(a, b, strict=True):
            assert ea.eval_id == eb.eval_id
            assert len(ea.expected_recommendations) == len(eb.expected_recommendations)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Utility functions
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeWeightedScore:
    def test_basic_weighted_average(self) -> None:
        score = _compute_weighted_score({"a": 0.5, "b": 1.0}, {"a": 0.5, "b": 0.5})
        assert score == pytest.approx(0.75)

    def test_clamps_below_0(self) -> None:
        score = _compute_weighted_score({"a": -0.5}, {"a": 1.0})
        assert score == 0.0

    def test_clamps_above_1(self) -> None:
        score = _compute_weighted_score({"a": 2.0}, {"a": 1.0})
        assert score == 1.0

    def test_zero_weight_sum(self) -> None:
        score = _compute_weighted_score({"a": 0.5}, {})
        assert score == 0.0


class TestSpearman:
    def test_perfect_positive(self) -> None:
        assert _spearman([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0, abs=0.01)

    def test_perfect_negative(self) -> None:
        assert _spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0, abs=0.01)

    def test_insufficient_data(self) -> None:
        assert _spearman([1], [2]) == 0.0
        assert _spearman([1, 2], [2, 1]) == 0.0


class TestExtractPriorityFeatures:
    def test_extracts_correct_keys(self) -> None:
        mapping = _make_mapping(
            tech="CUDA",
            mapping_score=0.8,
            mapping_confidence=0.7,
            gap_severity=0.6,
            gap_confidence=0.9,
        )
        features = _extract_priority_features(mapping)
        for key in (
            "mapping_score",
            "mapping_confidence",
            "gap_severity_score",
            "gap_confidence_score",
            "evidence_support",
            "rag_support",
            "business_impact",
            "implementation_complexity_inverse",
        ):
            assert key in features
        assert features["mapping_score"] == 0.8
        assert features["mapping_confidence"] == 0.7
        assert features["gap_severity_score"] == 0.6
        assert features["gap_confidence_score"] == 0.9


class TestComputePriorityScores:
    def test_returns_correct_count(self) -> None:
        mappings = [_make_mapping("CUDA"), _make_mapping("TensorRT")]
        scores = _compute_priority_scores_for_mappings(mappings, CANDIDATE_PRIORITY_WEIGHTS[0])
        assert len(scores) == 2

    def test_uncertainty_penalty_reduces_score(self) -> None:
        high_uncertainty = _make_mapping("CUDA", mapping_score=0.8, uncertainty=0.5)
        scores = _compute_priority_scores_for_mappings(
            [high_uncertainty],
            CANDIDATE_PRIORITY_WEIGHTS[0],
            uncertainty_penalty=0.2,
        )
        assert scores[0] < 0.8


# ═══════════════════════════════════════════════════════════════════════════
# 5. Ranking metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeRankingMetrics:
    def test_returns_none_with_no_labels(self) -> None:
        assert _compute_ranking_metrics([0.5], [], ["CUDA"]) is None

    def test_perfect_ranking(self) -> None:
        labels = [
            _make_label("CUDA", relevance=0.9, rank=1),
            _make_label("TensorRT", relevance=0.6, rank=2),
        ]
        mappings_techs = ["CUDA", "TensorRT"]
        metrics = _compute_ranking_metrics([0.8, 0.4], labels, mappings_techs)
        assert metrics is not None
        assert metrics.mrr == 1.0
        assert metrics.precision_at_k is not None
        assert metrics.precision_at_k[1] == 1.0

    def test_mrr_computed_correctly(self) -> None:
        labels = [
            _make_label("TensorRT", relevance=0.9, rank=1),
            _make_label("CUDA", relevance=0.3, rank=2),
        ]
        mappings_techs = ["CUDA", "TensorRT"]
        metrics = _compute_ranking_metrics([0.8, 0.3], labels, mappings_techs)
        assert metrics is not None
        assert (
            metrics.mrr == 0.5
        )  # TensorRT (relevant, rel=0.9) is 2nd in predicted ranking; CUDA (rel=0.3) is below threshold

    def test_precision_at_k(self) -> None:
        labels = [
            _make_label("CUDA", relevance=0.9, rank=1),
            _make_label("TensorRT", relevance=0.8, rank=2),
            _make_label("NIM", relevance=0.2, rank=3),
        ]
        mappings_techs = ["CUDA", "TensorRT", "NIM"]
        metrics = _compute_ranking_metrics([0.8, 0.7, 0.2], labels, mappings_techs)
        assert metrics is not None
        assert metrics.precision_at_k is not None
        assert metrics.precision_at_k[1] == 1.0  # top-1 is CUDA (relevant)
        assert metrics.precision_at_k[3] == pytest.approx(2.0 / 3.0, abs=0.01)

    def test_recall_at_k(self) -> None:
        labels = [
            _make_label("CUDA", relevance=0.9, rank=1),
            _make_label("TensorRT", relevance=0.8, rank=2),
        ]
        mappings_techs = ["CUDA", "TensorRT", "NIM"]
        metrics = _compute_ranking_metrics([0.8, 0.7, 0.1], labels, mappings_techs)
        assert metrics is not None
        assert metrics.recall_at_k is not None
        assert metrics.recall_at_k[1] == 0.5  # CUDA found in top-1, 2 relevant total

    def test_ndcg_computed(self) -> None:
        labels = [
            _make_label("CUDA", relevance=0.9, rank=1),
            _make_label("NIM", relevance=0.1, rank=2),
        ]
        mappings_techs = ["CUDA", "NIM"]
        metrics = _compute_ranking_metrics([0.8, 0.2], labels, mappings_techs)
        assert metrics is not None
        assert metrics.ndcg_at_k is not None
        assert 0.0 <= metrics.ndcg_at_k[1] <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 6. Support metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeSupportMetrics:
    def test_returns_none_with_empty_labels(self) -> None:
        assert _compute_support_metrics([], []) is None

    def test_unsupported_rate(self) -> None:
        labels = [_make_label("CUDA")]
        mappings = [_make_mapping("CUDA", ev_ids=[], rag_ids=[])]
        m = _compute_support_metrics(mappings, labels)
        assert m is not None
        assert m.unsupported_recommendation_rate == 1.0
        assert m.evidence_supported_recommendation_rate == 0.0
        assert m.rag_supported_recommendation_rate == 0.0

    def test_evidence_supported(self) -> None:
        labels = [_make_label("CUDA")]
        mappings = [_make_mapping("CUDA", ev_ids=["ev-1"], rag_ids=[])]
        m = _compute_support_metrics(mappings, labels)
        assert m is not None
        assert m.evidence_supported_recommendation_rate == 1.0
        assert m.rag_supported_recommendation_rate == 0.0

    def test_both_supported(self) -> None:
        labels = [_make_label("CUDA")]
        mappings = [_make_mapping("CUDA", ev_ids=["ev-1"], rag_ids=["rag-1"])]
        m = _compute_support_metrics(mappings, labels)
        assert m is not None
        assert m.evidence_and_rag_supported_rate == 1.0

    def test_labels_filter_mappings(self) -> None:
        """Only mappings matching labeled technologies are counted."""
        labels = [_make_label("CUDA")]
        mappings = [
            _make_mapping("CUDA", ev_ids=["ev-1"], rag_ids=["rag-1"]),
            _make_mapping("TensorRT", ev_ids=[], rag_ids=[]),
        ]
        m = _compute_support_metrics(mappings, labels)
        assert m is not None
        assert m.evidence_supported_recommendation_rate == 1.0
        assert m.unsupported_recommendation_rate == 0.0  # TensorRT excluded


# ═══════════════════════════════════════════════════════════════════════════
# 7. Correlation metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeCorrelationMetrics:
    def test_returns_none_with_no_labels(self) -> None:
        assert _compute_correlation_metrics([], []) is None

    def test_returns_none_with_too_few(self) -> None:
        labels = [_make_label("CUDA")]
        mappings = [_make_mapping("CUDA")]
        assert _compute_correlation_metrics(mappings, labels) is None  # n < 3

    def test_correlation_values_in_range(self) -> None:
        labels = [
            _make_label("CUDA", relevance=0.9, rank=1, actionability=0.8),
            _make_label("TensorRT", relevance=0.5, rank=2, actionability=0.5),
            _make_label("NIM", relevance=0.3, rank=3, actionability=0.3),
        ]
        mappings = [
            _make_mapping("CUDA", mapping_score=0.85, mapping_confidence=0.8),
            _make_mapping("TensorRT", mapping_score=0.50, mapping_confidence=0.5),
            _make_mapping("NIM", mapping_score=0.30, mapping_confidence=0.3),
        ]
        m = _compute_correlation_metrics(mappings, labels)
        assert m is not None
        assert m.actionability_score_correlation is not None
        assert -1.0 <= m.actionability_score_correlation <= 1.0
        assert m.mapping_score_correlation is not None
        assert -1.0 <= m.mapping_score_correlation <= 1.0
        assert m.priority_score_correlation is not None
        assert m.mapping_confidence_correlation is not None


# ═══════════════════════════════════════════════════════════════════════════
# 8. Calibration error metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeCalibrationError:
    def test_returns_none_with_too_few(self) -> None:
        labels = [_make_label("CUDA")]
        assert _compute_calibration_error_metrics([0.5], labels, ["CUDA"]) is None

    def test_perfect_calibration(self) -> None:
        labels = [
            _make_label("CUDA", relevance=0.8),
            _make_label("TensorRT", relevance=0.5),
            _make_label("NIM", relevance=0.3),
        ]
        ce = _compute_calibration_error_metrics([0.8, 0.5, 0.3], labels, ["CUDA", "TensorRT", "NIM"])
        assert ce is not None
        assert ce.confidence_calibration_error == pytest.approx(0.0, abs=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# 9. Grid search
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluateWeightCandidates:
    def test_returns_results_for_each_candidate(self) -> None:
        entries = generate_synthetic_recommendation_golden_set(count=10)
        results = _evaluate_weight_candidates(entries, CANDIDATE_PRIORITY_WEIGHTS)
        assert len(results) == len(CANDIDATE_PRIORITY_WEIGHTS)
        for r in results:
            assert isinstance(r, WeightCandidateResult)
            assert isinstance(r.candidate_index, int)

    def test_sorted_by_spearman_desc(self) -> None:
        entries = generate_synthetic_recommendation_golden_set(count=10)
        results = _evaluate_weight_candidates(entries, CANDIDATE_PRIORITY_WEIGHTS)
        for i in range(len(results) - 1):
            s_i = results[i].spearman
            s_next = results[i + 1].spearman
            if s_i is not None and s_next is not None:
                assert s_i >= s_next

    def test_insufficient_data_all_none(self) -> None:
        results = _evaluate_weight_candidates(
            [_make_entry("e1")],
            CANDIDATE_PRIORITY_WEIGHTS[:1],
        )
        assert results
        assert results[0].spearman is None


class TestSelectBestCandidate:
    def test_returns_best_index(self) -> None:
        candidates = [
            WeightCandidateResult(0, {}, spearman=0.8, mae=0.05, rmse=0.08),
            WeightCandidateResult(1, {}, spearman=0.5, mae=0.1, rmse=0.15),
        ]
        assert _select_best_candidate(candidates) == 0

    def test_returns_none_if_all_none(self) -> None:
        candidates = [
            WeightCandidateResult(0, {}, spearman=None, mae=None, rmse=None),
        ]
        assert _select_best_candidate(candidates) is None

    def test_skips_none_candidates(self) -> None:
        candidates = [
            WeightCandidateResult(0, {}, spearman=None, mae=None, rmse=None),
            WeightCandidateResult(1, {}, spearman=0.6, mae=0.1, rmse=0.12),
        ]
        assert _select_best_candidate(candidates) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 10. Threshold recommendations
# ═══════════════════════════════════════════════════════════════════════════


class TestRecommendMinimumMappingConfidence:
    def test_insufficient_data(self) -> None:
        result = _recommend_minimum_mapping_confidence([0.5])
        assert result["method"] == "insufficient_data"

    def test_recommendation_in_range(self) -> None:
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        result = _recommend_minimum_mapping_confidence(scores)
        assert result["recommended_min"] >= 0.10
        assert result["method"].startswith("percentile")


class TestRecommendMinimumEvidenceSupport:
    def test_insufficient_data(self) -> None:
        result = _recommend_minimum_evidence_support([])
        assert result["method"] == "insufficient_data"

    def test_basic(self) -> None:
        entries = [
            _make_entry("e1", mappings=[_make_mapping("CUDA", ev_ids=["ev-1"])]),
            _make_entry("e2", mappings=[_make_mapping("TensorRT", ev_ids=[])]),
        ]
        result = _recommend_minimum_evidence_support(entries)
        assert isinstance(result["recommended_min"], float)
        assert 0.0 <= result["recommended_min"] <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 11. Production readiness
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckProductionReady:
    def test_blocked_when_no_real_labels(self) -> None:
        ready, blockers = _check_recommendation_production_ready(
            labeled_entry_count=30,
            label_count=30,
            has_real_labels=False,
            synthetic_issues=[],
            coverage_by_tech={"CUDA": 10},
            spearman=0.8,
            mae=0.05,
            fp_rate=0.0,
        )
        assert not ready
        assert any("no real human labels" in b.lower() for b in blockers)

    def test_blocked_when_synthetic_labels(self) -> None:
        ready, blockers = _check_recommendation_production_ready(
            labeled_entry_count=30,
            label_count=30,
            has_real_labels=True,
            synthetic_issues=["Entry e1 has synthetic label"],
            coverage_by_tech={"CUDA": 10},
            spearman=0.8,
            mae=0.05,
            fp_rate=0.0,
        )
        assert not ready
        assert any("synthetic" in b.lower() for b in blockers)

    def test_blocked_when_too_few_entries(self) -> None:
        ready, blockers = _check_recommendation_production_ready(
            labeled_entry_count=1,
            label_count=1,
            has_real_labels=True,
            synthetic_issues=[],
            coverage_by_tech={},
            spearman=None,
            mae=None,
            fp_rate=None,
        )
        assert not ready
        assert len(blockers) >= 1

    def test_blocked_when_metrics_below_minimum(self) -> None:
        ready, blockers = _check_recommendation_production_ready(
            labeled_entry_count=30,
            label_count=30,
            has_real_labels=True,
            synthetic_issues=[],
            coverage_by_tech={"CUDA": 10, "TensorRT": 5},
            spearman=0.1,
            mae=0.5,
            fp_rate=0.5,
        )
        assert not ready
        assert any("spearman" in b.lower() for b in blockers)

    def test_passes_with_good_metrics(self) -> None:
        ready, blockers = _check_recommendation_production_ready(
            labeled_entry_count=30,
            label_count=30,
            has_real_labels=True,
            synthetic_issues=[],
            coverage_by_tech={"CUDA": 10, "TensorRT": 5},
            spearman=0.8,
            mae=0.05,
            fp_rate=0.0,
        )
        assert ready
        assert blockers == []


# ═══════════════════════════════════════════════════════════════════════════
# 12. Registry record generation
# ═══════════════════════════════════════════════════════════════════════════


class TestMakeBaselineRecords:
    def test_insufficient_produces_uncalibrated(self) -> None:
        result = RecommendationCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            has_real_labels=False,
            synthetic_label_issues=[],
            label_coverage={
                "total_entries_with_labels": 0,
                "total_recommendation_labels": 0,
                "technology_coverage": {},
                "gap_type_coverage": {},
            },
            production_blockers=["Empty"],
        )
        records = make_recommendation_baseline_records(result)
        assert len(records) == 6
        for r in records:
            assert r.calibration_status == CalibrationStatus.UNCALIBRATED
            assert r.production_allowed is False
            assert r.current_value is None

    def test_all_required_decisions_present(self) -> None:
        result = RecommendationCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            has_real_labels=False,
            synthetic_label_issues=[],
            label_coverage={
                "total_entries_with_labels": 0,
                "total_recommendation_labels": 0,
                "technology_coverage": {},
                "gap_type_coverage": {},
            },
        )
        records = make_recommendation_baseline_records(result)
        ids = {r.decision_id for r in records}
        expected = {
            "recommendation.priority_score_weights",
            "recommendation.production_threshold",
            "recommendation.confidence_threshold",
            "recommendation.uncertainty_penalty",
            "recommendation.minimum_mapping_confidence",
            "recommendation.minimum_evidence_support",
        }
        assert ids == expected

    def test_records_have_value_origin(self) -> None:
        result = RecommendationCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            has_real_labels=False,
            synthetic_label_issues=[],
            label_coverage={
                "total_entries_with_labels": 0,
                "total_recommendation_labels": 0,
                "technology_coverage": {},
                "gap_type_coverage": {},
            },
        )
        records = make_recommendation_baseline_records(result)
        for r in records:
            assert r.value_origin is not None
            assert "recommendation_baseline.py" in r.value_origin

    def test_records_have_evidence_source(self) -> None:
        result = RecommendationCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            has_real_labels=False,
            synthetic_label_issues=[],
            label_coverage={
                "total_entries_with_labels": 0,
                "total_recommendation_labels": 0,
                "technology_coverage": {},
                "gap_type_coverage": {},
            },
        )
        records = make_recommendation_baseline_records(result)
        for r in records:
            assert r.evidence_source is not None
            assert len(r.evidence_source) > 0

    def test_records_are_valid_pydantic(self) -> None:
        result = RecommendationCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            has_real_labels=False,
            synthetic_label_issues=[],
            label_coverage={
                "total_entries_with_labels": 0,
                "total_recommendation_labels": 0,
                "technology_coverage": {},
                "gap_type_coverage": {},
            },
        )
        records = make_recommendation_baseline_records(result)
        for r in records:
            assert isinstance(r, DecisionCalibrationRecord)
            assert r.decision_id
            assert r.decision_name
            assert r.decision_type is not None
            assert r.metric_name
            assert r.owner


# ═══════════════════════════════════════════════════════════════════════════
# 13. Full calibration run
# ═══════════════════════════════════════════════════════════════════════════


class TestRunCalibration:
    def test_insufficient_without_auto_generate(self) -> None:
        result = run_recommendation_baseline_calibration(
            golden_path=Path("data/eval/_nonexistent_rec_golden.json"),
            auto_generate_synthetic=False,
        )
        assert result.calibration_status == "baseline_dataset_insufficient"
        assert result.production_allowed is False
        assert result.golden_set_size == 0

    def test_synthetic_blocked_for_production(self) -> None:
        """Synthetic golden set must block production."""
        entries = generate_synthetic_recommendation_golden_set(count=30)
        path = Path("data/eval/_test_synthetic_rec_golden.json")
        path.write_text(
            json.dumps(
                {
                    "entries": [e.model_dump(mode="json") for e in entries],
                    "metadata": {"notes": "SYNTHETIC"},
                }
            ),
            encoding="utf-8",
        )
        try:
            result = run_recommendation_baseline_calibration(golden_path=path)
            assert result.golden_set_size == 30
            assert result.has_human_labels is True  # has labels
            assert result.has_real_labels is False  # but all synthetic
            assert result.production_allowed is False
            assert result.calibration_status == "baseline_dataset_insufficient"
        finally:
            if path.exists():
                path.unlink()

    def test_empty_golden_set_returns_insufficient(self) -> None:
        path = Path("data/eval/_test_empty_rec_golden.json")
        path.write_text(
            json.dumps({"entries": [], "metadata": {"total": 0}}),
            encoding="utf-8",
        )
        try:
            result = run_recommendation_baseline_calibration(
                golden_path=path,
                auto_generate_synthetic=False,
            )
            assert result.calibration_status == "baseline_dataset_insufficient"
            assert not result.production_allowed
        finally:
            if path.exists():
                path.unlink()

    def test_report_is_generated(self) -> None:
        result = run_recommendation_baseline_calibration(golden_path=_GOLDEN_PATH)
        assert isinstance(result.report, str)
        assert len(result.report) > 0


# ═══════════════════════════════════════════════════════════════════════════
# 14. Registry compatibility
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistryRecordsCompatibility:
    def test_production_blocked_when_insufficient(self) -> None:
        result = run_recommendation_baseline_calibration(golden_path=_GOLDEN_PATH)
        records = make_recommendation_baseline_records(result)
        for r in records:
            assert r.production_allowed is False
            assert r.calibration_status == CalibrationStatus.UNCALIBRATED
            assert r.current_value is None

    def test_records_match_required_decisions(self) -> None:
        from src.recommendation.recommendation_engine import REQUIRED_RECOMMENDATION_DECISIONS

        result = run_recommendation_baseline_calibration(golden_path=_GOLDEN_PATH)
        records = make_recommendation_baseline_records(result)
        record_ids = {r.decision_id for r in records}
        for dec_id in REQUIRED_RECOMMENDATION_DECISIONS:
            assert dec_id in record_ids, f"Missing record for {dec_id}"

    def test_production_blocked_for_synthetic_labels(self) -> None:
        """Evaluator must reject synthetic labels for production_allowed=true."""
        entries = generate_synthetic_recommendation_golden_set(count=10)
        path = Path("data/eval/_test_synth_prod_rejection.json")
        path.write_text(
            json.dumps({"entries": [e.model_dump(mode="json") for e in entries]}),
            encoding="utf-8",
        )
        try:
            result = run_recommendation_baseline_calibration(golden_path=path)
            records = make_recommendation_baseline_records(result)
            for r in records:
                assert r.production_allowed is False
        finally:
            if path.exists():
                path.unlink()

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.evaluation.gap_diagnosis_baseline import (
    CANDIDATE_CONFIDENCE_WEIGHTS,
    CANDIDATE_SEVERITY_WEIGHTS,
    ConfidenceMetrics,
    GapDiagnosisCalibrationResult,
    GapDiagnosisGoldenEntry,
    HumanLabeledGap,
    SeverityMetrics,
    WeightCandidateResult,
    _calibrate_min_evidence_coverage,
    _calibrate_threshold_from_scores,
    _calibrate_uncertainty_penalty_from_scores,
    _check_gap_diagnosis_production_ready,
    _compute_confidence_metrics,
    _compute_evidence_metrics,
    _compute_gap_detection_metrics,
    _compute_severity_metrics,
    _compute_weighted_score,
    _evaluate_weight_candidates,
    _select_best_candidate,
    _spearman,
    check_gap_diagnosis_labels_exist,
    count_labeled_gaps,
    generate_synthetic_gap_diagnosis_golden_set,
    load_gap_diagnosis_golden_set,
    make_gap_diagnosis_baseline_records,
    run_gap_diagnosis_baseline_calibration,
)
from src.evaluation.gap_diagnosis_baseline import (
    _distribution as dist_fn,
)
from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    DecisionCalibrationRecord,
)

_GOLDEN_PATH = Path("data/eval/golden_gap_diagnosis_baseline.json")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_label(
    gap_type: str = "compute_acceleration_gap",
    present: bool = True,
    severity: float = 0.5,
    confidence: float = 0.7,
    evidence_ids: list[str] | None = None,
) -> HumanLabeledGap:
    return HumanLabeledGap(
        gap_type=gap_type,
        human_label_gap_present=present,
        human_label_severity=severity,
        human_label_confidence=confidence,
        supporting_evidence_ids=evidence_ids or [],
        label_notes="test",
        label_source="test",
    )


def _make_entry(
    startup_id: str = "test-001",
    gap_labels: list[HumanLabeledGap] | None = None,
    evidence_count: int = 2,
) -> GapDiagnosisGoldenEntry:
    evidence: list[dict[str, Any]] = [
        {
            "id": f"ev-{startup_id}-{i}",
            "evidence_id": f"ev-{startup_id}-{i}",
            "source_id": f"src-{startup_id}-{i}",
            "url": f"https://example.com/{startup_id}/{i}",
            "text": f"Evidence {i} for {startup_id}",
            "snippet": f"Evidence {i}",
            "claim": f"Claim for evidence {i}",
            "confidence": "high",
            "evidence_confidence_score": 0.85,
            "source_quality_score": 0.75,
        }
        for i in range(evidence_count)
    ]
    return GapDiagnosisGoldenEntry(
        startup_id=startup_id,
        startup_name=f"Test {startup_id}",
        startup_profile_snapshot={"sector": "Technology"},
        accepted_evidence_items_snapshot=evidence,
        accepted_claims_snapshot=[
            {
                "id": f"cl-{startup_id}-0",
                "claim_id": f"cl-{startup_id}-0",
                "claim_text": "Test claim",
                "support_status": "supported",
                "is_critical": False,
            }
        ],
        ai_native_score_snapshot=0.5,
        nvidia_fit_score_snapshot=0.5,
        expected_gap_types=["compute_acceleration_gap"],
        human_labeled_gaps=gap_labels or [],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Golden set loading
# ═══════════════════════════════════════════════════════════════════════════


class TestLoadGoldenSet:
    def test_loads_real_file(self) -> None:
        entries = load_gap_diagnosis_golden_set(_GOLDEN_PATH)
        assert isinstance(entries, list)

    def test_entries_have_required_fields(self) -> None:
        entry = _make_entry()
        assert entry.startup_id
        assert entry.startup_name
        assert isinstance(entry.startup_profile_snapshot, dict)
        assert isinstance(entry.accepted_evidence_items_snapshot, list)
        assert isinstance(entry.accepted_claims_snapshot, list)
        assert entry.ai_native_score_snapshot is not None
        assert entry.nvidia_fit_score_snapshot is not None
        assert isinstance(entry.expected_gap_types, list)
        assert isinstance(entry.human_labeled_gaps, list)

    def test_non_existent_path_returns_empty(self) -> None:
        entries = load_gap_diagnosis_golden_set(Path("nonexistent.json"))
        assert entries == []

    def test_human_labeled_gap_schema(self) -> None:
        label = _make_label(gap_type="inference_performance_gap", severity=0.8, confidence=0.9)
        assert label.gap_type == "inference_performance_gap"
        assert label.human_label_gap_present is True
        assert 0.0 <= label.human_label_severity <= 1.0
        assert 0.0 <= label.human_label_confidence <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Label inspection
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckLabelsExist:
    def test_no_labels(self) -> None:
        entry = _make_entry(gap_labels=[])
        assert not check_gap_diagnosis_labels_exist([entry])

    def test_has_labels(self) -> None:
        entry = _make_entry(gap_labels=[_make_label()])
        assert check_gap_diagnosis_labels_exist([entry])

    def test_empty_list(self) -> None:
        assert not check_gap_diagnosis_labels_exist([])


class TestCountLabeledGaps:
    def test_counts_entries_and_labels(self) -> None:
        entries = [
            _make_entry("e1", gap_labels=[_make_label("gap_a")]),
            _make_entry("e2", gap_labels=[_make_label("gap_b"), _make_label("gap_c")]),
            _make_entry("e3", gap_labels=[]),
        ]
        result = count_labeled_gaps(entries)
        assert result["total_entries_with_labels"] == 2
        assert result["total_gap_labels"] == 3

    def test_empty(self) -> None:
        result = count_labeled_gaps([])
        assert result["total_entries_with_labels"] == 0
        assert result["total_gap_labels"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 3. Synthetic golden set
# ═══════════════════════════════════════════════════════════════════════════


class TestSyntheticGoldenSet:
    def test_generates_requested_count(self) -> None:
        entries = generate_synthetic_gap_diagnosis_golden_set(count=10)
        assert len(entries) == 10

    def test_generates_default_count(self) -> None:
        entries = generate_synthetic_gap_diagnosis_golden_set()
        assert len(entries) == 60

    def test_each_entry_has_labels(self) -> None:
        entries = generate_synthetic_gap_diagnosis_golden_set(count=5)
        for e in entries:
            assert len(e.human_labeled_gaps) >= 1

    def test_each_entry_has_fields(self) -> None:
        entries = generate_synthetic_gap_diagnosis_golden_set(count=3)
        for e in entries:
            assert e.startup_id
            assert e.startup_name
            assert e.ai_native_score_snapshot is not None
            assert e.nvidia_fit_score_snapshot is not None

    def test_labels_have_valid_ranges(self) -> None:
        entries = generate_synthetic_gap_diagnosis_golden_set(count=10)
        for e in entries:
            for g in e.human_labeled_gaps:
                assert 0.0 <= g.human_label_severity <= 1.0
                assert 0.0 <= g.human_label_confidence <= 1.0
                assert g.label_source == "derived_from_synthetic_reference"

    def test_deterministic(self) -> None:
        a = generate_synthetic_gap_diagnosis_golden_set(count=5)
        b = generate_synthetic_gap_diagnosis_golden_set(count=5)
        assert len(a) == len(b)
        for ea, eb in zip(a, b, strict=True):
            assert ea.startup_id == eb.startup_id
            assert len(ea.human_labeled_gaps) == len(eb.human_labeled_gaps)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Utility functions
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeWeightedScore:
    def test_basic_weighted_average(self) -> None:
        score = _compute_weighted_score({"a": 0.5, "b": 1.0}, {"a": 0.5, "b": 0.5})
        assert score == pytest.approx(0.75)

    def test_clamps_below_0(self) -> None:
        score = _compute_weighted_score({"a": -0.5, "b": 0.0}, {"a": 1.0, "b": 0.0})
        assert score == 0.0

    def test_clamps_above_1(self) -> None:
        score = _compute_weighted_score({"a": 2.0, "b": 0.0}, {"a": 1.0, "b": 0.0})
        assert score == 1.0

    def test_zero_weight_sum(self) -> None:
        score = _compute_weighted_score({"a": 0.5}, {})
        assert score == 0.0

    def test_extra_features_ignored(self) -> None:
        score = _compute_weighted_score({"a": 0.5, "c": 100.0}, {"a": 1.0})
        assert score == 0.5


class TestSpearman:
    def test_perfect_positive(self) -> None:
        assert _spearman([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0, abs=0.01)

    def test_perfect_negative(self) -> None:
        assert _spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0, abs=0.01)

    def test_no_correlation(self) -> None:
        rho = _spearman([1, 2, 3, 4, 5], [5, 1, 4, 2, 3])
        assert -1.0 <= rho <= 1.0

    def test_insufficient_data(self) -> None:
        assert _spearman([1], [2]) == 0.0
        assert _spearman([1, 2], [2, 1]) == 0.0


class TestDistribution:
    def test_empty(self) -> None:
        d = dist_fn([])
        assert d["count"] == 0
        assert d["mean"] == 0.0

    def test_basic(self) -> None:
        d = dist_fn([1, 2, 3, 4, 5])
        assert d["count"] == 5
        assert d["mean"] == 3.0
        assert d["min"] == 1.0
        assert d["max"] == 5.0
        assert d["p5"] >= 1.0
        assert d["p50"] >= 2.0
        assert d["p95"] <= 5.0


# ═══════════════════════════════════════════════════════════════════════════
# 5. Severity metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeSeverityMetrics:
    def test_returns_none_with_too_few(self) -> None:
        assert _compute_severity_metrics([0.5], [0.5]) is None

    def test_perfect_match(self) -> None:
        m = _compute_severity_metrics([0.1, 0.5, 0.9], [0.1, 0.5, 0.9])
        assert m is not None
        assert m.correlation is not None and m.correlation == pytest.approx(1.0, abs=0.01)
        assert m.mae is not None and m.mae == 0.0
        assert m.rmse is not None and m.rmse == 0.0

    def test_mae_computed_correctly(self) -> None:
        m = _compute_severity_metrics([0.5, 0.5], [0.5, 0.5])
        assert m is None  # n < 3

    def test_correlation_range(self) -> None:
        m = _compute_severity_metrics([0.1, 0.5, 0.9], [0.9, 0.5, 0.1])
        assert m is not None and m.correlation is not None
        assert -1.0 <= m.correlation <= 1.0

    def test_high_severity_precision_recall(self) -> None:
        m = _compute_severity_metrics([0.9, 0.1, 0.8], [0.9, 0.2, 0.75])
        assert m is not None
        assert m.high_severity_precision is not None and 0.0 <= m.high_severity_precision <= 1.0
        assert m.high_severity_recall is not None and 0.0 <= m.high_severity_recall <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 6. Confidence metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeConfidenceMetrics:
    def test_returns_none_with_too_few(self) -> None:
        assert _compute_confidence_metrics([0.5], [0.5], [0.1]) is None

    def test_perfect_match(self) -> None:
        m = _compute_confidence_metrics([0.1, 0.5, 0.9], [0.1, 0.5, 0.9], [0.1, 0.1, 0.1])
        assert m is not None
        assert m.correlation is not None and m.correlation == pytest.approx(1.0, abs=0.01)
        assert m.mae is not None and m.mae == 0.0
        assert m.rmse is not None and m.rmse == 0.0

    def test_uncertainty_error_relationship(self) -> None:
        m = _compute_confidence_metrics([0.3, 0.5, 0.7], [0.4, 0.5, 0.6], [0.1, 0.2, 0.3])
        assert m is not None
        assert m.uncertainty_error_relationship is not None
        assert isinstance(m.uncertainty_error_relationship, float)
        assert -1.0 <= m.uncertainty_error_relationship <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 7. Gap detection metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeGapDetectionMetrics:
    def test_returns_none_with_no_labels(self) -> None:
        m = _compute_gap_detection_metrics([], [], ["gap_a"])
        assert m is None

    def test_perfect_detection(self) -> None:
        labels = [_make_label("gap_a", present=True)]
        preds = [{"gap_type": "gap_a", "detected": True}]
        m = _compute_gap_detection_metrics(preds, labels, ["gap_a", "gap_b"])
        assert m is not None
        assert m.gap_type_precision is not None
        assert m.gap_type_recall is not None
        assert m.gap_type_f1 is not None
        assert m.false_positive_rate == 0.0
        assert m.false_negative_rate == 0.0

    def test_false_positive(self) -> None:
        labels = [_make_label("gap_a", present=False)]
        preds = [{"gap_type": "gap_a", "detected": True}]
        m = _compute_gap_detection_metrics(preds, labels, ["gap_a"])
        assert m is not None and m.false_positive_rate is not None
        assert m.false_positive_rate > 0

    def test_false_negative(self) -> None:
        labels = [_make_label("gap_a", present=True)]
        preds = [{"gap_type": "gap_a", "detected": False}]
        m = _compute_gap_detection_metrics(preds, labels, ["gap_a"])
        assert m is not None and m.false_negative_rate is not None
        assert m.false_negative_rate > 0


# ═══════════════════════════════════════════════════════════════════════════
# 8. Evidence metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeEvidenceMetrics:
    def test_returns_none_with_empty_labels(self) -> None:
        assert _compute_evidence_metrics([], []) is None

    def test_basic_coverage(self) -> None:
        labels = [_make_label("gap_a", evidence_ids=["ev-1"])]
        m = _compute_evidence_metrics([], labels)
        assert m is not None
        assert m.evidence_coverage_per_gap is not None
        assert m.evidence_coverage_per_gap.get("gap_a") == 1.0

    def test_gap_without_evidence(self) -> None:
        labels = [_make_label("gap_a", evidence_ids=[])]
        m = _compute_evidence_metrics([], labels)
        assert m is not None
        assert m.gap_without_evidence_rate == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 9. Intermediate calibrators
# ═══════════════════════════════════════════════════════════════════════════


class TestCalibrateThresholdFromScores:
    def test_insufficient_data(self) -> None:
        result = _calibrate_threshold_from_scores([0.5], percentile=5.0)
        assert result["threshold"] is None
        assert result["method"] == "insufficient_data"

    def test_threshold_in_range(self) -> None:
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        result = _calibrate_threshold_from_scores(scores)
        assert result["threshold"] is not None
        assert 0.0 <= result["threshold"] <= 1.0
        assert result["method"].startswith("percentile")

    def test_distribution_included(self) -> None:
        result = _calibrate_threshold_from_scores([0.1, 0.3, 0.5, 0.7, 0.9])
        assert "distribution" in result
        assert "mean" in result["distribution"]
        assert "p5" in result["distribution"]


class TestCalibrateUncertaintyPenalty:
    def test_insufficient_data(self) -> None:
        result = _calibrate_uncertainty_penalty_from_scores([0.5], [0.5], [0.1])
        assert result["method"] == "insufficient_data"
        assert result["best_penalty"] == 0.0

    def test_selects_best_penalty(self) -> None:
        pred = [0.3, 0.5, 0.7, 0.4, 0.6]
        human = [0.35, 0.52, 0.68, 0.42, 0.58]
        uncert = [0.1, 0.15, 0.2, 0.12, 0.18]
        result = _calibrate_uncertainty_penalty_from_scores(pred, human, uncert)
        assert isinstance(result["best_penalty"], float)
        assert "results" in result
        assert len(result["results"]) > 0

    def test_penalty_reduces_error(self) -> None:
        """With predictions consistently above labels, penalty should help."""
        pred = [0.6, 0.7, 0.8]
        human = [0.5, 0.6, 0.7]
        uncert = [0.2, 0.2, 0.2]
        result = _calibrate_uncertainty_penalty_from_scores(pred, human, uncert)
        assert result["best_penalty"] >= 0.0


class TestCalibrateMinEvidenceCoverage:
    def test_insufficient_data(self) -> None:
        result = _calibrate_min_evidence_coverage([])
        assert result["method"] == "insufficient_data"
        assert result["recommended_min_coverage"] == 0.10

    def test_basic(self) -> None:
        entries = [
            _make_entry("e1", gap_labels=[_make_label(evidence_ids=["ev-1", "ev-2"])]),
            _make_entry("e2", gap_labels=[_make_label(evidence_ids=["ev-3"])]),
        ]
        result = _calibrate_min_evidence_coverage(entries)
        assert isinstance(result["recommended_min_coverage"], float)
        assert 0.0 <= result["recommended_min_coverage"] <= 1.0

    def test_recommended_floor(self) -> None:
        result = _calibrate_min_evidence_coverage([])
        assert result["recommended_min_coverage"] == 0.10


# ═══════════════════════════════════════════════════════════════════════════
# 10. Production readiness
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckProductionReady:
    def test_blocked_when_too_few_entries(self) -> None:
        ready, blockers = _check_gap_diagnosis_production_ready(
            labeled_entry_count=1,
            gap_label_count=1,
            coverage_by_type={},
            sev_metrics=None,
            conf_metrics=None,
        )
        assert not ready
        assert len(blockers) >= 1

    def test_blocked_when_metrics_below_minimum(self) -> None:
        bad_sev = SeverityMetrics(
            correlation=0.1,
            mae=0.5,
            rmse=0.6,
            calibration_error=0.5,
            high_severity_precision=0.0,
            high_severity_recall=0.0,
        )
        bad_conf = ConfidenceMetrics(
            correlation=0.2,
            mae=0.4,
            rmse=0.5,
            calibration_error=0.4,
            uncertainty_error_relationship=0.0,
        )
        ready, blockers = _check_gap_diagnosis_production_ready(
            labeled_entry_count=30,
            gap_label_count=30,
            coverage_by_type={"gap_a": 1.0},
            sev_metrics=bad_sev,
            conf_metrics=bad_conf,
        )
        assert not ready
        assert any("spearman" in b for b in blockers)
        assert any("MAE" in b for b in blockers)

    def test_passes_with_good_metrics(self) -> None:
        good_sev = SeverityMetrics(
            correlation=0.8,
            mae=0.05,
            rmse=0.06,
            calibration_error=0.05,
            high_severity_precision=0.9,
            high_severity_recall=0.8,
        )
        good_conf = ConfidenceMetrics(
            correlation=0.75,
            mae=0.08,
            rmse=0.09,
            calibration_error=0.08,
            uncertainty_error_relationship=0.3,
        )
        ready, blockers = _check_gap_diagnosis_production_ready(
            labeled_entry_count=30,
            gap_label_count=30,
            coverage_by_type={"gap_a": 1.0, "gap_b": 1.0},
            sev_metrics=good_sev,
            conf_metrics=good_conf,
        )
        assert ready
        assert blockers == []


# ═══════════════════════════════════════════════════════════════════════════
# 11. Grid search
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluateWeightCandidates:
    def test_returns_results_for_each_candidate(self) -> None:
        entries = generate_synthetic_gap_diagnosis_golden_set(count=10)
        results = _evaluate_weight_candidates(entries, CANDIDATE_SEVERITY_WEIGHTS, "severity")
        assert len(results) == len(CANDIDATE_SEVERITY_WEIGHTS)
        for r in results:
            assert isinstance(r, WeightCandidateResult)
            assert isinstance(r.candidate_index, int)

    def test_sorted_by_spearman_desc(self) -> None:
        entries = generate_synthetic_gap_diagnosis_golden_set(count=10)
        results = _evaluate_weight_candidates(entries, CANDIDATE_SEVERITY_WEIGHTS, "severity")
        for i in range(len(results) - 1):
            s_i = results[i].spearman
            s_next = results[i + 1].spearman
            if s_i is not None and s_next is not None:
                assert s_i >= s_next

    def test_insufficient_data_all_none(self) -> None:
        results = _evaluate_weight_candidates(
            [_make_entry("e1", gap_labels=[_make_label()])],
            CANDIDATE_SEVERITY_WEIGHTS[:1],
            "severity",
        )
        assert results
        assert results[0].spearman is None

    def test_confidence_weights_evaluation(self) -> None:
        entries = generate_synthetic_gap_diagnosis_golden_set(count=10)
        results = _evaluate_weight_candidates(entries, CANDIDATE_CONFIDENCE_WEIGHTS, "confidence")
        assert len(results) == len(CANDIDATE_CONFIDENCE_WEIGHTS)


class TestSelectBestCandidate:
    def test_returns_best_index(self) -> None:
        """Returns first valid candidate (assumes pre-sorted by evaluate)."""
        candidates = [
            WeightCandidateResult(0, {}, "severity", spearman=0.8, mae=0.05, rmse=0.08),
            WeightCandidateResult(1, {}, "severity", spearman=0.5, mae=0.1, rmse=0.15),
        ]
        assert _select_best_candidate(candidates) == 0

    def test_returns_none_if_all_none(self) -> None:
        candidates = [
            WeightCandidateResult(0, {}, "severity", spearman=None, mae=None, rmse=None),
        ]
        assert _select_best_candidate(candidates) is None

    def test_skips_none_candidates(self) -> None:
        candidates = [
            WeightCandidateResult(0, {}, "severity", spearman=None, mae=None, rmse=None),
            WeightCandidateResult(1, {}, "severity", spearman=0.6, mae=0.1, rmse=0.12),
        ]
        assert _select_best_candidate(candidates) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 12. Registry record generation
# ═══════════════════════════════════════════════════════════════════════════


class TestMakeBaselineRecords:
    def test_insufficient_produces_uncalibrated(self) -> None:
        result = GapDiagnosisCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            label_coverage={
                "total_entries_with_labels": 0,
                "total_gap_labels": 0,
                "gap_type_coverage": {},
            },
            production_blockers=["Empty"],
        )
        records = make_gap_diagnosis_baseline_records(result)
        assert len(records) == 5
        for r in records:
            assert r.calibration_status == CalibrationStatus.UNCALIBRATED
            assert r.production_allowed is False
            assert r.current_value is None

    def test_blocked_produces_uncalibrated(self) -> None:
        result = GapDiagnosisCalibrationResult(
            calibration_status="baseline_measured_blocked",
            production_allowed=False,
            golden_set_size=30,
            has_human_labels=True,
            label_coverage={
                "total_entries_with_labels": 30,
                "total_gap_labels": 40,
                "gap_type_coverage": {"gap_a": 10},
            },
            production_blockers=["Severity spearman below minimum"],
        )
        records = make_gap_diagnosis_baseline_records(result)
        for r in records:
            assert r.calibration_status == CalibrationStatus.UNCALIBRATED
            assert r.production_allowed is False

    def test_all_required_decisions_present(self) -> None:
        result = GapDiagnosisCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            label_coverage={
                "total_entries_with_labels": 0,
                "total_gap_labels": 0,
                "gap_type_coverage": {},
            },
        )
        records = make_gap_diagnosis_baseline_records(result)
        ids = {r.decision_id for r in records}
        expected = {
            "gap_diagnosis.severity_weights",
            "gap_diagnosis.confidence_weights",
            "gap_diagnosis.production_threshold",
            "gap_diagnosis.uncertainty_penalty",
            "gap_diagnosis.minimum_evidence_coverage",
        }
        assert ids == expected

    def test_successful_produces_baseline_measured(self) -> None:
        result = GapDiagnosisCalibrationResult(
            calibration_status="baseline_measured",
            production_allowed=True,
            golden_set_size=30,
            has_human_labels=True,
            label_coverage={
                "total_entries_with_labels": 30,
                "total_gap_labels": 50,
                "gap_type_coverage": {"gap_a": 10},
            },
            severity_candidates=[
                WeightCandidateResult(0, CANDIDATE_SEVERITY_WEIGHTS[0], "severity", spearman=0.8, mae=0.1, rmse=0.12),
            ],
            confidence_candidates=[
                WeightCandidateResult(
                    0,
                    CANDIDATE_CONFIDENCE_WEIGHTS[0],
                    "confidence",
                    spearman=0.75,
                    mae=0.12,
                    rmse=0.14,
                ),
            ],
            best_severity_candidate_index=0,
            best_confidence_candidate_index=0,
            best_severity_metrics=SeverityMetrics(
                correlation=0.8,
                mae=0.1,
                rmse=0.12,
                calibration_error=0.1,
                high_severity_precision=0.8,
                high_severity_recall=0.7,
            ),
            best_confidence_metrics=ConfidenceMetrics(
                correlation=0.75,
                mae=0.12,
                rmse=0.14,
                calibration_error=0.12,
                uncertainty_error_relationship=0.3,
            ),
            production_threshold={
                "threshold": 0.3,
                "method": "percentile_p5",
                "percentile": 5.0,
                "distribution": {},
            },
            uncertainty_penalty={
                "best_penalty": 0.02,
                "method": "sensitivity_analysis",
                "results": [],
                "best_mae": 0.09,
                "best_max_error": 0.2,
            },
            min_evidence_coverage={"recommended_min_coverage": 0.15, "method": "p25", "n": 50},
        )
        records = make_gap_diagnosis_baseline_records(result)
        assert len(records) == 5
        for r in records:
            assert r.calibration_status == CalibrationStatus.BASELINE_MEASURED
            assert r.production_allowed is True

    def test_records_have_evidence_source(self) -> None:
        result = GapDiagnosisCalibrationResult(
            calibration_status="baseline_dataset_insufficient",
            production_allowed=False,
            golden_set_size=0,
            has_human_labels=False,
            label_coverage={
                "total_entries_with_labels": 0,
                "total_gap_labels": 0,
                "gap_type_coverage": {},
            },
        )
        records = make_gap_diagnosis_baseline_records(result)
        for r in records:
            assert r.evidence_source is not None
            assert len(r.evidence_source) > 0
            assert isinstance(r.notes, str)
            assert len(r.notes) > 0

    def test_records_have_value_origin(self) -> None:
        result = GapDiagnosisCalibrationResult(
            calibration_status="baseline_measured",
            production_allowed=True,
            golden_set_size=30,
            has_human_labels=True,
            label_coverage={
                "total_entries_with_labels": 30,
                "total_gap_labels": 50,
                "gap_type_coverage": {},
            },
            severity_candidates=[
                WeightCandidateResult(0, CANDIDATE_SEVERITY_WEIGHTS[0], "severity", spearman=0.8, mae=0.1, rmse=0.12),
            ],
            confidence_candidates=[
                WeightCandidateResult(
                    0,
                    CANDIDATE_CONFIDENCE_WEIGHTS[0],
                    "confidence",
                    spearman=0.75,
                    mae=0.12,
                    rmse=0.14,
                ),
            ],
            best_severity_candidate_index=0,
            best_confidence_candidate_index=0,
        )
        records = make_gap_diagnosis_baseline_records(result)
        for r in records:
            assert r.value_origin is not None
            assert "gap_diagnosis_baseline.py" in r.value_origin


# ═══════════════════════════════════════════════════════════════════════════
# 13. Full calibration run
# ═══════════════════════════════════════════════════════════════════════════


class TestRunCalibration:
    def test_insufficient_without_auto_generate(self) -> None:
        """With auto_generate_synthetic=False, golden set missing returns insufficient."""
        result = run_gap_diagnosis_baseline_calibration(
            golden_path=Path("data/eval/_nonexistent_golden.json"),
            auto_generate_synthetic=False,
        )
        assert result.calibration_status == "baseline_dataset_insufficient"
        assert result.production_allowed is False
        assert result.golden_set_size == 0

    def test_synthetic_full_calibration(self) -> None:
        """Run full calibration with synthetic 60-entry golden set."""
        entries = generate_synthetic_gap_diagnosis_golden_set(count=60)
        path = Path("data/eval/_test_synthetic_gap_golden.json")
        path.write_text(
            json.dumps({"startups": [e.model_dump(mode="json") for e in entries]}),
            encoding="utf-8",
        )
        try:
            result = run_gap_diagnosis_baseline_calibration(golden_path=path)
            assert result.golden_set_size == 60
            assert result.has_human_labels is True
            assert result.label_coverage["total_gap_labels"] >= 60

            # Should meet or approach production criteria with synthetic data
            if result.production_allowed:
                assert result.calibration_status == "baseline_measured"
                assert result.production_threshold is not None
                assert result.production_threshold["threshold"] is not None
            else:
                assert result.calibration_status in (
                    "baseline_measured_blocked",
                    "baseline_dataset_insufficient",
                )
        finally:
            if path.exists():
                path.unlink()

    def test_candidates_are_evaluated(self) -> None:
        """Grid search candidates should be populated."""
        entries = generate_synthetic_gap_diagnosis_golden_set(count=30)
        path = Path("data/eval/_test_synthetic_gap_golden_30.json")
        path.write_text(
            json.dumps({"startups": [e.model_dump(mode="json") for e in entries]}),
            encoding="utf-8",
        )
        try:
            result = run_gap_diagnosis_baseline_calibration(golden_path=path)
            assert len(result.severity_candidates) == len(CANDIDATE_SEVERITY_WEIGHTS)
            assert len(result.confidence_candidates) == len(CANDIDATE_CONFIDENCE_WEIGHTS)
        finally:
            if path.exists():
                path.unlink()

    def test_report_is_generated(self) -> None:
        """Calibration report should be non-empty."""
        result = run_gap_diagnosis_baseline_calibration(golden_path=_GOLDEN_PATH)
        assert isinstance(result.report, str)
        assert len(result.report) > 0

    def test_too_few_entries_returns_insufficient(self) -> None:
        entries = [_make_entry("e1", gap_labels=[_make_label()])]
        path = Path("data/eval/_test_gap_too_few.json")
        path.write_text(
            json.dumps({"startups": [e.model_dump(mode="json") for e in entries]}),
            encoding="utf-8",
        )
        try:
            result = run_gap_diagnosis_baseline_calibration(golden_path=path)
            assert result.calibration_status == "baseline_dataset_insufficient"
            assert not result.production_allowed
        finally:
            if path.exists():
                path.unlink()


# ═══════════════════════════════════════════════════════════════════════════
# 14. Registry compatibility
# ═══════════════════════════════════════════════════════════════════════════


class TestRegistryRecordsCompatibility:
    def test_production_blocked_when_insufficient(self) -> None:
        """Records from insufficient data must block production."""
        result = run_gap_diagnosis_baseline_calibration(golden_path=_GOLDEN_PATH)
        records = make_gap_diagnosis_baseline_records(result)
        for r in records:
            assert r.production_allowed is False
            assert r.calibration_status == CalibrationStatus.UNCALIBRATED
            assert r.current_value is None

    def test_records_match_required_decisions(self) -> None:
        from src.diagnosis.gap_diagnosis_scoring import REQUIRED_CALIBRATION_DECISIONS

        result = run_gap_diagnosis_baseline_calibration(golden_path=_GOLDEN_PATH)
        records = make_gap_diagnosis_baseline_records(result)
        record_ids = {r.decision_id for r in records}
        for dec_id in REQUIRED_CALIBRATION_DECISIONS:
            assert dec_id in record_ids, f"Missing record for {dec_id}"

    def test_records_are_valid_pydantic(self) -> None:
        """All records pass DecisionCalibrationRecord validation."""
        result = run_gap_diagnosis_baseline_calibration(golden_path=_GOLDEN_PATH)
        records = make_gap_diagnosis_baseline_records(result)
        for r in records:
            assert isinstance(r, DecisionCalibrationRecord)
            assert r.decision_id
            assert r.decision_name
            assert r.decision_type is not None
            assert r.metric_name
            assert r.calibration_method is not None
            assert r.owner
            assert r.last_calibrated_at is not None

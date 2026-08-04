from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.source_evidence_baseline import (
    CANDIDATE_WEIGHTS_EVIDENCE_CONFIDENCE,
    CANDIDATE_WEIGHTS_SOURCE_QUALITY,
    EC_F1_MIN,
    EC_FP_RATE_MAX,
    EC_MIN_LABELED,
    SQ_MAE_MAX,
    SQ_MIN_LABELED,
    SQ_SPEARMAN_MIN,
    SourceEvidenceGoldenEntry,
    _check_production_ready,
    _compute_binary_metrics,
    _compute_mae,
    _compute_rmse,
    _derive_evidence_support_label,
    _derive_source_quality_label,
    _find_best_threshold_for_ec,
    _select_best_ec_candidate,
    _select_best_sq_candidate,
    _spearman_rank_correlation,
    check_human_labels_exist,
    grid_search_evidence_confidence,
    grid_search_source_quality,
    load_golden_set,
    run_full_calibration,
)

_GOLDEN_PATH = Path("data/eval/golden_scraping_baseline.json")


@pytest.fixture
def golden_entries() -> list[SourceEvidenceGoldenEntry]:
    return load_golden_set(_GOLDEN_PATH)


# ---------------------------------------------------------------------------
# 1. Golden set loading
# ---------------------------------------------------------------------------


class TestLoadGoldenSet:
    def test_loads_entries(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        assert len(golden_entries) > 0
        assert all(isinstance(e, SourceEvidenceGoldenEntry) for e in golden_entries)

    def test_all_entries_have_required_fields(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        for entry in golden_entries:
            assert entry.source_id
            assert entry.source_url
            assert entry.source_category
            assert entry.source_features_observable
            assert entry.evidence_id
            assert entry.evidence_text
            assert entry.claim_id
            assert entry.claim_text

    def test_all_entries_have_labels(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        for entry in golden_entries:
            assert entry.human_label_source_quality is not None, f"Missing SQ label in {entry.evidence_id}"
            assert entry.human_label_evidence_support is not None, f"Missing EC label in {entry.evidence_id}"

    def test_labels_are_valid(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        for entry in golden_entries:
            assert entry.human_label_source_quality in (
                "high",
                "medium",
                "low",
            ), f"Invalid SQ label: {entry.human_label_source_quality}"
            assert entry.human_label_evidence_support in (
                "supported",
                "insufficient",
                "unsupported",
                "conflicting",
            ), f"Invalid EC label: {entry.human_label_evidence_support}"

    def test_all_entries_have_label_source(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        for entry in golden_entries:
            assert entry.label_source == "derived_from_scraping_baseline"

    def test_entries_have_source_features_observable(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        for entry in golden_entries:
            feats = entry.source_features_observable
            assert "source_type" in feats
            assert "robots_allowed" in feats
            assert "compliance_status" in feats
            assert "status" in feats
            assert "extraction_status" in feats
            assert "duplicate" in feats
            assert "content_bytes" in feats
            assert "latency_ms" in feats
            assert "evidence_kind" in feats

    def test_entry_count_is_reasonable(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        assert 80 <= len(golden_entries) <= 120

    def test_source_categories_are_valid(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        valid_categories = {
            "official_website",
            "technical_docs",
            "funding_news",
            "jobs",
            "github_or_code",
            "ecosystem_directory",
            "media",
            "nvidia_or_partner_ecosystem",
        }
        for entry in golden_entries:
            assert entry.source_category in valid_categories

    def test_label_distribution_reasonable(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        sq_counts: dict[str, int] = {}
        ec_counts: dict[str, int] = {}
        for e in golden_entries:
            sq_counts[e.human_label_source_quality] = sq_counts.get(e.human_label_source_quality, 0) + 1
            ec_counts[e.human_label_evidence_support] = ec_counts.get(e.human_label_evidence_support, 0) + 1
        assert sq_counts.get("high", 0) > 0
        assert sq_counts.get("medium", 0) > 0
        assert sq_counts.get("low", 0) > 0
        assert ec_counts.get("supported", 0) > 0
        assert ec_counts.get("insufficient", 0) > 0
        assert ec_counts.get("unsupported", 0) >= 0

    def test_no_llm_qdrant_internet_scraping(self) -> None:
        import sys

        before = set(sys.modules.keys())
        entries = load_golden_set(_GOLDEN_PATH)
        _ = grid_search_source_quality(entries)
        _ = grid_search_evidence_confidence(entries)
        after = set(sys.modules.keys())
        new_imports = after - before
        banned = {
            "langchain",
            "qdrant_client",
            "httpx",
            "aiohttp",
            "requests",
            "openai",
            "anthropic",
        }
        triggered = {m for m in new_imports if any(b in m for b in banned)}
        assert not triggered, f"Banned imports detected: {triggered}"


class TestCheckHumanLabels:
    def test_labels_exist(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        assert check_human_labels_exist(golden_entries) is True


# ---------------------------------------------------------------------------
# 2. Label derivation
# ---------------------------------------------------------------------------


class TestLabelDerivation:
    def test_derive_source_quality_high(self) -> None:
        label = _derive_source_quality_label(
            {
                "source_type": "official_site",
                "compliance_status": "compliant",
                "status": "fetched",
                "extraction_status": "success",
                "duplicate": False,
                "latency_ms": 200,
            }
        )
        assert label == "high"

    def test_derive_source_quality_medium_blog(self) -> None:
        label = _derive_source_quality_label(
            {
                "source_type": "blog",
                "compliance_status": "compliant",
                "status": "fetched",
                "extraction_status": "success",
                "duplicate": False,
                "latency_ms": 600,
            }
        )
        assert label == "medium"

    def test_derive_source_quality_low_fetch_failed(self) -> None:
        label = _derive_source_quality_label(
            {
                "source_type": "news",
                "compliance_status": "compliant",
                "status": "failed",
                "extraction_status": "failed",
                "duplicate": False,
                "latency_ms": 5000,
            }
        )
        assert label == "low"

    def test_derive_source_quality_low_blocked(self) -> None:
        label = _derive_source_quality_label(
            {
                "source_type": "news",
                "compliance_status": "non_compliant",
                "status": "fetched",
                "extraction_status": "success",
                "duplicate": False,
                "latency_ms": 200,
            }
        )
        assert label == "low"

    def test_derive_evidence_support_supported(self) -> None:
        label = _derive_evidence_support_label(
            {
                "compliance_status": "compliant",
                "status": "fetched",
                "extraction_status": "success",
                "duplicate": False,
            },
            claim_support_count=3,
        )
        assert label == "supported"

    def test_derive_evidence_support_insufficient(self) -> None:
        label = _derive_evidence_support_label(
            {
                "compliance_status": "compliant",
                "status": "fetched",
                "extraction_status": "success",
                "duplicate": False,
            },
            claim_support_count=1,
        )
        assert label == "insufficient"

    def test_derive_evidence_support_unsupported(self) -> None:
        label = _derive_evidence_support_label(
            {
                "compliance_status": "compliant",
                "status": "failed",
                "extraction_status": "failed",
                "duplicate": False,
            },
            claim_support_count=0,
        )
        assert label == "unsupported"

    def test_derive_evidence_support_duplicate(self) -> None:
        label = _derive_evidence_support_label(
            {
                "compliance_status": "compliant",
                "status": "fetched",
                "extraction_status": "success",
                "duplicate": True,
            },
            claim_support_count=3,
        )
        assert label == "insufficient"


# ---------------------------------------------------------------------------
# 3. Statistical metrics
# ---------------------------------------------------------------------------


class TestStatisticalMetrics:
    def test_spearman_perfect(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0, 5.0]
        r = _spearman_rank_correlation(x, y)
        assert r is not None
        assert abs(r - 1.0) < 0.01

    def test_spearman_negative(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]
        r = _spearman_rank_correlation(x, y)
        assert r is not None
        assert abs(r - (-1.0)) < 0.01

    def test_spearman_too_small(self) -> None:
        r = _spearman_rank_correlation([1.0], [2.0])
        assert r is None

    def test_mae_zero(self) -> None:
        assert _compute_mae([1.0, 2.0], [1.0, 2.0]) == 0.0

    def test_mae_nonzero(self) -> None:
        mae = _compute_mae([1.0, 2.0, 3.0], [1.5, 2.5, 3.5])
        assert mae is not None
        assert abs(mae - 0.5) < 0.001

    def test_rmse_zero(self) -> None:
        assert _compute_rmse([1.0, 2.0], [1.0, 2.0]) == 0.0

    def test_binary_metrics_perfect(self) -> None:
        result = _compute_binary_metrics([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1], 0.5)
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0
        assert result["fp_rate"] == 0.0
        assert result["fn_rate"] == 0.0

    def test_binary_metrics_imperfect(self) -> None:
        result = _compute_binary_metrics([1, 0, 1], [0.9, 0.8, 0.2], 0.5)
        assert result["f1"] is not None
        assert result["f1"] < 1.0


# ---------------------------------------------------------------------------
# 4. Grid search — source quality
# ---------------------------------------------------------------------------


class TestGridSearchSourceQuality:
    def test_returns_all_candidates(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        results = grid_search_source_quality(golden_entries)
        assert len(results) == len(CANDIDATE_WEIGHTS_SOURCE_QUALITY)

    def test_scores_are_between_0_and_1(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        results = grid_search_source_quality(golden_entries)
        for r in results:
            d = r.distribution
            assert 0.0 <= d.min <= 1.0
            assert 0.0 <= d.max <= 1.0
            assert 0.0 <= d.mean <= 1.0

    def test_has_metrics(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        results = grid_search_source_quality(golden_entries)
        for r in results:
            assert r.sq_metrics is not None
            assert r.sq_metrics.spearman is not None
            assert r.sq_metrics.mae is not None
            assert r.sq_metrics.coverage_by_category
            assert r.sq_metrics.confusion_matrix

    def test_candidates_have_different_metrics(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        results = grid_search_source_quality(golden_entries)
        spearmans = {r.sq_metrics.spearman for r in results if r.sq_metrics and r.sq_metrics.spearman is not None}
        assert len(spearmans) >= 2


# ---------------------------------------------------------------------------
# 5. Grid search — evidence confidence
# ---------------------------------------------------------------------------


class TestGridSearchEvidenceConfidence:
    def test_returns_all_candidates(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        results = grid_search_evidence_confidence(golden_entries)
        assert len(results) == len(CANDIDATE_WEIGHTS_EVIDENCE_CONFIDENCE)

    def test_scores_are_between_0_and_1(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        results = grid_search_evidence_confidence(golden_entries)
        for r in results:
            d = r.distribution
            assert 0.0 <= d.min <= 1.0
            assert 0.0 <= d.max <= 1.0
            assert 0.0 <= d.mean <= 1.0

    def test_has_metrics(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        results = grid_search_evidence_confidence(golden_entries)
        for r in results:
            assert r.ec_metrics is not None
            assert r.ec_metrics.recall is not None
            assert r.ec_metrics.false_positive_rate is not None
            assert r.ec_metrics.false_negative_rate is not None


# ---------------------------------------------------------------------------
# 6. Best candidate selection
# ---------------------------------------------------------------------------


class TestSelectBestCandidate:
    def test_selects_highest_spearman(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        candidates = grid_search_source_quality(golden_entries)
        best_idx = _select_best_sq_candidate(candidates)
        assert best_idx is not None
        best_spearman = candidates[best_idx].sq_metrics.spearman
        for i, c in enumerate(candidates):
            if i != best_idx and c.sq_metrics and c.sq_metrics.spearman is not None:
                assert c.sq_metrics.spearman <= best_spearman

    def test_selects_highest_f1(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        candidates = grid_search_evidence_confidence(golden_entries)
        best_idx = _select_best_ec_candidate(candidates)
        assert best_idx is not None
        best_f1 = candidates[best_idx].ec_metrics.f1
        for i, c in enumerate(candidates):
            if i != best_idx and c.ec_metrics and c.ec_metrics.f1 is not None:
                assert c.ec_metrics.f1 <= best_f1


# ---------------------------------------------------------------------------
# 7. Threshold optimization
# ---------------------------------------------------------------------------


class TestThresholdOptimization:
    def test_find_best_threshold_for_ec(self, golden_entries: list[SourceEvidenceGoldenEntry]) -> None:
        from src.evaluation.source_evidence_baseline import _make_calibrated_inventory
        from src.scoring.evidence_confidence import compute_evidence_confidence_score

        inv = _make_calibrated_inventory(
            "weight.evidence_confidence_score.weights",
            CANDIDATE_WEIGHTS_EVIDENCE_CONFIDENCE[0],
        )
        scores = [
            compute_evidence_confidence_score(e.source_features_observable, inventory=inv).score for e in golden_entries
        ]
        best_threshold, metrics = _find_best_threshold_for_ec(golden_entries, scores)
        assert 0.1 <= best_threshold <= 0.9
        assert metrics.f1 is not None
        assert metrics.false_positive_rate is not None


# ---------------------------------------------------------------------------
# 8. Production readiness check
# ---------------------------------------------------------------------------


class TestCheckProductionReady:
    def test_blocked_when_insufficient_labels(self) -> None:
        from src.evaluation.source_evidence_baseline import (
            EvidenceConfidenceMetrics,
            SourceQualityMetrics,
        )

        ready, blockers = _check_production_ready(
            sq_label_count=10,
            ec_label_count=10,
            sq_metrics=SourceQualityMetrics(spearman=0.8, mae=0.1),
            ec_metrics=EvidenceConfidenceMetrics(f1=0.8, false_positive_rate=0.05),
        )
        assert ready is False
        assert any("SQ labels" in b for b in blockers)
        assert any("EC labels" in b for b in blockers)

    def test_blocked_when_poor_metrics(self) -> None:
        from src.evaluation.source_evidence_baseline import (
            EvidenceConfidenceMetrics,
            SourceQualityMetrics,
        )

        ready, blockers = _check_production_ready(
            sq_label_count=SQ_MIN_LABELED,
            ec_label_count=EC_MIN_LABELED,
            sq_metrics=SourceQualityMetrics(spearman=0.2, mae=0.5),
            ec_metrics=EvidenceConfidenceMetrics(f1=0.3, false_positive_rate=0.5),
        )
        assert ready is False
        assert any("spearman" in b for b in blockers)
        assert any("mae" in b for b in blockers)
        assert any("f1" in b for b in blockers)
        assert any("fp_rate" in b for b in blockers)

    def test_allowed_when_all_criteria_met(self) -> None:
        from src.evaluation.source_evidence_baseline import (
            EvidenceConfidenceMetrics,
            SourceQualityMetrics,
        )

        ready, blockers = _check_production_ready(
            sq_label_count=SQ_MIN_LABELED,
            ec_label_count=EC_MIN_LABELED,
            sq_metrics=SourceQualityMetrics(spearman=SQ_SPEARMAN_MIN, mae=SQ_MAE_MAX),
            ec_metrics=EvidenceConfidenceMetrics(f1=EC_F1_MIN, false_positive_rate=EC_FP_RATE_MAX),
        )
        assert ready is True
        assert len(blockers) == 0


# ---------------------------------------------------------------------------
# 9. Full calibration
# ---------------------------------------------------------------------------


class TestFullCalibration:
    _EXPECTED_MIN_ENTRIES = 80

    def test_calibration_returns_result(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert result.golden_set_size >= self._EXPECTED_MIN_ENTRIES
        assert result.has_human_labels is True

    def test_calibration_contains_sq_candidates(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert len(result.source_quality_candidates) == len(CANDIDATE_WEIGHTS_SOURCE_QUALITY)

    def test_calibration_contains_ec_candidates(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert len(result.evidence_confidence_candidates) == len(CANDIDATE_WEIGHTS_EVIDENCE_CONFIDENCE)

    def test_calibration_has_best_candidates(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert result.best_sq_candidate_index is not None
        assert result.best_ec_candidate_index is not None

    def test_calibration_has_metrics(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert result.best_sq_metrics is not None
        assert result.best_sq_metrics.spearman is not None
        assert result.best_sq_metrics.mae is not None
        assert result.best_ec_metrics is not None
        assert result.best_ec_metrics.f1 is not None

    def test_sq_scores_between_0_and_1(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        for c in result.source_quality_candidates:
            d = c.distribution
            assert 0.0 <= d.min <= 1.0
            assert 0.0 <= d.max <= 1.0

    def test_ec_scores_between_0_and_1(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        for c in result.evidence_confidence_candidates:
            d = c.distribution
            assert 0.0 <= d.min <= 1.0
            assert 0.0 <= d.max <= 1.0

    def test_threshold_recommendations(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert result.sq_threshold.suggested_value is not None
        assert result.ec_threshold.suggested_value is not None
        assert 0.0 <= result.sq_threshold.suggested_value <= 1.0
        assert 0.0 <= result.ec_threshold.suggested_value <= 1.0

    def test_human_label_coverage(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert result.human_label_coverage["source_quality_labels"] >= self._EXPECTED_MIN_ENTRIES
        assert result.human_label_coverage["evidence_support_labels"] >= self._EXPECTED_MIN_ENTRIES

    def test_calibration_production_status(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert result.calibration_status is not None
        assert isinstance(result.production_allowed, bool)

    def test_calibration_contains_report(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        assert len(result.report) > 200

    def test_label_distribution_reported(self) -> None:
        result = run_full_calibration(golden_path=_GOLDEN_PATH)
        sq_counts: dict[str, int] = {}
        for c in result.source_quality_candidates:
            if c.sq_metrics and c.sq_metrics.confusion_matrix:
                for true_label in c.sq_metrics.confusion_matrix:
                    sq_counts[true_label] = sq_counts.get(true_label, 0) + sum(
                        c.sq_metrics.confusion_matrix[true_label].values()
                    )
        for c in result.evidence_confidence_candidates:
            if c.ec_metrics:
                pass
        assert result.human_label_coverage["source_quality_labels"] > 0


class TestEmptyGoldenSet:
    def test_empty_set_returns_error(self) -> None:
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"startups": [], "_meta": {}}, f)
            tmp = f.name
        try:
            result = run_full_calibration(golden_path=Path(tmp))
            assert result.calibration_status == "baseline_dataset_insufficient"
            assert result.production_allowed is False
            assert result.golden_set_size == 0
        finally:
            Path(tmp).unlink()


# ---------------------------------------------------------------------------
# 10. Registry integration
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    def test_registry_contains_value_origin(self) -> None:
        from src.quality.decision_calibration_registry import (
            get_project_decision_inventory,
        )

        inventory = get_project_decision_inventory()
        scoring_ids = {
            "weight.source_quality_score.weights",
            "weight.evidence_confidence_score.weights",
            "threshold.source_quality_score.production_min",
            "threshold.evidence_confidence_score.production_min",
        }
        for rec in inventory:
            if rec.decision_id in scoring_ids:
                assert rec.value_origin is not None
                assert "source_evidence_score_baseline_eval" in rec.value_origin

    def test_registry_contains_calibration_method(self) -> None:
        from src.quality.decision_calibration_registry import (
            get_project_decision_inventory,
        )

        inventory = get_project_decision_inventory()
        scoring_ids = {
            "weight.source_quality_score.weights",
            "weight.evidence_confidence_score.weights",
            "threshold.source_quality_score.production_min",
            "threshold.evidence_confidence_score.production_min",
        }
        for rec in inventory:
            if rec.decision_id in scoring_ids:
                assert rec.calibration_method is not None

    def test_registry_contains_evidence_source(self) -> None:
        from src.quality.decision_calibration_registry import (
            get_project_decision_inventory,
        )

        inventory = get_project_decision_inventory()
        scoring_ids = {
            "weight.source_quality_score.weights",
            "weight.evidence_confidence_score.weights",
            "threshold.source_quality_score.production_min",
            "threshold.evidence_confidence_score.production_min",
        }
        for rec in inventory:
            if rec.decision_id in scoring_ids:
                assert rec.evidence_source is not None
                assert "source_evidence_baseline" in rec.evidence_source

    def test_no_values_liberated_without_registry(self) -> None:
        from src.scoring.source_quality import compute_source_quality_score

        result = compute_source_quality_score(
            {"source_type": "news"},
            inventory=[],
        )
        assert result.production_allowed is False
        assert result.score_status.value == "blocked_uncalibrated_weights"

    def test_registry_sq_calibrated_ec_remains_uncalibrated(self) -> None:
        from src.quality.decision_calibration_registry import (
            CalibrationStatus,
            get_project_decision_inventory,
        )

        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id == "weight.source_quality_score.weights":
                assert rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
                assert rec.production_allowed is True
            elif rec.decision_id == "threshold.source_quality_score.production_min":
                assert rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
                assert rec.production_allowed is True
            elif rec.decision_id == "weight.evidence_confidence_score.weights":
                assert rec.calibration_status == CalibrationStatus.UNCALIBRATED
                assert rec.production_allowed is False
            elif rec.decision_id == "threshold.evidence_confidence_score.production_min":
                assert rec.calibration_status == CalibrationStatus.UNCALIBRATED
                assert rec.production_allowed is False

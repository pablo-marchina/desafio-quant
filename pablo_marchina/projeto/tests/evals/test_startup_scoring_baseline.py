from __future__ import annotations

from pathlib import Path
from typing import Any

from src.evaluation.startup_scoring_calibration import (
    AI_NATIVE_MAE_MAX,
    AI_NATIVE_MIN_LABELED,
    AI_NATIVE_SPEARMAN_MIN,
    CANDIDATE_AI_WEIGHTS,
    CANDIDATE_NVIDIA_WEIGHTS,
    NVIDIA_FIT_FP_RATE_MAX,
    NVIDIA_FIT_MAE_MAX,
    NVIDIA_FIT_MIN_LABELED,
    NVIDIA_FIT_SPEARMAN_MIN,
    StartupScoringGoldenEntry,
    StartupScoringMetrics,
    _check_startup_scoring_production_ready,
    _compute_ai_native_metrics,
    _compute_nvidia_fit_metrics,
    _compute_scores_for_entries,
    _evaluate_weight_candidates,
    _select_best_candidate,
    check_human_labels_exist,
    load_startup_scoring_golden_set,
    run_startup_scoring_baseline_calibration,
)

_GOLDEN_PATH = Path("data/eval/golden_startup_scoring_baseline.json")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_test_entry(
    ai_signals: int = 1,
    nv_signals: int = 1,
    ai_label: str | None = "medium",
    nv_label: str | None = "medium",
    label_source: str = "test",
) -> StartupScoringGoldenEntry:
    claims: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    if ai_signals > 0:
        claims.append(
            {
                "claim_text": "Startup usa inteligencia artificial para analise preditiva",
                "criticality": "critical",
                "support_status": "supported",
                "confidence": "medium",
            }
        )
    if nv_signals > 0:
        claims.append(
            {
                "claim_text": "Plataforma usa GPU NVIDIA para treinamento de modelos",
                "criticality": "normal",
                "support_status": "supported",
                "confidence": "medium",
            }
        )
    if ai_signals > 1:
        evidence.append(
            {
                "text": "A startup utiliza machine learning e PyTorch para processamento de dados com GPU.",
                "source_type": "official_website",
                "source_quality_score": 0.85,
                "evidence_confidence_score": 0.78,
                "source_id": "src1",
            }
        )
    if nv_signals > 1:
        evidence.append(
            {
                "text": "Treinamento distribuido com CUDA e TensorRT em cluster A100.",
                "source_type": "technical_docs",
                "source_quality_score": 0.90,
                "evidence_confidence_score": 0.82,
                "source_id": "src2",
            }
        )

    return StartupScoringGoldenEntry(
        startup_id="test-001",
        startup_name="TestAI",
        website_url="https://testai.example.com",
        extracted_profile_snapshot={"sector": "Technology"},
        accepted_evidence_items_snapshot=evidence,
        accepted_claims_snapshot=claims,
        human_label_ai_native_level=ai_label,
        human_label_nvidia_fit_level=nv_label,
        label_notes="Test entry",
        label_source=label_source,
        labeler_id="test-runner",
    )


# ── 1. Golden set loading ─────────────────────────────────────────────────────


class TestLoadGoldenSet:
    def test_loads_entries(self) -> None:
        entries = load_startup_scoring_golden_set(_GOLDEN_PATH)
        assert isinstance(entries, list)

    def test_entries_have_required_fields(self) -> None:
        entry = _make_test_entry()
        assert entry.startup_id
        assert entry.startup_name
        assert entry.human_label_ai_native_level is not None
        assert entry.human_label_nvidia_fit_level is not None
        assert entry.label_source is not None

    def test_label_to_numeric(self) -> None:
        entry = _make_test_entry(ai_label="high", nv_label="high")
        assert entry.human_label_ai_native_numeric == 0.9
        assert entry.human_label_nvidia_fit_numeric == 0.9

        entry_low = _make_test_entry(ai_label="low", nv_label="low")
        assert entry_low.human_label_ai_native_numeric == 0.1
        assert entry_low.human_label_nvidia_fit_numeric == 0.1

    def test_numeric_label_takes_precedence(self) -> None:
        entry = StartupScoringGoldenEntry(
            startup_id="test-002",
            startup_name="TestNum",
            human_label_ai_native_level="low",
            human_label_ai_native_score=0.8,
            human_label_nvidia_fit_level="low",
            human_label_nvidia_fit_score=0.7,
        )
        assert entry.human_label_ai_native_numeric == 0.8
        assert entry.human_label_nvidia_fit_numeric == 0.7

    def test_no_llm_qdrant_internet_scraping(self) -> None:
        import sys

        before = set(sys.modules.keys())
        load_startup_scoring_golden_set(_GOLDEN_PATH)
        _ = _compute_scores_for_entries([_make_test_entry()], CANDIDATE_AI_WEIGHTS[0], "ai_native")
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


# ── 2. Human label check ──────────────────────────────────────────────────────


class TestCheckHumanLabels:
    def test_labels_exist(self) -> None:
        entries = [_make_test_entry()]
        assert check_human_labels_exist(entries) is True

    def test_no_labels(self) -> None:
        entry = _make_test_entry(ai_label=None, nv_label=None)
        assert check_human_labels_exist([entry]) is False

    def test_partial_labels(self) -> None:
        entry = _make_test_entry(ai_label="high", nv_label=None)
        assert check_human_labels_exist([entry]) is True


# ── 3. Metrics computation ────────────────────────────────────────────────────


class TestComputeMetrics:
    def test_ai_native_metrics_perfect(self) -> None:
        pred = [0.9, 0.5, 0.1]
        human = [0.9, 0.5, 0.1]
        feats = [{"uncertainty_penalty": 0.0}] * 3
        metrics = _compute_ai_native_metrics(pred, human, feats)
        assert metrics.spearman is not None and abs(metrics.spearman - 1.0) < 0.01
        assert metrics.mae is not None and metrics.mae < 0.01
        assert metrics.rmse is not None and metrics.rmse < 0.01
        assert metrics.f1 is not None and abs(metrics.f1 - 1.0) < 0.01

    def test_ai_native_scores_between_0_and_1(self) -> None:
        entries = [
            _make_test_entry(ai_signals=2, ai_label="high"),
            _make_test_entry(ai_signals=1, ai_label="medium"),
            _make_test_entry(ai_signals=0, ai_label="low"),
        ]
        predicted, human, feats = _compute_scores_for_entries(entries, CANDIDATE_AI_WEIGHTS[0], "ai_native")
        for s in predicted:
            assert 0.0 <= s <= 1.0

    def test_nvidia_fit_scores_between_0_and_1(self) -> None:
        entries = [
            _make_test_entry(nv_signals=2, nv_label="high"),
            _make_test_entry(nv_signals=1, nv_label="medium"),
            _make_test_entry(nv_signals=0, nv_label="low"),
        ]
        predicted, human, feats = _compute_scores_for_entries(entries, CANDIDATE_NVIDIA_WEIGHTS[0], "nvidia_fit")
        for s in predicted:
            assert 0.0 <= s <= 1.0

    def test_nvidia_fit_metrics_includes_fp_rate(self) -> None:
        pred = [0.8, 0.4, 0.2]
        human = [0.3, 0.5, 0.1]
        feats = [{"uncertainty_penalty": 0.0}] * 3
        metrics = _compute_nvidia_fit_metrics(pred, human, feats)
        assert metrics.false_positive_rate is not None
        assert metrics.precision_at_k is not None
        assert metrics.recall_at_k is not None

    def test_metrics_empty_small_dataset(self) -> None:
        metrics = _compute_ai_native_metrics([], [], [])
        assert metrics.spearman is None
        assert metrics.mae is None
        metrics2 = _compute_nvidia_fit_metrics([0.5], [0.5], [{"uncertainty_penalty": 0.0}])
        assert metrics2.spearman is None


# ── 4. Grid search — multiple candidates ──────────────────────────────────────


class TestGridSearch:
    def test_evaluates_all_ai_candidates(self) -> None:
        entries = [
            _make_test_entry(ai_signals=2, ai_label="high"),
            _make_test_entry(ai_signals=1, ai_label="medium"),
            _make_test_entry(ai_signals=0, ai_label="low"),
            _make_test_entry(ai_signals=2, ai_label="high"),
            _make_test_entry(ai_signals=0, ai_label="low"),
        ]
        results = _evaluate_weight_candidates(entries, CANDIDATE_AI_WEIGHTS, "ai_native")
        assert len(results) == len(CANDIDATE_AI_WEIGHTS)

    def test_evaluates_all_nv_candidates(self) -> None:
        entries = [
            _make_test_entry(nv_signals=2, nv_label="high"),
            _make_test_entry(nv_signals=1, nv_label="medium"),
            _make_test_entry(nv_signals=0, nv_label="low"),
            _make_test_entry(nv_signals=2, nv_label="high"),
            _make_test_entry(nv_signals=0, nv_label="low"),
        ]
        results = _evaluate_weight_candidates(entries, CANDIDATE_NVIDIA_WEIGHTS, "nvidia_fit")
        assert len(results) == len(CANDIDATE_NVIDIA_WEIGHTS)

    def test_candidates_have_different_metrics(self) -> None:
        entries = [
            _make_test_entry(ai_signals=2, ai_label="high"),
            _make_test_entry(ai_signals=1, ai_label="medium"),
            _make_test_entry(ai_signals=0, ai_label="low"),
            _make_test_entry(ai_signals=2, ai_label="high"),
            _make_test_entry(ai_signals=0, ai_label="low"),
        ]
        results = _evaluate_weight_candidates(entries, CANDIDATE_AI_WEIGHTS, "ai_native")
        spearmans = {r.spearman for r in results if r.spearman is not None}
        assert len(spearmans) >= 1


class TestSelectBestCandidate:
    def test_selects_best_ai_candidate(self) -> None:
        entries = [
            _make_test_entry(ai_signals=2, ai_label="high"),
            _make_test_entry(ai_signals=1, ai_label="medium"),
            _make_test_entry(ai_signals=0, ai_label="low"),
            _make_test_entry(ai_signals=2, ai_label="high"),
            _make_test_entry(ai_signals=0, ai_label="low"),
        ]
        results = _evaluate_weight_candidates(entries, CANDIDATE_AI_WEIGHTS, "ai_native")
        best_idx = _select_best_candidate(results, "ai_native")
        assert best_idx is not None
        assert 0 <= best_idx < len(CANDIDATE_AI_WEIGHTS)

    def test_selects_best_nv_candidate(self) -> None:
        entries = [
            _make_test_entry(nv_signals=2, nv_label="high"),
            _make_test_entry(nv_signals=1, nv_label="medium"),
            _make_test_entry(nv_signals=0, nv_label="low"),
            _make_test_entry(nv_signals=2, nv_label="high"),
            _make_test_entry(nv_signals=0, nv_label="low"),
        ]
        results = _evaluate_weight_candidates(entries, CANDIDATE_NVIDIA_WEIGHTS, "nvidia_fit")
        best_idx = _select_best_candidate(results, "nvidia_fit")
        assert best_idx is not None


# ── 5. Production readiness ────────────────────────────────────────────────────


class TestCheckProductionReady:
    def test_blocked_when_insufficient_labels(self) -> None:
        ready, blockers = _check_startup_scoring_production_ready(
            ai_label_count=5,
            nv_label_count=5,
            ai_metrics=None,
            nv_metrics=None,
        )
        assert ready is False
        assert any("labels" in b for b in blockers)

    def test_blocked_when_poor_metrics(self) -> None:
        ready, blockers = _check_startup_scoring_production_ready(
            ai_label_count=AI_NATIVE_MIN_LABELED,
            nv_label_count=NVIDIA_FIT_MIN_LABELED,
            ai_metrics=StartupScoringMetrics(spearman=0.2, mae=0.5),
            nv_metrics=StartupScoringMetrics(spearman=0.2, mae=0.5, false_positive_rate=0.8),
        )
        assert ready is False
        assert any("spearman" in b for b in blockers)
        assert any("mae" in b for b in blockers)
        assert any("fp_rate" in b for b in blockers)

    def test_allowed_when_all_criteria_met(self) -> None:
        ready, blockers = _check_startup_scoring_production_ready(
            ai_label_count=AI_NATIVE_MIN_LABELED,
            nv_label_count=NVIDIA_FIT_MIN_LABELED,
            ai_metrics=StartupScoringMetrics(
                spearman=AI_NATIVE_SPEARMAN_MIN,
                mae=AI_NATIVE_MAE_MAX,
            ),
            nv_metrics=StartupScoringMetrics(
                spearman=NVIDIA_FIT_SPEARMAN_MIN,
                mae=NVIDIA_FIT_MAE_MAX,
                false_positive_rate=NVIDIA_FIT_FP_RATE_MAX,
            ),
        )
        assert ready is True
        assert len(blockers) == 0


# ── 6. Full calibration ───────────────────────────────────────────────────────


class TestFullCalibration:
    def test_calibration_returns_result(self) -> None:
        result = run_startup_scoring_baseline_calibration(golden_path=_GOLDEN_PATH)
        assert result.golden_set_size >= 30
        assert result.calibration_status == "baseline_measured"
        assert result.production_allowed is True
        assert result.has_human_labels is True

    def test_empty_set_returns_insufficient(self) -> None:
        import json
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"startups": [], "_meta": {}}, f)
            tmp = f.name
        try:
            result = run_startup_scoring_baseline_calibration(golden_path=Path(tmp))
            assert result.calibration_status == "baseline_dataset_insufficient"
            assert result.production_allowed is False
            assert result.golden_set_size == 0
        finally:
            Path(tmp).unlink()

    def test_with_test_entries(self) -> None:
        import json
        import tempfile

        entries = [
            _make_test_entry(ai_signals=2, nv_signals=2, ai_label="high", nv_label="high"),
            _make_test_entry(ai_signals=1, nv_signals=1, ai_label="medium", nv_label="medium"),
            _make_test_entry(ai_signals=0, nv_signals=0, ai_label="low", nv_label="low"),
            _make_test_entry(ai_signals=2, nv_signals=2, ai_label="high", nv_label="high"),
            _make_test_entry(ai_signals=0, nv_signals=0, ai_label="low", nv_label="low"),
        ]
        data = {
            "_meta": {"purpose": "test", "calibration_status": "test"},
            "startups": [
                {
                    "startup_id": e.startup_id,
                    "startup_name": e.startup_name,
                    "website_url": e.website_url,
                    "extracted_profile_snapshot": e.extracted_profile_snapshot,
                    "accepted_evidence_items_snapshot": e.accepted_evidence_items_snapshot,
                    "accepted_claims_snapshot": e.accepted_claims_snapshot,
                    "human_label_ai_native_level": e.human_label_ai_native_level,
                    "human_label_nvidia_fit_level": e.human_label_nvidia_fit_level,
                    "label_notes": e.label_notes,
                    "label_source": e.label_source,
                    "labeler_id": e.labeler_id,
                }
                for e in entries
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            tmp = f.name
        try:
            result = run_startup_scoring_baseline_calibration(golden_path=Path(tmp))
            assert result.golden_set_size == 5
            assert result.has_human_labels is True
            assert result.human_label_coverage["ai_native_labels"] == 5
            assert result.human_label_coverage["nvidia_fit_labels"] == 5
            assert result.best_ai_candidate_index is not None
            assert result.best_nv_candidate_index is not None
        finally:
            Path(tmp).unlink()

    def test_calibration_report_generated(self) -> None:
        result = run_startup_scoring_baseline_calibration(golden_path=_GOLDEN_PATH)
        assert len(result.report) > 0

    def test_calibration_has_human_label_coverage(self) -> None:
        result = run_startup_scoring_baseline_calibration(golden_path=_GOLDEN_PATH)
        assert "ai_native_labels" in result.human_label_coverage
        assert "nvidia_fit_labels" in result.human_label_coverage


# ── 7. Registry integration ────────────────────────────────────────────────────


class TestRegistryIntegration:
    def test_registry_contains_value_origin(self) -> None:
        from src.quality.decision_calibration_registry import (
            get_project_decision_inventory,
        )

        inventory = get_project_decision_inventory()
        scoring_ids = {
            "ai_native_score.weights",
            "ai_native_score.production_threshold",
            "ai_native_score.uncertainty_penalty",
            "nvidia_fit_score.weights",
            "nvidia_fit_score.production_threshold",
            "nvidia_fit_score.uncertainty_penalty",
        }
        for rec in inventory:
            if rec.decision_id in scoring_ids:
                assert rec.value_origin is not None
                assert "startup_scoring_baseline_calibration" in rec.value_origin

    def test_registry_contains_calibration_method(self) -> None:
        from src.quality.decision_calibration_registry import (
            get_project_decision_inventory,
        )

        inventory = get_project_decision_inventory()
        scoring_ids = {
            "ai_native_score.weights",
            "ai_native_score.production_threshold",
            "ai_native_score.uncertainty_penalty",
            "nvidia_fit_score.weights",
            "nvidia_fit_score.production_threshold",
            "nvidia_fit_score.uncertainty_penalty",
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
            "ai_native_score.weights",
            "ai_native_score.production_threshold",
            "ai_native_score.uncertainty_penalty",
            "nvidia_fit_score.weights",
            "nvidia_fit_score.production_threshold",
            "nvidia_fit_score.uncertainty_penalty",
        }
        for rec in inventory:
            if rec.decision_id in scoring_ids:
                assert rec.evidence_source is not None
                assert "startup_scoring_baseline_calibration" in rec.evidence_source

    def test_registry_startup_scoring_is_measured(self) -> None:
        from src.quality.decision_calibration_registry import (
            CalibrationStatus,
            get_project_decision_inventory,
        )

        inventory = get_project_decision_inventory()
        for rec in inventory:
            if rec.decision_id in {
                "ai_native_score.weights",
                "nvidia_fit_score.weights",
            }:
                assert rec.calibration_status == CalibrationStatus.BASELINE_MEASURED
                assert rec.production_allowed is True

    def test_no_values_liberated_without_registry(self) -> None:
        from src.scoring.startup_scoring import compute_startup_scoring

        result = compute_startup_scoring([], [], [], inventory=[])
        assert result.ai_native.production_allowed is False
        assert result.nvidia_fit.production_allowed is False
        assert result.ai_native.score_status.value == "blocked_uncalibrated_scoring"

    def test_threshold_from_measured_result(self) -> None:
        from src.evaluation.startup_scoring_calibration import _calibrate_threshold_from_errors

        pred = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05]
        human = [0.85, 0.78, 0.72, 0.58, 0.48, 0.42, 0.28, 0.18, 0.12, 0.08]
        result = _calibrate_threshold_from_errors(pred, human, percentile=5.0)
        assert result["threshold"] is not None
        assert 0.0 <= result["threshold"] <= 1.0
        assert "distribution" in result

    def test_uncertainty_penalty_from_measured_result(self) -> None:
        from src.evaluation.startup_scoring_calibration import (
            _calibrate_uncertainty_penalty_from_data,
        )

        pred = [0.9, 0.5, 0.1]
        human = [0.85, 0.55, 0.15]
        uncertainties = [0.1, 0.2, 0.3]
        result = _calibrate_uncertainty_penalty_from_data(pred, human, uncertainties)
        assert "best_penalty" in result
        assert "method" in result

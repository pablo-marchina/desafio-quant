"""Tests for startup scoring — ai_native_score and nvidia_fit_score."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.quality.decision_calibration_registry import (
    CalibrationMethod,
    CalibrationStatus,
    DecisionCalibrationRecord,
    DecisionType,
    get_project_decision_inventory,
)
from src.scoring.startup_scoring import (
    AI_NATIVE_THRESHOLD_DECISION_ID,
    AI_NATIVE_UNCERTAINTY_DECISION_ID,
    AI_NATIVE_WEIGHTS_DECISION_ID,
    NVIDIA_FIT_THRESHOLD_DECISION_ID,
    NVIDIA_FIT_UNCERTAINTY_DECISION_ID,
    NVIDIA_FIT_WEIGHTS_DECISION_ID,
    REQUIRED_CALIBRATION_DECISIONS,
    NvidiaFitFeatures,
    ScoreComponent,
    ScoreStatus,
    StartupScoreResult,
    StartupScoringFeatures,
    build_scoring_summary,
    compute_startup_scoring,
    extract_ai_native_features,
    extract_nvidia_fit_features,
)

# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def calibrated_inventory() -> list[DecisionCalibrationRecord]:
    _now = datetime(2026, 6, 18, tzinfo=UTC)
    ai_weights: dict[str, float] = {
        "ai_signal_count": 0.15,
        "ai_signal_source_coverage": 0.10,
        "technical_ai_term_count": 0.10,
        "product_ai_claim_count": 0.10,
        "accepted_ai_evidence_count": 0.10,
        "ai_claim_support_ratio": 0.10,
        "evidence_confidence_mean_for_ai_claims": 0.10,
        "source_quality_mean_for_ai_sources": 0.10,
        "technical_depth_signal_count": 0.05,
        "model_or_ml_infrastructure_signal_count": 0.05,
        "uncertainty_penalty": 0.05,
    }
    nv_weights: dict[str, float] = {
        "gpu_compute_signal_count": 0.10,
        "cuda_or_acceleration_signal_count": 0.10,
        "inference_or_training_signal_count": 0.10,
        "computer_vision_signal_count": 0.08,
        "genai_llm_signal_count": 0.10,
        "data_pipeline_signal_count": 0.08,
        "nvidia_keyword_signal_count": 0.08,
        "nvidia_relevant_industry_signal_count": 0.08,
        "accepted_nvidia_fit_evidence_count": 0.08,
        "rag_context_alignment_count": 0.05,
        "evidence_confidence_mean_for_nvidia_claims": 0.05,
        "implementation_complexity_proxy": 0.05,
        "uncertainty_penalty": 0.05,
    }
    return [
        DecisionCalibrationRecord(
            decision_id=AI_NATIVE_WEIGHTS_DECISION_ID,
            decision_name="Test AI Native Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=ai_weights,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            last_calibrated_at=_now,
        ),
        DecisionCalibrationRecord(
            decision_id=AI_NATIVE_THRESHOLD_DECISION_ID,
            decision_name="Test AI Native Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.3,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            last_calibrated_at=_now,
        ),
        DecisionCalibrationRecord(
            decision_id=AI_NATIVE_UNCERTAINTY_DECISION_ID,
            decision_name="Test AI Native Uncertainty",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.15,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            last_calibrated_at=_now,
        ),
        DecisionCalibrationRecord(
            decision_id=NVIDIA_FIT_WEIGHTS_DECISION_ID,
            decision_name="Test NVIDIA Fit Weights",
            decision_type=DecisionType.WEIGHT,
            current_value=nv_weights,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            last_calibrated_at=_now,
        ),
        DecisionCalibrationRecord(
            decision_id=NVIDIA_FIT_THRESHOLD_DECISION_ID,
            decision_name="Test NVIDIA Fit Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.3,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            last_calibrated_at=_now,
        ),
        DecisionCalibrationRecord(
            decision_id=NVIDIA_FIT_UNCERTAINTY_DECISION_ID,
            decision_name="Test NVIDIA Fit Uncertainty",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.15,
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
            last_calibrated_at=_now,
        ),
    ]


@pytest.fixture
def empty_claims() -> list[dict[str, Any]]:
    return []


@pytest.fixture
def sample_claims() -> list[dict[str, Any]]:
    return [
        {
            "claim_text": "Startup usa inteligencia artificial para analise de creditos",
            "criticality": "critical",
            "support_status": "supported",
            "confidence": "medium",
        },
        {
            "claim_text": "Nosso modelo de deep learning foi treinado com GPU NVIDIA A100",
            "criticality": "normal",
            "support_status": "supported",
            "confidence": "medium",
        },
        {
            "claim_text": "Plataforma de ia generativa para chatbots empresariais",
            "criticality": "normal",
            "support_status": "supported",
            "confidence": "high",
        },
        {
            "claim_text": "API de recomendacao baseada em machine learning",
            "criticality": "normal",
            "support_status": "supported",
            "confidence": "high",
        },
        {
            "claim_text": "Processo seletivo para engenheiro de dados",
            "criticality": "normal",
            "support_status": "unsupported",
            "confidence": "low",
        },
    ]


@pytest.fixture
def sample_evidence_items() -> list[dict[str, Any]]:
    return [
        {
            "text": "A startup usa inteligencia artificial e PyTorch para processamento de imagens com GPU.",
            "source_type": "official_website",
            "source_quality_score": 0.85,
            "evidence_confidence_score": 0.78,
            "source_id": "src1",
        },
        {
            "text": "A empresa utiliza machine learning para deteccao de fraude com inferencia em tempo real.",
            "source_type": "news",
            "source_quality_score": 0.72,
            "evidence_confidence_score": 0.65,
            "source_id": "src2",
        },
        {
            "text": "Plataforma de ia generativa usando transformers e fine-tuning com CUDA.",
            "source_type": "blog",
            "source_quality_score": 0.68,
            "evidence_confidence_score": 0.60,
            "source_id": "src3",
        },
        {
            "text": "Cluster Kubernetes com orchestracao de containers para servicos de IA.",
            "source_type": "technical_docs",
            "source_quality_score": 0.90,
            "evidence_confidence_score": 0.82,
            "source_id": "src4",
        },
        {
            "text": "Empresa contratou engenheiro de software senior.",
            "source_type": "jobs",
            "source_quality_score": 0.55,
            "evidence_confidence_score": 0.45,
            "source_id": "src5",
        },
    ]


@pytest.fixture
def sample_accepted_items(sample_evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in sample_evidence_items if item["source_quality_score"] >= 0.6]


# ── Feature extraction tests ────────────────────────────────────────────────────


class TestExtractAiNativeFeatures:
    def test_extracts_features_with_data(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
    ) -> None:
        features = extract_ai_native_features(sample_claims, sample_accepted_items, sample_evidence_items)
        assert isinstance(features, StartupScoringFeatures)
        assert features.ai_signal_count >= 3
        assert features.ai_signal_source_coverage >= 0.0
        assert features.technical_ai_term_count >= 1
        assert features.product_ai_claim_count >= 0
        assert features.accepted_ai_evidence_count >= 1
        assert features.ai_claim_support_ratio >= 0.0
        assert features.evidence_confidence_mean_for_ai_claims >= 0.0
        assert features.source_quality_mean_for_ai_sources >= 0.0
        assert features.technical_depth_signal_count >= 1
        assert features.model_or_ml_infrastructure_signal_count >= 1
        assert features.uncertainty_penalty >= 0.0

    def test_empty_claims_returns_zero_features(self) -> None:
        features = extract_ai_native_features([], [], [])
        assert isinstance(features, StartupScoringFeatures)
        assert features.ai_signal_count == 0
        assert features.ai_signal_source_coverage == 0.0
        assert features.accepted_ai_evidence_count == 0
        assert features.uncertainty_penalty == 1.0


class TestExtractNvidiaFitFeatures:
    def test_extracts_features_with_data(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
    ) -> None:
        features = extract_nvidia_fit_features(sample_claims, sample_accepted_items, sample_evidence_items)
        assert isinstance(features, NvidiaFitFeatures)
        assert features.gpu_compute_signal_count >= 1
        assert features.inference_or_training_signal_count >= 1
        assert features.nvidia_keyword_signal_count >= 1
        assert features.evidence_confidence_mean_for_nvidia_claims >= 0.0

    def test_with_rag_context(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
    ) -> None:
        rag = ["NVIDIA CUDA para aceleracao de treinamento", "Outro contexto qualquer"]
        features = extract_nvidia_fit_features(
            sample_claims, sample_accepted_items, sample_evidence_items, rag_contexts=rag
        )
        assert features.rag_context_alignment_count >= 1


# ── Calibration gating tests ────────────────────────────────────────────────────


class TestComputeStartupScoring:
    def test_computes_ai_native_features(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
        calibrated_inventory: list[DecisionCalibrationRecord],
    ) -> None:
        result = compute_startup_scoring(
            sample_claims,
            sample_accepted_items,
            sample_evidence_items,
            inventory=calibrated_inventory,
        )
        assert isinstance(result, StartupScoreResult)
        assert isinstance(result.ai_native, ScoreComponent)
        assert result.ai_native.score_name == "ai_native_score"
        assert result.ai_native.features is not None
        assert "ai_signal_count" in result.ai_native.features

    def test_computes_nvidia_fit_features(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
        calibrated_inventory: list[DecisionCalibrationRecord],
    ) -> None:
        result = compute_startup_scoring(
            sample_claims,
            sample_accepted_items,
            sample_evidence_items,
            inventory=calibrated_inventory,
        )
        assert isinstance(result.nvidia_fit, ScoreComponent)
        assert result.nvidia_fit.score_name == "nvidia_fit_score"
        assert "gpu_compute_signal_count" in result.nvidia_fit.features

    def test_blocks_when_ai_native_weights_missing(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
    ) -> None:
        empty_inventory: list[DecisionCalibrationRecord] = []
        result = compute_startup_scoring(
            sample_claims, sample_accepted_items, sample_evidence_items, inventory=empty_inventory
        )
        assert result.ai_native.score_status == ScoreStatus.BLOCKED_UNCALIBRATED_SCORING
        assert result.ai_native.production_allowed is False
        assert len(result.ai_native.blockers) > 0

    def test_blocks_when_nvidia_fit_weights_missing(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
    ) -> None:
        empty_inventory: list[DecisionCalibrationRecord] = []
        result = compute_startup_scoring(
            sample_claims, sample_accepted_items, sample_evidence_items, inventory=empty_inventory
        )
        assert result.nvidia_fit.score_status == ScoreStatus.BLOCKED_UNCALIBRATED_SCORING
        assert result.nvidia_fit.production_allowed is False
        assert len(result.nvidia_fit.blockers) > 0

    def test_blocks_when_thresholds_missing(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
    ) -> None:
        partial_inventory: list[DecisionCalibrationRecord] = [
            DecisionCalibrationRecord(
                decision_id=AI_NATIVE_WEIGHTS_DECISION_ID,
                decision_name="Test Weights",
                decision_type=DecisionType.WEIGHT,
                current_value={"ai_signal_count": 1.0},
                calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
                calibration_status=CalibrationStatus.CALIBRATED,
                production_allowed=True,
            ),
        ]
        result = compute_startup_scoring(
            sample_claims, sample_accepted_items, sample_evidence_items, inventory=partial_inventory
        )
        assert result.ai_native.score_status == ScoreStatus.BLOCKED_UNCALIBRATED_SCORING
        assert result.ai_native.production_allowed is False

    def test_calibrated_scores_are_between_0_and_1(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
        calibrated_inventory: list[DecisionCalibrationRecord],
    ) -> None:
        result = compute_startup_scoring(
            sample_claims,
            sample_accepted_items,
            sample_evidence_items,
            inventory=calibrated_inventory,
        )
        assert 0.0 <= result.ai_native.score_value <= 1.0
        assert 0.0 <= result.nvidia_fit.score_value <= 1.0

    def test_score_result_contains_all_metadata(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
        calibrated_inventory: list[DecisionCalibrationRecord],
    ) -> None:
        result = compute_startup_scoring(
            sample_claims,
            sample_accepted_items,
            sample_evidence_items,
            inventory=calibrated_inventory,
        )
        for component in [result.ai_native, result.nvidia_fit]:
            assert component.score_name
            assert isinstance(component.features, dict)
            assert len(component.features) > 0
            assert isinstance(component.weights, dict)
            assert isinstance(component.thresholds, dict)
            assert isinstance(component.calibration_decision_ids, list)
            assert len(component.calibration_decision_ids) > 0
            assert component.uncertainty >= 0.0
            assert component.explanation

    def test_unsupported_critical_claim_generates_failed_summary(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
        calibrated_inventory: list[DecisionCalibrationRecord],
    ) -> None:
        result = compute_startup_scoring(
            sample_claims,
            sample_accepted_items,
            sample_evidence_items,
            inventory=calibrated_inventory,
        )
        summary = build_scoring_summary(result, unsupported_critical_claims_count=1)
        assert summary.scoring_status == "failed"
        assert summary.production_allowed is False
        assert len(summary.blockers) > 0


class TestBuildScoringSummary:
    def test_metrics_are_calculated(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
        calibrated_inventory: list[DecisionCalibrationRecord],
    ) -> None:
        result = compute_startup_scoring(
            sample_claims,
            sample_accepted_items,
            sample_evidence_items,
            inventory=calibrated_inventory,
        )
        summary = build_scoring_summary(
            result,
            accepted_evidence_count=3,
            rejected_evidence_count=2,
            accepted_claim_count=4,
            average_evidence_confidence=0.75,
            average_source_quality=0.80,
        )
        metrics = summary.score_metrics
        assert "ai_native_feature_coverage" in metrics
        assert "nvidia_fit_feature_coverage" in metrics
        assert metrics["accepted_evidence_count"] == 3
        assert metrics["rejected_evidence_count"] == 2
        assert metrics["accepted_claim_count"] == 4
        assert metrics["average_evidence_confidence"] == 0.75
        assert metrics["average_source_quality"] == 0.80
        assert "scoring_uncertainty" in metrics
        assert "calibrated_decision_count" in metrics
        assert "missing_calibration_count" in metrics
        assert "unsupported_critical_claims_count" in metrics


# ── Real inventory test ─────────────────────────────────────────────────────────


class TestWithRealInventory:
    def test_passes_with_real_inventory(self) -> None:
        real_inventory = get_project_decision_inventory()
        result = compute_startup_scoring([], [], [], inventory=real_inventory)
        assert result.ai_native.production_allowed is True
        assert result.nvidia_fit.production_allowed is True

    def test_required_decisions_exist_in_registry(self) -> None:
        real_inventory = get_project_decision_inventory()
        existing_ids = {r.decision_id for r in real_inventory}
        for dec_id in REQUIRED_CALIBRATION_DECISIONS:
            assert dec_id in existing_ids, f"{dec_id} not found in registry"


# ── No LLM/Qdrant/internet/scraping check ────────────────────────────────────────


class TestNoExternalCalls:
    def test_extraction_is_deterministic(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
    ) -> None:
        f1 = extract_ai_native_features(sample_claims, sample_accepted_items, sample_evidence_items)
        f2 = extract_ai_native_features(sample_claims, sample_accepted_items, sample_evidence_items)
        assert f1.model_dump() == f2.model_dump()

    def test_compute_is_deterministic(
        self,
        sample_claims: list[dict[str, Any]],
        sample_evidence_items: list[dict[str, Any]],
        sample_accepted_items: list[dict[str, Any]],
        calibrated_inventory: list[DecisionCalibrationRecord],
    ) -> None:
        r1 = compute_startup_scoring(
            sample_claims,
            sample_accepted_items,
            sample_evidence_items,
            inventory=calibrated_inventory,
        )
        r2 = compute_startup_scoring(
            sample_claims,
            sample_accepted_items,
            sample_evidence_items,
            inventory=calibrated_inventory,
        )
        assert r1.ai_native.score_value == r2.ai_native.score_value
        assert r1.nvidia_fit.score_value == r2.nvidia_fit.score_value

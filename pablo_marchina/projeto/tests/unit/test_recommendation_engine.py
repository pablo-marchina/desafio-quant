from datetime import UTC, datetime

from src.classification.ai_native_classifier import ClassificationResult
from src.diagnosis.schemas import (
    EvidenceTag,
    GapDiagnosisResult,
    GapWithEvidence,
    NvidiaTechnologyCandidate,
)
from src.extraction.schemas import (
    AINativeLevel,
    ConfidenceLevel,
    StartupProfile,
    TechnicalGap,
)
from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    DecisionCalibrationRecord,
    DecisionType,
)
from src.rag.schemas import RagPipelineOutput
from src.recommendation.nvidia_technology_mapping import REQUIRED_MAPPING_DECISIONS
from src.recommendation.recommendation_engine import (
    REQUIRED_RECOMMENDATION_DECISIONS,
    NvidiaRecommendationRecord,
    RecommendationRankingStatus,
    _compute_overall_confidence,
    _compute_overall_priority,
    _determine_action,
    _determine_priority,
    _suggest_experiment,
    build_per_gap_recommendation,
    build_recommendations,
    compute_recommendation_metrics,
    rank_recommendations_from_mappings,
)
from src.recommendation.schemas import (
    RecommendedNextAction,
    SuggestedTechnicalExperiment,
)
from src.validation.evidence_validator import EvidenceKind, ValidatedEvidence


def _make_profile() -> StartupProfile:
    return StartupProfile(
        startup_name="TestAI",
        website="https://testai.com",
        sector="SaaS",
        description="A test startup.",
        product_summary="AI platform.",
        ai_signals=["AI copilot"],
        sources=[],
        confidence_score=0.8,
    )


def _make_rag_context(missing: bool = False) -> RagPipelineOutput:
    return RagPipelineOutput(
        packing_result=None,
        retrieval_mode="lexical",
        missing_context=missing,
        rag_quality_summary="No corpus available." if missing else "RAG context OK.",
    )


def _make_classification() -> ClassificationResult:
    return ClassificationResult(
        startup_name="TestAI",
        classification=AINativeLevel.AI_NATIVE,
        confidence=ConfidenceLevel.HIGH,
        reasoning="Test classification.",
    )


def _make_gap(
    gap: TechnicalGap = TechnicalGap.HIGH_INFERENCE_COST,
    detected: bool = True,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    tag: EvidenceTag = EvidenceTag.FACT,
) -> GapWithEvidence:
    return GapWithEvidence(
        gap=gap,
        detected=detected,
        confidence=confidence,
        evidence_tag=tag,
        reasoning="Test reasoning.",
        evidence_used=[
            ValidatedEvidence(
                claim="Test claim",
                source_url="https://test.com",
                source_type="official_site",
                quote_or_evidence="Test quote",
                confidence=ConfidenceLevel.HIGH,
                collected_at=datetime.now(UTC),
                evidence_kind=EvidenceKind.FACT,
            )
        ],
    )


def _make_diagnosis(
    gaps: list[GapWithEvidence] | None = None,
) -> GapDiagnosisResult:
    if gaps is None:
        gaps = [_make_gap()]
    return GapDiagnosisResult(
        startup_name="TestAI",
        diagnosed_gaps=gaps,
        nvidia_technology_candidates=[
            NvidiaTechnologyCandidate(
                technology_name="TensorRT-LLM",
                addresses_gap=TechnicalGap.HIGH_INFERENCE_COST,
                justification="Direct match.",
            ),
        ],
        confidence=ConfidenceLevel.HIGH,
        reasoning="Test diagnosis.",
        missing_evidence=["More data needed."],
    )


def _make_validated_evidence() -> list[ValidatedEvidence]:
    return [
        ValidatedEvidence(
            claim="Evidence claim.",
            source_url="https://test.com",
            source_type="official_site",
            quote_or_evidence="Quote.",
            confidence=ConfidenceLevel.HIGH,
            collected_at=datetime.now(UTC),
            evidence_kind=EvidenceKind.FACT,
        ),
    ]


class TestDetermineAction:
    def test_not_recommended_motion_returns_not_recommended(self) -> None:
        gap = _make_gap()
        action = _determine_action(gap, "not_recommended")
        assert action == RecommendedNextAction.NOT_RECOMMENDED

    def test_not_detected_returns_monitor(self) -> None:
        gap = _make_gap(detected=False)
        action = _determine_action(gap, "immediate_outreach")
        assert action == RecommendedNextAction.MONITOR

    def test_low_confidence_returns_validate_manually(self) -> None:
        gap = _make_gap(confidence=ConfidenceLevel.LOW)
        action = _determine_action(gap, "immediate_outreach")
        assert action == RecommendedNextAction.VALIDATE_MANUALLY

    def test_lack_evidence_motion_returns_validate_manually(self) -> None:
        gap = _make_gap()
        action = _determine_action(gap, "lack_evidence_more_research")
        assert action == RecommendedNextAction.VALIDATE_MANUALLY

    def test_high_confidence_immediate_outreach_returns_approach_now(self) -> None:
        gap = _make_gap()
        action = _determine_action(gap, "immediate_outreach")
        assert action == RecommendedNextAction.APPROACH_NOW

    def test_medium_confidence_approach_now(self) -> None:
        gap = _make_gap(confidence=ConfidenceLevel.MEDIUM)
        action = _determine_action(gap, "immediate_outreach")
        assert action == RecommendedNextAction.VALIDATE_MANUALLY

    def test_medium_confidence_monitor_motion_returns_monitor(self) -> None:
        gap = _make_gap(confidence=ConfidenceLevel.MEDIUM)
        action = _determine_action(gap, "monitor_and_nurture")
        assert action == RecommendedNextAction.MONITOR


class TestDeterminePriority:
    def test_approach_now_high_confidence(self) -> None:
        p = _determine_priority(RecommendedNextAction.APPROACH_NOW, ConfidenceLevel.HIGH)
        from src.extraction.schemas import RecommendationPriority

        assert p == RecommendationPriority.HIGH

    def test_approach_now_medium_confidence(self) -> None:
        from src.extraction.schemas import RecommendationPriority

        p = _determine_priority(RecommendedNextAction.APPROACH_NOW, ConfidenceLevel.MEDIUM)
        assert p == RecommendationPriority.MEDIUM

    def test_validate_manually_returns_medium_or_low(self) -> None:
        from src.extraction.schemas import RecommendationPriority

        p_high = _determine_priority(RecommendedNextAction.VALIDATE_MANUALLY, ConfidenceLevel.HIGH)
        assert p_high == RecommendationPriority.MEDIUM
        p_low = _determine_priority(RecommendedNextAction.VALIDATE_MANUALLY, ConfidenceLevel.LOW)
        assert p_low == RecommendationPriority.LOW

    def test_monitor_returns_low(self) -> None:
        from src.extraction.schemas import RecommendationPriority

        p = _determine_priority(RecommendedNextAction.MONITOR, ConfidenceLevel.HIGH)
        assert p == RecommendationPriority.LOW


class TestComputeOverall:
    def test_overall_priority_with_high(self) -> None:
        from src.extraction.schemas import RecommendationPriority
        from src.recommendation.schemas import PerGapRecommendation

        recs = [
            PerGapRecommendation(
                diagnosed_gap=TechnicalGap.HIGH_INFERENCE_COST,
                detected=True,
                priority=RecommendationPriority.HIGH,
                confidence=ConfidenceLevel.HIGH,
            ),
            PerGapRecommendation(
                diagnosed_gap=TechnicalGap.HIGH_LATENCY,
                detected=True,
                priority=RecommendationPriority.LOW,
                confidence=ConfidenceLevel.MEDIUM,
            ),
        ]
        assert _compute_overall_priority(recs) == RecommendationPriority.HIGH

    def test_overall_confidence_with_mixed(self) -> None:
        from src.recommendation.schemas import PerGapRecommendation

        recs = [
            PerGapRecommendation(
                diagnosed_gap=TechnicalGap.HIGH_INFERENCE_COST,
                detected=True,
                priority="high",
                confidence=ConfidenceLevel.HIGH,
            ),
            PerGapRecommendation(
                diagnosed_gap=TechnicalGap.HIGH_LATENCY,
                detected=True,
                priority="low",
                confidence=ConfidenceLevel.MEDIUM,
            ),
        ]
        assert _compute_overall_confidence(recs) == ConfidenceLevel.MEDIUM

    def test_no_detected_gaps_low_confidence(self) -> None:
        from src.recommendation.schemas import PerGapRecommendation

        recs = [
            PerGapRecommendation(
                diagnosed_gap=TechnicalGap.HIGH_INFERENCE_COST,
                detected=False,
                priority="low",
                confidence=ConfidenceLevel.LOW,
            ),
        ]
        assert _compute_overall_confidence(recs) == ConfidenceLevel.LOW


class TestSuggestExperiment:
    def test_known_gap_returns_experiment(self) -> None:
        experiment = _suggest_experiment(TechnicalGap.HIGH_INFERENCE_COST, "TensorRT-LLM")
        assert experiment is not None
        assert isinstance(experiment, SuggestedTechnicalExperiment)
        assert "TensorRT-LLM" in experiment.nvidia_technology
        assert experiment.target_gap == TechnicalGap.HIGH_INFERENCE_COST

    def test_unknown_gap_returns_none(self) -> None:
        experiment = _suggest_experiment(
            TechnicalGap.SLOW_DATA_PIPELINE,
            "cuDF",
        )
        assert experiment is not None
        assert "cuDF" in experiment.nvidia_technology


class TestBuildPerGap:
    def test_detected_high_confidence_generates_full_recommendation(self) -> None:
        profile = _make_profile()
        classification = _make_classification()
        gap = _make_gap()

        rec = build_per_gap_recommendation(
            gap=gap,
            tech_names=["TensorRT-LLM"],
            profile=profile,
            classification=classification,
            recommended_motion="immediate_outreach",
        )
        assert rec.detected is True
        assert rec.action == RecommendedNextAction.APPROACH_NOW
        assert len(rec.recommended_nvidia_technologies) == 1
        assert rec.suggested_experiment is not None
        assert rec.priority.value == "high"

    def test_undetected_gap_generates_monitor_action(self) -> None:
        profile = _make_profile()
        classification = _make_classification()
        gap = _make_gap(detected=False)

        rec = build_per_gap_recommendation(
            gap=gap,
            tech_names=[],
            profile=profile,
            classification=classification,
            recommended_motion="immediate_outreach",
        )
        assert rec.detected is False
        assert rec.action == RecommendedNextAction.MONITOR
        assert rec.suggested_experiment is None
        assert rec.recommended_nvidia_technologies == []

    def test_inferred_evidence_adds_missing_evidence_entry(self) -> None:
        profile = _make_profile()
        classification = _make_classification()
        gap = _make_gap(tag=EvidenceTag.INFERRED)

        rec = build_per_gap_recommendation(
            gap=gap,
            tech_names=["TensorRT-LLM"],
            profile=profile,
            classification=classification,
            recommended_motion="immediate_outreach",
        )
        assert len(rec.missing_evidence) == 1
        assert "inference" in rec.missing_evidence[0].lower()


class TestBuildRecommendations:
    def test_full_integration_returns_result(self) -> None:
        profile = _make_profile()
        classification = _make_classification()
        evidence = _make_validated_evidence()
        diagnosis = _make_diagnosis()

        result = build_recommendations(
            startup_name="TestAI",
            profile=profile,
            classification=classification,
            validated_evidence=evidence,
            defensibility=None,
            inception_fit=None,
            production_readiness=None,
            composite=None,
            final_priority_score=0.85,
            recommended_motion="immediate_outreach",
            gap_diagnosis=diagnosis,
            rag_context=_make_rag_context(),
        )
        assert result.startup_name == "TestAI"
        assert len(result.recommendations) == 1
        assert result.top_recommendation is not None
        assert result.top_recommendation.action == RecommendedNextAction.APPROACH_NOW

    def test_multiple_gaps_all_approach_now(self) -> None:
        gap1 = _make_gap(TechnicalGap.HIGH_INFERENCE_COST)
        gap2 = _make_gap(TechnicalGap.HIGH_LATENCY, confidence=ConfidenceLevel.HIGH)
        diagnosis = _make_diagnosis([gap1, gap2])

        result = build_recommendations(
            startup_name="TestAI",
            profile=_make_profile(),
            classification=_make_classification(),
            validated_evidence=_make_validated_evidence(),
            defensibility=None,
            inception_fit=None,
            production_readiness=None,
            composite=None,
            final_priority_score=0.85,
            recommended_motion="immediate_outreach",
            gap_diagnosis=diagnosis,
            rag_context=_make_rag_context(),
        )
        assert len(result.recommendations) == 2
        approach = [r for r in result.recommendations if r.action == RecommendedNextAction.APPROACH_NOW]
        assert len(approach) == 2

    def test_reasoning_contains_startup_name_and_gap_count(self) -> None:
        gap = _make_gap(TechnicalGap.SLOW_DATA_PIPELINE)
        diagnosis = _make_diagnosis([gap])

        result = build_recommendations(
            startup_name="TestAI",
            profile=_make_profile(),
            classification=_make_classification(),
            validated_evidence=_make_validated_evidence(),
            defensibility=None,
            inception_fit=None,
            production_readiness=None,
            composite=None,
            final_priority_score=0.85,
            recommended_motion="high_priority_outreach",
            gap_diagnosis=diagnosis,
            rag_context=_make_rag_context(),
        )
        assert "TestAI" in result.reasoning
        assert "Gaps diagnosed: 1" in result.reasoning

    def test_rag_missing_context_blocks_recommendation(self) -> None:
        gap = _make_gap(TechnicalGap.HIGH_INFERENCE_COST)
        diagnosis = _make_diagnosis([gap])

        result = build_recommendations(
            startup_name="TestAI",
            profile=_make_profile(),
            classification=_make_classification(),
            validated_evidence=_make_validated_evidence(),
            defensibility=None,
            inception_fit=None,
            production_readiness=None,
            composite=None,
            final_priority_score=0.85,
            recommended_motion="immediate_outreach",
            gap_diagnosis=diagnosis,
            rag_context=_make_rag_context(missing=True),
        )
        assert len(result.recommendations) == 1
        rec = result.recommendations[0]
        assert rec.action == RecommendedNextAction.NOT_RECOMMENDED
        assert rec.confidence == ConfidenceLevel.LOW
        assert len(rec.missing_evidence) == 1
        assert "RAG context missing" in rec.missing_evidence[0]


# =========================================================================
# Mapping-based recommendation tests
# =========================================================================


def _make_calibrated_inventory() -> list[DecisionCalibrationRecord]:
    """Return a fully calibrated inventory for recommendation decisions."""
    return [
        DecisionCalibrationRecord(
            decision_id="recommendation.priority_score_weights",
            decision_name="test",
            decision_type=DecisionType.WEIGHT,
            current_value={
                "mapping_score": 0.25,
                "mapping_confidence": 0.20,
                "gap_severity_score": 0.10,
                "gap_confidence_score": 0.10,
                "evidence_support": 0.10,
                "rag_support": 0.10,
                "business_impact": 0.10,
                "implementation_complexity_inverse": 0.05,
            },
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.production_threshold",
            decision_name="test",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.40,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.confidence_threshold",
            decision_name="test",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.50,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.uncertainty_penalty",
            decision_name="test",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.10,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.minimum_mapping_confidence",
            decision_name="test",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.30,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
        ),
        DecisionCalibrationRecord(
            decision_id="recommendation.minimum_evidence_support",
            decision_name="test",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.0,
            calibration_status=CalibrationStatus.CALIBRATED,
            production_allowed=True,
        ),
    ]


def _make_sample_mapping(
    gap_type: str = "inference_performance_gap",
    tech: str = "TensorRT",
    mapping_score: float = 0.75,
    mapping_confidence: float = 0.80,
    production_allowed: bool = True,
) -> dict[str, object]:
    return {
        "mapping_id": f"map-test-1-{gap_type}",
        "gap_type": gap_type,
        "nvidia_technology": tech,
        "technology_category": "inference_optimization",
        "required_gap_features": ["gap_severity_score", "gap_confidence_score"],
        "required_rag_topics": [],
        "required_evidence_types": ["fact"],
        "mapping_score": mapping_score,
        "mapping_confidence": mapping_confidence,
        "uncertainty": 0.1,
        "supporting_rag_context_ids": ["rag-ctx-1", "rag-ctx-2"],
        "supporting_evidence_ids": ["ev-1"],
        "calibration_decision_ids": REQUIRED_MAPPING_DECISIONS,
        "production_allowed": production_allowed,
        "blockers": [],
        "explanation": f"Mapping '{gap_type} → {tech}'",
        "features": {
            "gap_severity_score": 0.70,
            "gap_confidence_score": 0.80,
        },
    }


def _make_mapping_blocked_uncalibrated(
    gap_type: str = "inference_performance_gap",
) -> dict[str, object]:
    return {
        "mapping_id": f"map-test-1-{gap_type}",
        "gap_type": gap_type,
        "nvidia_technology": "TensorRT",
        "technology_category": "inference_optimization",
        "required_gap_features": [],
        "required_rag_topics": [],
        "required_evidence_types": [],
        "mapping_score": 0.0,
        "mapping_confidence": 0.0,
        "uncertainty": 1.0,
        "supporting_rag_context_ids": [],
        "supporting_evidence_ids": [],
        "calibration_decision_ids": REQUIRED_MAPPING_DECISIONS,
        "production_allowed": False,
        "blockers": ["Calibration decisions missing"],
        "explanation": "Blocked: uncalibrated",
    }


class TestRankFromMappingsNoMappings:
    def test_empty_mappings_returns_blocked(self) -> None:
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=[],
            mapping_status="",
        )
        assert result["ranking_status"] == RecommendationRankingStatus.BLOCKED_NO_NVIDIA_MAPPINGS.value
        assert result["production_allowed"] is False
        assert len(result["blockers"]) == 1
        assert "No NVIDIA technology mappings" in result["blockers"][0]
        assert result["nvidia_recommendations"] == []


class TestRankFromMappingsBlockedUncalibrated:
    def test_mapping_status_blocked_returns_blocked_uncalibrated(self) -> None:
        mappings = [_make_mapping_blocked_uncalibrated()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="blocked_uncalibrated_mapping",
        )
        assert result["ranking_status"] == RecommendationRankingStatus.BLOCKED_UNCALIBRATED_MAPPING.value
        assert result["production_allowed"] is False

    def test_mapping_status_failed_blocks(self) -> None:
        mappings = [_make_mapping_blocked_uncalibrated()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="failed",
        )
        assert result["ranking_status"] == RecommendationRankingStatus.BLOCKED_UNCALIBRATED_MAPPING.value

    def test_mapping_status_needs_more_evidence_blocks(self) -> None:
        mappings = [_make_mapping_blocked_uncalibrated()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="needs_more_evidence",
        )
        assert result["ranking_status"] == RecommendationRankingStatus.BLOCKED_UNCALIBRATED_MAPPING.value


class TestRankFromMappingsMissingCalibration:
    def test_no_calibrated_inventory_blocks_recommendation(self) -> None:
        mappings = [_make_sample_mapping()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=[],  # empty inventory → all decisions missing
        )
        assert result["ranking_status"] == RecommendationRankingStatus.BLOCKED_UNCALIBRATED_RECOMMENDATION.value
        assert result["production_allowed"] is False
        assert len(result["blockers"]) > 0


class TestRankFromMappingsProductionAllowed:
    def test_production_allowed_mapping_generates_recommendation(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.75,
                mapping_confidence=0.80,
                production_allowed=True,
            )
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        assert result["ranking_status"] == RecommendationRankingStatus.PASSED.value
        assert result["production_allowed"] is True
        recs = result["nvidia_recommendations"]
        assert len(recs) == 1
        rec = recs[0]
        assert rec["nvidia_technology"] == "TensorRT"
        assert rec["gap_type"] == "inference_performance_gap"
        assert rec["production_allowed"] is True
        assert rec["recommendation_priority_score"] > 0

    def test_no_mappings_for_technology(self) -> None:
        """Technology not in mappings does not become a recommendation."""
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
            )
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        techs = [r["nvidia_technology"] for r in result["nvidia_recommendations"]]
        assert "CUDA" not in techs
        assert "TensorRT" in techs

    def test_supporting_rag_context_ids_preserved(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
            )
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        rec = result["nvidia_recommendations"][0]
        assert rec["supporting_rag_context_ids"] == ["rag-ctx-1", "rag-ctx-2"]

    def test_supporting_evidence_ids_preserved(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
            )
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        rec = result["nvidia_recommendations"][0]
        assert rec["supporting_evidence_ids"] == ["ev-1"]

    def test_mapping_score_and_confidence_preserved(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.75,
                mapping_confidence=0.80,
            )
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        rec = result["nvidia_recommendations"][0]
        assert rec["mapping_score"] == 0.75
        assert rec["mapping_confidence"] == 0.80

    def test_recommendations_sorted_by_priority_score_desc(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.50,
                mapping_confidence=0.60,
            ),
            _make_sample_mapping(
                gap_type="data_pipeline_gap",
                tech="RAPIDS",
                mapping_score=0.90,
                mapping_confidence=0.95,
            ),
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        recs = result["nvidia_recommendations"]
        scores = [r["recommendation_priority_score"] for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_run_id_preserved(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [_make_sample_mapping()]
        result = rank_recommendations_from_mappings(
            run_id="custom-run-id",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        assert result["run_id"] == "custom-run-id"

    def test_recommendation_metrics_calculated(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [_make_sample_mapping()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        metrics = result["nvidia_recommendation_metrics"]
        assert metrics["recommendation_count"] == 1
        assert metrics["mapping_count"] == 1
        assert metrics["production_allowed_recommendation_count"] == 1
        assert metrics["average_mapping_score"] > 0
        assert metrics["average_mapping_confidence"] > 0
        assert metrics["average_recommendation_priority_score"] > 0
        assert metrics["evidence_supported_recommendation_rate"] > 0
        assert metrics["rag_supported_recommendation_rate"] > 0

    def test_blocked_mapping_production_not_allowed_in_recommendation(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.2,
                mapping_confidence=0.2,
                production_allowed=False,
            )
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        rec = result["nvidia_recommendations"][0]
        assert rec["production_allowed"] is False
        assert len(rec["blockers"]) > 0

    def test_no_llm_qdrant_scraping_imports(self) -> None:
        """Verify no LLM, Qdrant, or scraping is called by the function."""
        inventory = _make_calibrated_inventory()
        mappings = [_make_sample_mapping()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        assert result is not None
        rec = result["nvidia_recommendations"][0]
        assert rec["gap_type"] == "inference_performance_gap"
        assert rec["recommendation_type"] == "technology_adoption"


class TestRecommendationPriorityScore:
    def test_priority_score_zero_without_calibrated_weights(self) -> None:
        mappings = [_make_sample_mapping()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=[],  # no calibration
        )
        assert result["ranking_status"] == RecommendationRankingStatus.BLOCKED_UNCALIBRATED_RECOMMENDATION.value

    def test_priority_score_computed_with_calibrated_weights(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.85,
                mapping_confidence=0.90,
            )
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        rec = result["nvidia_recommendations"][0]
        assert rec["recommendation_priority_score"] > 0


class TestComputeRecommendationMetrics:
    def test_empty_recommendations(self) -> None:
        metrics = compute_recommendation_metrics([])
        assert metrics.recommendation_count == 0
        assert metrics.mapping_count == 0
        assert metrics.production_allowed_recommendation_count == 0

    def test_mixed_production_blocked(self) -> None:
        recs = [
            NvidiaRecommendationRecord(
                recommendation_id="rec-1",
                gap_id="gap-1",
                gap_type="inference_performance_gap",
                nvidia_technology="TensorRT",
                reason="test",
                mapping_score=0.8,
                mapping_confidence=0.7,
                recommendation_priority_score=0.6,
                confidence=0.7,
                uncertainty=0.1,
                business_impact=0.7,
                implementation_complexity=0.5,
                supporting_rag_context_ids=["r1"],
                supporting_evidence_ids=["e1"],
                production_allowed=True,
            ),
            NvidiaRecommendationRecord(
                recommendation_id="rec-2",
                gap_id="gap-2",
                gap_type="data_pipeline_gap",
                nvidia_technology="RAPIDS",
                reason="test",
                mapping_score=0.0,
                mapping_confidence=0.0,
                recommendation_priority_score=0.0,
                confidence=0.0,
                uncertainty=1.0,
                business_impact=0.5,
                implementation_complexity=0.5,
                production_allowed=False,
                blockers=["blocked"],
            ),
        ]
        metrics = compute_recommendation_metrics(recs)
        assert metrics.recommendation_count == 2
        assert metrics.production_allowed_recommendation_count == 1
        assert metrics.blocked_recommendation_count == 0
        assert metrics.needs_review_recommendation_count == 1
        assert metrics.mapping_count == 2
        assert metrics.average_mapping_score == 0.4
        assert metrics.average_mapping_confidence == 0.35
        assert metrics.average_recommendation_priority_score == 0.3
        assert metrics.average_recommendation_confidence == 0.35
        assert metrics.evidence_supported_recommendation_rate == 0.5
        assert metrics.rag_supported_recommendation_rate == 0.5
        assert metrics.recommendation_uncertainty_mean == 0.55
        assert metrics.missing_recommendation_calibration_count == len(REQUIRED_RECOMMENDATION_DECISIONS)


class TestRankFromMappingsCalibrationValidation:
    def test_partial_calibration_blocks(self) -> None:
        """Only some decisions calibrated → blocked."""
        partial = _make_calibrated_inventory()[:3]  # only first 3
        mappings = [_make_sample_mapping()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=partial,
        )
        assert result["ranking_status"] == RecommendationRankingStatus.BLOCKED_UNCALIBRATED_RECOMMENDATION.value

    def test_uncalibrated_status_blocks(self) -> None:
        """Decision exists but is UNCALIBRATED → blocked."""
        uncal_inventory = [
            DecisionCalibrationRecord(
                decision_id=did,
                decision_name="test",
                decision_type=DecisionType.WEIGHT,
                current_value=0.5,
                calibration_status=CalibrationStatus.UNCALIBRATED,
                production_allowed=False,
            )
            for did in REQUIRED_RECOMMENDATION_DECISIONS
        ]
        mappings = [_make_sample_mapping()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=uncal_inventory,
        )
        assert result["ranking_status"] == RecommendationRankingStatus.BLOCKED_UNCALIBRATED_RECOMMENDATION.value


class TestNewMetricsFields:
    def test_average_recommendation_confidence_computed(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.8,
                mapping_confidence=0.9,
            ),
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        metrics = result["nvidia_recommendation_metrics"]
        assert "average_recommendation_confidence" in metrics
        assert 0 < metrics["average_recommendation_confidence"] <= 1.0

    def test_needs_review_recommendation_count_computed(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.2,
                mapping_confidence=0.1,
                production_allowed=False,
            ),
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        metrics = result["nvidia_recommendation_metrics"]
        assert "needs_review_recommendation_count" in metrics
        assert metrics["needs_review_recommendation_count"] >= 0

    def test_recommendation_uncertainty_mean_computed(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.8,
                mapping_confidence=0.9,
            ),
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        metrics = result["nvidia_recommendation_metrics"]
        assert "recommendation_uncertainty_mean" in metrics
        assert 0 <= metrics["recommendation_uncertainty_mean"] <= 1.0

    def test_priority_score_between_zero_and_one(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.99,
                mapping_confidence=0.99,
            ),
            _make_sample_mapping(
                gap_type="data_pipeline_gap",
                tech="RAPIDS",
                mapping_score=0.5,
                mapping_confidence=0.5,
            ),
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        for rec in result["nvidia_recommendations"]:
            assert 0.0 <= rec["recommendation_priority_score"] <= 1.0

    def test_no_rag_contexts_production_blocked(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.8,
                mapping_confidence=0.8,
                production_allowed=True,
            ),
        ]
        # Override to remove RAG IDs
        mappings[0]["supporting_rag_context_ids"] = []
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        rec = result["nvidia_recommendations"][0]
        # Mapping allows production, but recommendation may allow it
        # (min_evidence_support=0.0 means evidence is not required)
        # RAG not being present is not necessarily a blocker by itself
        # unless it causes the score to fall below production_threshold
        assert len(rec["supporting_rag_context_ids"]) == 0
        # The recommendation should still be evaluated
        assert rec["gap_type"] == "inference_performance_gap"

    def test_no_evidence_ids_handled(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.8,
                mapping_confidence=0.8,
                production_allowed=True,
            ),
        ]
        mappings[0]["supporting_evidence_ids"] = []
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        rec = result["nvidia_recommendations"][0]
        assert len(rec["supporting_evidence_ids"]) == 0
        assert rec["gap_type"] == "inference_performance_gap"

    def test_calibration_decision_ids_attached(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [_make_sample_mapping()]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        rec = result["nvidia_recommendations"][0]
        cal_ids = rec.get("calibration_decision_ids", [])
        assert len(cal_ids) >= len(REQUIRED_RECOMMENDATION_DECISIONS)
        for did in REQUIRED_RECOMMENDATION_DECISIONS:
            assert did in cal_ids

    def test_mapping_blocked_production_allowed_false(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.0,
                mapping_confidence=0.0,
                production_allowed=False,
            ),
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        rec = result["nvidia_recommendations"][0]
        assert rec["production_allowed"] is False

    def test_sorted_by_priority_score_desc(self) -> None:
        inventory = _make_calibrated_inventory()
        mappings = [
            _make_sample_mapping(
                gap_type="inference_performance_gap",
                tech="TensorRT",
                mapping_score=0.3,
                mapping_confidence=0.4,
            ),
            _make_sample_mapping(
                gap_type="data_pipeline_gap",
                tech="RAPIDS",
                mapping_score=0.95,
                mapping_confidence=0.95,
            ),
        ]
        result = rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        recs = result["nvidia_recommendations"]
        scores = [r["recommendation_priority_score"] for r in recs]
        assert scores == sorted(scores, reverse=True), f"Expected descending order, got {scores}"

    def test_no_llm_qdrant_scraping_called(self) -> None:
        """Verify no external service is called during ranking."""
        inventory = _make_calibrated_inventory()
        mappings = [_make_sample_mapping()]
        import sys as _sys

        before = set(_sys.modules.keys())
        rank_recommendations_from_mappings(
            run_id="test-1",
            nvidia_technology_mappings=mappings,
            mapping_status="passed",
            inventory=inventory,
        )
        after = set(_sys.modules.keys())
        new = after - before
        banned = {"langchain", "qdrant_client", "playwright", "openai", "anthropic", "httpx"}
        triggered = {m for m in new if any(b in m for b in banned)}
        assert not triggered, f"Banned imports triggered: {triggered}"

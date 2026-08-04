"""Tests for deterministic gap diagnosis."""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import Any

from pydantic import HttpUrl

from src.classification.ai_native_classifier import ClassificationResult
from src.diagnosis.gap_diagnosis import diagnose_gaps
from src.diagnosis.gap_diagnosis_scoring import (
    diagnose_gaps_quantitative,
    extract_gap_confidence_features,
    extract_gap_severity_features,
)
from src.diagnosis.nvidia_mapping import build_technology_candidates
from src.diagnosis.schemas import (
    ALL_GAP_TYPES,
    EvidenceTag,
    GapConfidenceFeatures,
    GapDiagnosisResult,
    GapDiagnosisStatus,
    GapSeverityFeatures,
    GapWithEvidence,
)
from src.extraction.schemas import (
    AINativeLevel,
    ConfidenceLevel,
    SourceType,
    StartupProfile,
)
from src.quality.decision_calibration_registry import (
    CalibrationMethod,
    CalibrationStatus,
    DecisionCalibrationRecord,
    DecisionType,
)
from src.validation.evidence_validator import EvidenceKind, ValidatedEvidence

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_evidence(
    claim: str,
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    evidence_kind: EvidenceKind = EvidenceKind.FACT,
    quote: str = "The company uses AI for core features.",
) -> ValidatedEvidence:
    return ValidatedEvidence(
        claim=claim,
        source_url=HttpUrl("https://example.com"),
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence=quote,
        confidence=confidence,
        evidence_kind=evidence_kind,
        collected_at=datetime.now(timezone.utc),  # noqa: UP017
    )


def _make_profile(
    sector: str = "Technology",
    ai_signals: list[str] | None = None,
    tech_stack: list[str] | None = None,
    description: str = "A technology company building software.",
    product_summary: str = "Building software solutions.",
    customers: list[str] | None = None,
    funding: list[str] | None = None,
) -> StartupProfile:
    return StartupProfile(
        startup_name="Test Startup",
        website=HttpUrl("https://example.com"),
        sector=sector,
        description=description,
        product_summary=product_summary,
        ai_signals=ai_signals or [],
        tech_stack_signals=tech_stack or [],
        customers=customers or [],
        funding_signals=funding or [],
        sources=[],
        confidence_score=0.5,
    )


def _make_classification(
    level: AINativeLevel = AINativeLevel.AI_ENABLED,
) -> ClassificationResult:
    return ClassificationResult(
        startup_name="Test Startup",
        classification=level,
        confidence=ConfidenceLevel.HIGH,
        reasoning=f"Classified as {level.value}.",
    )


# ---------------------------------------------------------------------------
# Scenario tests
# ---------------------------------------------------------------------------


class TestGapDiagnosis:
    def test_external_api_gap(self) -> None:
        """Startup using 'gpt' and 'openai' should trigger external_api_dependency."""
        profile = _make_profile(
            tech_stack=["Python", "openai", "gpt"],
            ai_signals=["AI signal: llm", "AI signal: gpt"],
            description="We build LLM-powered chatbots using OpenAI GPT-4.",
            product_summary="Chatbot platform using GPT API.",
        )
        evidence = [
            _make_evidence("Uses OpenAI GPT-4 for core features", ConfidenceLevel.HIGH),
        ]
        result = diagnose_gaps(
            "Test Startup",
            profile,
            _make_classification(),
            evidence,
        )
        gap = _find_gap(result, "external_api_dependency")
        assert gap is not None
        assert gap.detected
        assert gap.evidence_tag == EvidenceTag.FACT

    def test_inference_cost_gap(self) -> None:
        """Startup with high-volume inference without NVIDIA tech."""
        profile = _make_profile(
            tech_stack=["Python", "Flask"],
            ai_signals=["AI signal: inference", "AI signal: high volume"],
            description="High-volume inference serving thousands of requests per second.",
            product_summary="Real-time inference API.",
        )
        evidence = [
            _make_evidence(
                "High-volume inference without GPU acceleration",
                ConfidenceLevel.MEDIUM,
            ),
        ]
        result = diagnose_gaps(
            "Test Startup",
            profile,
            _make_classification(AINativeLevel.AI_NATIVE),
            evidence,
        )
        gap = _find_gap(result, "high_inference_cost")
        assert gap is not None
        assert gap.detected

    def test_agent_governance_gap(self) -> None:
        """Startup building AI agents without guardrails."""
        profile = _make_profile(
            tech_stack=["Python", "LangChain"],
            ai_signals=["AI signal: agent", "AI signal: autonomous"],
            description="Multi-agent system for enterprise workflow automation.",
            product_summary="Autonomous AI agents for business processes.",
        )
        result = diagnose_gaps(
            "Test Startup",
            profile,
            _make_classification(AINativeLevel.AI_NATIVE),
            [],
        )
        gap = _find_gap(result, "agent_governance_gap")
        assert gap is not None
        assert gap.detected

    def test_voice_gap(self) -> None:
        """Startup in call center with voice/speech should detect voice_need."""
        profile = _make_profile(
            sector="Customer Service",
            ai_signals=["AI signal: voice", "AI signal: speech-to-text"],
            tech_stack=["Python"],
            description="Voicebot for customer service call centers.",
            product_summary="Speech-to-text analytics platform for calls.",
        )
        evidence = [
            _make_evidence("Voicebot platform for call centers", ConfidenceLevel.HIGH),
        ]
        result = diagnose_gaps(
            "Test Startup",
            profile,
            _make_classification(AINativeLevel.AI_ENABLED),
            evidence,
        )
        gap = _find_gap(result, "voice_need")
        assert gap is not None
        assert gap.detected
        assert gap.evidence_tag == EvidenceTag.FACT

    def test_healthcare_gap(self) -> None:
        """HealthTech sector should detect healthcare_compliance_need."""
        profile = _make_profile(
            sector="HealthTech",
            ai_signals=["AI signal: medical imaging"],
            tech_stack=["Python", "PyTorch"],
            description="AI-powered medical diagnosis platform.",
            product_summary="Medical imaging analysis for hospitals.",
        )
        result = diagnose_gaps(
            "Test Startup",
            profile,
            _make_classification(AINativeLevel.AI_NATIVE),
            [],
        )
        gap = _find_gap(result, "healthcare_compliance_need")
        assert gap is not None
        assert gap.detected

    def test_no_gaps_clean(self) -> None:
        """Generic startup with no AI signals should detect few or no gaps."""
        profile = _make_profile(
            sector="E-commerce",
            tech_stack=["WordPress"],
            ai_signals=[],
            description="Online store selling handmade products.",
            product_summary="E-commerce platform for artisans.",
        )
        result = diagnose_gaps(
            "Test Startup",
            profile,
            _make_classification(AINativeLevel.NON_AI),
            [],
        )
        detected = [g for g in result.diagnosed_gaps if g.detected]
        assert len(detected) <= 2

    def test_inferred_gap_weak_evidence(self) -> None:
        """Gap detected by keyword in profile without direct evidence should be inferred."""
        profile = _make_profile(
            tech_stack=["Python"],
            ai_signals=["AI signal: computer vision"],
            description="Using computer vision for quality inspection.",
            product_summary="CV inspection system.",
        )
        result = diagnose_gaps(
            "Test Startup",
            profile,
            _make_classification(AINativeLevel.AI_ENABLED),
            [],
        )
        gap = _find_gap(result, "computer_vision_need")
        assert gap is not None
        assert gap.detected
        assert gap.evidence_tag == EvidenceTag.INFERRED

    def test_full_pipeline_with_mapping(self) -> None:
        """End-to-end: diagnose gaps then build technology candidates."""
        profile = _make_profile(
            sector="HealthTech",
            tech_stack=["Python", "openai", "gpt"],
            ai_signals=[
                "AI signal: voice",
                "AI signal: speech-to-text",
                "AI signal: agent",
                "AI signal: autonomous",
            ],
            description="Voice AI agents for healthcare call centers.",
            product_summary="Speech-enabled agents for patient intake.",
        )
        result = diagnose_gaps(
            "Test Startup",
            profile,
            _make_classification(AINativeLevel.AI_NATIVE),
            [],
        )
        assert isinstance(result, GapDiagnosisResult)
        assert len(result.diagnosed_gaps) == 15
        detected = [g for g in result.diagnosed_gaps if g.detected]
        assert len(detected) >= 2

        candidates = build_technology_candidates(result.diagnosed_gaps)
        assert len(candidates) >= 1
        for c in candidates:
            assert c.technology_name
            assert c.justification
            assert c.addresses_gap

    def test_missing_evidence_reported(self) -> None:
        """Inferred gaps should produce missing_evidence entries."""
        profile = _make_profile(
            tech_stack=["Python"],
            ai_signals=["AI signal: robotics"],
            description="Robotics startup building autonomous drones.",
            product_summary="Drone navigation system.",
        )
        result = diagnose_gaps(
            "Test Startup",
            profile,
            _make_classification(AINativeLevel.AI_ENABLED),
            [],
        )
        assert len(result.missing_evidence) > 0
        for msg in result.missing_evidence:
            assert "inference" in msg or "inferred" in msg

    def test_latency_gap(self) -> None:
        """Startup with latency keywords without NVIDIA tech."""
        profile = _make_profile(
            tech_stack=["Python", "Flask"],
            ai_signals=["AI signal: real-time", "AI signal: inference"],
            description="Real-time inference API with low-latency requirements.",
            product_summary="Low latency serving platform.",
        )
        result = diagnose_gaps(
            "Latency Startup",
            profile,
            _make_classification(AINativeLevel.AI_NATIVE),
            [],
        )
        gap = _find_gap(result, "high_latency")
        assert gap is not None
        assert gap.detected

    def test_data_pipeline_gap(self) -> None:
        """Startup with data tech without RAPIDS."""
        profile = _make_profile(
            tech_stack=["Python", "Kafka", "Spark", "Airflow"],
            ai_signals=["AI signal: data pipeline"],
            description="Data processing platform with large-scale ETL pipelines.",
            product_summary="ETL platform for batch processing.",
        )
        result = diagnose_gaps(
            "Data Startup",
            profile,
            _make_classification(AINativeLevel.AI_ENABLED),
            [],
        )
        gap = _find_gap(result, "slow_data_pipeline")
        assert gap is not None
        assert gap.detected

    def test_privacy_deployment_gap(self) -> None:
        """Regulated sector without privacy evidence should detect gap."""
        profile = _make_profile(
            sector="FinTech",
            tech_stack=["Python"],
            ai_signals=["AI signal: nlp"],
            description="FinTech processing sensitive customer financial data.",
            product_summary="NLP-based financial document analysis.",
        )
        result = diagnose_gaps(
            "Privacy Startup",
            profile,
            _make_classification(AINativeLevel.AI_ENABLED),
            [],
        )
        gap = _find_gap(result, "privacy_or_controlled_deployment_gap")
        assert gap is not None
        assert gap.detected
        assert gap.evidence_tag == EvidenceTag.INFERRED

    def test_cybersecurity_gap(self) -> None:
        """Startup with cybersecurity keywords."""
        profile = _make_profile(
            tech_stack=["Python"],
            ai_signals=["AI signal: threat detection", "AI signal: security"],
            description="AI-powered threat detection and intrusion prevention platform.",
            product_summary="Cybersecurity platform using machine learning.",
        )
        result = diagnose_gaps(
            "Security Startup",
            profile,
            _make_classification(AINativeLevel.AI_NATIVE),
            [],
        )
        gap = _find_gap(result, "ai_cybersecurity_need")
        assert gap is not None
        assert gap.detected

    def test_observability_gap(self) -> None:
        """AI-native startup without monitoring/observability signals."""
        profile = _make_profile(
            tech_stack=["Python", "PyTorch"],
            ai_signals=["AI signal: deep learning"],
            description="Deep learning platform for image recognition.",
            product_summary="Image recognition API.",
        )
        result = diagnose_gaps(
            "Obs Startup",
            profile,
            _make_classification(AINativeLevel.AI_NATIVE),
            [],
        )
        gap = _find_gap(result, "observability_gap")
        assert gap is not None
        assert gap.detected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_gap(result: GapDiagnosisResult, gap_value: str) -> GapWithEvidence | None:
    for g in result.diagnosed_gaps:
        if g.gap.value == gap_value:
            return g
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Quantitative gap diagnosis tests
# ═══════════════════════════════════════════════════════════════════════════


def _make_calibrated_gap_diagnosis_decisions() -> list[DecisionCalibrationRecord]:
    """Create calibrated decision records for gap diagnosis testing."""
    now = datetime(2026, 6, 18, tzinfo=UTC)
    return [
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.severity_weights",
            decision_name="Gap Diagnosis: Severity Weights",
            decision_type=DecisionType.WEIGHT,
            current_value={
                "missing_required_signal_count": 0.20,
                "weak_evidence_count": 0.15,
                "rejected_evidence_count": 0.15,
                "unsupported_claim_count": 0.15,
                "low_confidence_evidence_count": 0.10,
                "relevant_signal_absence": 0.10,
                "nvidia_fit_opportunity_signal_count": 0.05,
                "implementation_complexity_proxy": 0.05,
                "business_impact_proxy": 0.03,
                "uncertainty_penalty": 0.02,
            },
            metric_name="gap_diagnosis_severity_weights",
            value_origin="Grid search on 30 golden entries (test)",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-diagnosis",
            last_calibrated_at=now,
            evidence_source="Test fixture",
            notes="Calibrated for testing",
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.confidence_weights",
            decision_name="Gap Diagnosis: Confidence Weights",
            decision_type=DecisionType.WEIGHT,
            current_value={
                "supporting_evidence_count": 0.20,
                "supporting_source_count": 0.15,
                "average_evidence_confidence": 0.15,
                "average_source_quality": 0.15,
                "cross_source_agreement_count": 0.10,
                "contradiction_count": 0.10,
                "extraction_success_rate": 0.08,
                "source_category_coverage": 0.07,
            },
            metric_name="gap_diagnosis_confidence_weights",
            value_origin="Grid search on 30 golden entries (test)",
            calibration_method=CalibrationMethod.GRID_SEARCH,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-diagnosis",
            last_calibrated_at=now,
            evidence_source="Test fixture",
            notes="Calibrated for testing",
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.production_threshold",
            decision_name="Gap Diagnosis: Production Threshold",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.50,
            metric_name="gap_diagnosis_production_threshold",
            value_origin="P5 percentile on 30 golden entries (test)",
            calibration_method=CalibrationMethod.PERCENTILE_RULE,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-diagnosis",
            last_calibrated_at=now,
            evidence_source="Test fixture",
            notes="Calibrated for testing",
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.uncertainty_penalty",
            decision_name="Gap Diagnosis: Uncertainty Penalty",
            decision_type=DecisionType.FALLBACK_POLICY,
            current_value=0.10,
            metric_name="gap_diagnosis_uncertainty_penalty",
            value_origin="Sensitivity analysis on 30 golden entries (test)",
            calibration_method=CalibrationMethod.SENSITIVITY_ANALYSIS,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-diagnosis",
            last_calibrated_at=now,
            evidence_source="Test fixture",
            notes="Calibrated for testing",
        ),
        DecisionCalibrationRecord(
            decision_id="gap_diagnosis.minimum_evidence_coverage",
            decision_name="Gap Diagnosis: Minimum Evidence Coverage",
            decision_type=DecisionType.THRESHOLD,
            current_value=0.30,
            metric_name="gap_diagnosis_min_evidence_coverage",
            value_origin="Baseline measurement on historical runs (test)",
            calibration_method=CalibrationMethod.BASELINE_MEASUREMENT,
            calibration_status=CalibrationStatus.BASELINE_MEASURED,
            production_allowed=True,
            owner="team-diagnosis",
            last_calibrated_at=now,
            evidence_source="Test fixture",
            notes="Calibrated for testing",
        ),
    ]


def _make_evidence_dict(
    claim: str = "Test claim",
    confidence: float = 0.8,
    source_quality: float = 0.7,
    source_id: str = "src-1",
    evidence_id: str = "ev-1",
) -> dict[str, Any]:
    return {
        "id": evidence_id,
        "evidence_id": evidence_id,
        "source_id": source_id,
        "url": f"https://example.com/{source_id}",
        "text": claim,
        "snippet": claim,
        "claim": claim,
        "confidence": "high",
        "evidence_confidence_score": confidence,
        "source_quality_score": source_quality,
    }


def _make_claim_dict(
    claim_text: str = "Test claim",
    support_status: str = "supported",
    claim_id: str = "cl-1",
    is_critical: bool = False,
) -> dict[str, Any]:
    return {
        "id": claim_id,
        "claim_id": claim_id,
        "claim_text": claim_text,
        "support_status": support_status,
        "is_critical": is_critical,
    }


class TestGapDiagnosisQuantitative:
    """Tests for the quantitative gap diagnosis (gap_diagnosis_scoring.py)."""

    def test_features_extracted_per_gap_type(self) -> None:
        """Each gap type gets severity and confidence features."""
        evidence = [_make_evidence_dict(claim="GPU acceleration with CUDA", evidence_id="ev-1")]
        claims = [_make_claim_dict(claim_text="Uses GPU acceleration", claim_id="cl-1")]

        for gap_type in ALL_GAP_TYPES:
            sev = extract_gap_severity_features(
                gap_type=gap_type,
                evidence_items=evidence,
                accepted_evidence_items=evidence,
                rejected_evidence_items=[],
                claims=claims,
                evidence_validation=None,
                collection_metrics=None,
            )
            conf = extract_gap_confidence_features(
                gap_type=gap_type,
                evidence_items=evidence,
                accepted_evidence_items=evidence,
                claims=claims,
                collection_metrics=None,
                extraction_metrics=None,
            )

            assert isinstance(sev, GapSeverityFeatures)
            assert isinstance(conf, GapConfidenceFeatures)
            # All severity features should be >= 0
            for fname in sev.model_dump():
                val = getattr(sev, fname)
                assert isinstance(val, (int, float))
                assert val >= 0

    def test_blocks_when_severity_weights_missing(self) -> None:
        """Missing severity_weights blocks diagnosis."""
        calibrated = _make_calibrated_gap_diagnosis_decisions()
        # Remove severity_weights from calibrated inventory
        inventory = [d for d in calibrated if d.decision_id != "gap_diagnosis.severity_weights"]

        result = diagnose_gaps_quantitative(
            run_id="test-run-1",
            evidence_items=[_make_evidence_dict()],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        assert result.gap_diagnosis_status == GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS
        assert not result.production_allowed
        assert any("severity_weights" in b for b in result.blockers)

    def test_blocks_when_confidence_weights_missing(self) -> None:
        """Missing confidence_weights blocks diagnosis."""
        calibrated = _make_calibrated_gap_diagnosis_decisions()
        inventory = [d for d in calibrated if d.decision_id != "gap_diagnosis.confidence_weights"]

        result = diagnose_gaps_quantitative(
            run_id="test-run-2",
            evidence_items=[_make_evidence_dict()],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        assert result.gap_diagnosis_status == GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS
        assert not result.production_allowed

    def test_blocks_when_threshold_missing(self) -> None:
        """Missing production threshold blocks diagnosis."""
        calibrated = _make_calibrated_gap_diagnosis_decisions()
        inventory = [d for d in calibrated if d.decision_id != "gap_diagnosis.production_threshold"]

        result = diagnose_gaps_quantitative(
            run_id="test-run-3",
            evidence_items=[_make_evidence_dict()],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        assert result.gap_diagnosis_status == GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS
        assert not result.production_allowed

    def test_blocks_when_uncertainty_penalty_missing(self) -> None:
        """Missing uncertainty_penalty blocks diagnosis."""
        calibrated = _make_calibrated_gap_diagnosis_decisions()
        inventory = [d for d in calibrated if d.decision_id != "gap_diagnosis.uncertainty_penalty"]

        result = diagnose_gaps_quantitative(
            run_id="test-run-4",
            evidence_items=[_make_evidence_dict()],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        assert result.gap_diagnosis_status == GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS
        assert not result.production_allowed

    def test_blocks_when_minimum_evidence_coverage_missing(self) -> None:
        """Missing minimum_evidence_coverage blocks diagnosis."""
        calibrated = _make_calibrated_gap_diagnosis_decisions()
        inventory = [d for d in calibrated if d.decision_id != "gap_diagnosis.minimum_evidence_coverage"]

        result = diagnose_gaps_quantitative(
            run_id="test-run-5",
            evidence_items=[_make_evidence_dict()],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        assert result.gap_diagnosis_status == GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS
        assert not result.production_allowed

    def test_blocks_with_uncalibrated_registry(self) -> None:
        """Default (uncalibrated) registry blocks gap diagnosis.

        Note: gap_diagnosis.* decisions are now UNCALIBRATED in the
        real registry (production blocked until human-labeled calibration).
        This test verifies that a MISSING decision (not in the registry at
        all) produces a block.
        """
        from src.quality.decision_calibration_registry import get_project_decision_inventory

        inventory = get_project_decision_inventory()
        # Remove one required decision to simulate missing calibration
        inventory = [d for d in inventory if d.decision_id != "gap_diagnosis.severity_weights"]

        result = diagnose_gaps_quantitative(
            run_id="test-run-6",
            evidence_items=[_make_evidence_dict()],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        assert result.gap_diagnosis_status == GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS
        assert not result.production_allowed

    def test_scores_between_0_and_1_with_calibration(self) -> None:
        """With valid calibration, all severity and confidence scores are in [0,1]."""
        inventory = _make_calibrated_gap_diagnosis_decisions()
        evidence = [
            _make_evidence_dict(
                claim="GPU acceleration with CUDA for deep learning inference",
                confidence=0.85,
                source_quality=0.8,
                evidence_id="ev-1",
                source_id="src-1",
            ),
            _make_evidence_dict(
                claim="NVIDIA Triton inference server for model deployment",
                confidence=0.75,
                source_quality=0.7,
                evidence_id="ev-2",
                source_id="src-2",
            ),
        ]
        claims = [
            _make_claim_dict(claim_text="Uses GPU acceleration", claim_id="cl-1"),
            _make_claim_dict(claim_text="Deploys with Triton", claim_id="cl-2"),
        ]

        result = diagnose_gaps_quantitative(
            run_id="test-run-7",
            evidence_items=evidence,
            claims=claims,
            inventory=inventory,
        )

        assert result.gap_diagnosis_status != GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS
        for gap in result.gaps:
            assert 0.0 <= gap.severity_score <= 1.0, f"{gap.gap_type}: severity={gap.severity_score}"
            assert 0.0 <= gap.confidence_score <= 1.0, f"{gap.gap_type}: confidence={gap.confidence_score}"

    def test_each_gap_has_evidence_ids_or_needs_more_evidence(self) -> None:
        """Every gap has supporting_evidence_ids or needs_more_evidence status."""
        inventory = _make_calibrated_gap_diagnosis_decisions()

        result = diagnose_gaps_quantitative(
            run_id="test-run-8",
            evidence_items=[_make_evidence_dict(claim="AI startup description", evidence_id="ev-1")],
            claims=[_make_claim_dict(claim_id="cl-1")],
            inventory=inventory,
        )

        for gap in result.gaps:
            if len(gap.supporting_evidence_ids) == 0:
                assert gap.status in (
                    GapDiagnosisStatus.NEEDS_MORE_EVIDENCE,
                    GapDiagnosisStatus.BLOCKED_UNCALIBRATED_GAP_DIAGNOSIS,
                ), f"{gap.gap_type} has no evidence but status is {gap.status}"

    def test_unsupported_critical_claim_blocks(self) -> None:
        """Unsupported critical claims block gap diagnosis."""
        inventory = _make_calibrated_gap_diagnosis_decisions()
        evidence = [_make_evidence_dict()]
        claims = [
            _make_claim_dict(
                claim_text="Critical unsupported claim",
                support_status="unsupported",
                is_critical=True,
                claim_id="cl-critical",
            ),
        ]

        result = diagnose_gaps_quantitative(
            run_id="test-run-9",
            evidence_items=evidence,
            claims=claims,
            inventory=inventory,
        )

        assert result.gap_diagnosis_status == GapDiagnosisStatus.FAILED
        assert not result.production_allowed
        assert any("unsupported critical" in b.lower() for b in result.blockers)

    def test_metrics_are_computed(self) -> None:
        """GapDiagnosisMetrics are computed with correct values."""
        inventory = _make_calibrated_gap_diagnosis_decisions()
        evidence = [_make_evidence_dict(evidence_id="ev-1")]
        claims = [_make_claim_dict(claim_id="cl-1")]

        result = diagnose_gaps_quantitative(
            run_id="test-run-10",
            evidence_items=evidence,
            claims=claims,
            inventory=inventory,
        )

        assert result.metrics is not None
        assert result.metrics.total_gap_count == len(ALL_GAP_TYPES)
        assert result.metrics.production_allowed_gap_count >= 0
        assert result.metrics.blocked_gap_count >= 0
        assert 0.0 <= result.metrics.average_gap_severity <= 1.0
        assert 0.0 <= result.metrics.average_gap_confidence <= 1.0
        assert result.metrics.missing_calibration_count == 0
        assert result.metrics.calibrated_decision_count == 5

    def test_calibration_decision_ids_attached(self) -> None:
        """Calibration decision IDs are attached to each gap result."""
        inventory = _make_calibrated_gap_diagnosis_decisions()
        evidence = [_make_evidence_dict(evidence_id="ev-1")]
        claims = [_make_claim_dict(claim_id="cl-1")]

        result = diagnose_gaps_quantitative(
            run_id="test-run-11",
            evidence_items=evidence,
            claims=claims,
            inventory=inventory,
        )

        for gap in result.gaps:
            assert len(gap.calibration_decision_ids) == 5

    def test_run_id_preserved(self) -> None:
        """The run_id is preserved in the summary."""
        inventory = _make_calibrated_gap_diagnosis_decisions()

        result = diagnose_gaps_quantitative(
            run_id="custom-run-id-42",
            evidence_items=[_make_evidence_dict()],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        assert result.run_id == "custom-run-id-42"

    def test_no_llm_or_external_calls(self) -> None:
        """Test that no LLM, Qdrant, internet, or scraping is called.

        This is verified by the fact that all computation is deterministic
        and only uses in-memory data structures. We verify by checking
        there are no imports from rag, scraping, or LLM modules.
        """
        import src.diagnosis.gap_diagnosis_scoring as mod

        source = mod.__file__ or ""
        with open(source) as f:
            content = f.read()

        assert "openai" not in content
        assert "qdrant" not in content
        assert "trafilatura" not in content
        assert "playwright" not in content
        assert "instructor" not in content
        assert "langchain" not in content
        assert "sentence_transformers" not in content
        assert "httpx" not in content

    def test_scores_with_empty_evidence(self) -> None:
        """With no evidence, gaps get needs_more_evidence status."""
        inventory = _make_calibrated_gap_diagnosis_decisions()

        result = diagnose_gaps_quantitative(
            run_id="test-run-12",
            evidence_items=[],
            claims=[],
            inventory=inventory,
        )

        assert result.gap_diagnosis_status == GapDiagnosisStatus.NEEDS_REVIEW
        for gap in result.gaps:
            assert gap.status == GapDiagnosisStatus.NEEDS_MORE_EVIDENCE
            assert not gap.production_allowed

    def test_rejected_evidence_increases_severity(self) -> None:
        """Startup with rejected evidence should have higher severity."""
        inventory = _make_calibrated_gap_diagnosis_decisions()
        evidence = [_make_evidence_dict(claim="GPU computing", evidence_id="ev-1")]
        rejected = [
            _make_evidence_dict(claim="Rejected claim", evidence_id="ev-rej", source_id="src-rej"),
            _make_evidence_dict(claim="Another rejection", evidence_id="ev-rej2", source_id="src-rej2"),
        ]

        result_no_reject = diagnose_gaps_quantitative(
            run_id="test-run-13a",
            evidence_items=evidence,
            rejected_evidence_items=[],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        result_with_reject = diagnose_gaps_quantitative(
            run_id="test-run-13b",
            evidence_items=evidence,
            rejected_evidence_items=rejected,
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        # Severity should be >= when rejected evidence present
        for i, _ in enumerate(ALL_GAP_TYPES):
            assert result_with_reject.gaps[i].severity_score >= result_no_reject.gaps[i].severity_score

    def test_all_gap_types_present(self) -> None:
        """All 12 gap types are diagnosed."""
        inventory = _make_calibrated_gap_diagnosis_decisions()

        result = diagnose_gaps_quantitative(
            run_id="test-run-14",
            evidence_items=[_make_evidence_dict()],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        diagnosed_types = {g.gap_type for g in result.gaps}
        expected_types = set(ALL_GAP_TYPES)
        assert diagnosed_types == expected_types
        assert len(result.gaps) == 12

    def test_evidence_coverage_gap_tracked(self) -> None:
        """Evidence coverage gap count is tracked in metrics."""
        inventory = _make_calibrated_gap_diagnosis_decisions()

        result = diagnose_gaps_quantitative(
            run_id="test-run-15",
            evidence_items=[_make_evidence_dict()],
            claims=[_make_claim_dict()],
            inventory=inventory,
        )

        assert result.metrics is not None
        assert result.metrics.evidence_coverage_gap_count >= 0

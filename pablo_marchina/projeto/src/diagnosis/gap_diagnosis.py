"""Deterministic gap diagnosis — combines profile signals, validated evidence, and scores
to detect production AI gaps."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.classification.ai_native_classifier import ClassificationResult
from src.diagnosis.schemas import EvidenceTag, GapDiagnosisResult, GapWithEvidence
from src.extraction.schemas import AINativeLevel, ConfidenceLevel, StartupProfile, TechnicalGap

# Runtime-compatible aliases — replaced scoring determinístico with Any
DefensibilityScoreResult = Any
InceptionFitScoreResult = Any
ProductionReadinessResult = Any
from src.validation.evidence_validator import ValidatedEvidence

# ---------------------------------------------------------------------------
# Keyword lists per gap
# ---------------------------------------------------------------------------

_GAP_KEYWORDS: dict[TechnicalGap, list[str]] = {
    TechnicalGap.EXTERNAL_API_DEPENDENCY: [
        "gpt",
        "openai",
        "api dependency",
        "api wrapper",
        "llm api",
    ],
    TechnicalGap.HIGH_INFERENCE_COST: [
        "high volume inference",
        "inference cost",
        "gpu cost",
        "expensive inference",
        "compute cost",
    ],
    TechnicalGap.HIGH_LATENCY: [
        "low latency",
        "real-time",
        "throughput",
        "latency",
    ],
    TechnicalGap.AGENT_GOVERNANCE_GAP: [
        "agent",
        "autonomous",
        "multi-agent",
        "ai agent",
        "agentic",
    ],
    TechnicalGap.OBSERVABILITY_GAP: [
        "monitoring",
        "observability",
        "logging",
        "telemetry",
        "model monitoring",
        "drift detection",
    ],
    TechnicalGap.MODEL_EVALUATION_GAP: [
        "evaluation",
        "model eval",
        "benchmark",
        "offline eval",
        "a/b test",
    ],
    TechnicalGap.PRIVACY_OR_CONTROLLED_DEPLOYMENT_GAP: [
        "privacy",
        "on-prem",
        "controlled deployment",
        "on-premise",
        "data residency",
        "air-gapped",
    ],
    TechnicalGap.SLOW_DATA_PIPELINE: [
        "data pipeline",
        "data processing",
        "etl",
        "batch processing",
        "data ingestion",
        "streaming",
        "kafka",
        "spark",
        "feature store",
    ],
    TechnicalGap.HEAVY_TABULAR_PROCESSING: [
        "tabular",
        "structured data",
        "predictive model",
        "predictive analytics",
        "regression",
        "classification",
    ],
    TechnicalGap.VOICE_NEED: [
        "voice",
        "speech",
        "audio",
        "call center",
        "voicebot",
        "speech-to-text",
        "text-to-speech",
        "stt",
        "tts",
    ],
    TechnicalGap.SIMULATION_NEED: [
        "simulation",
        "digital twin",
        "physics simulation",
        "3d simulation",
        "rendering",
    ],
    TechnicalGap.COMPUTER_VISION_NEED: [
        "computer vision",
        "image",
        "video",
        "object detection",
        "image recognition",
        "visao computacional",
    ],
    TechnicalGap.ROBOTICS_NEED: [
        "robot",
        "robotics",
        "autonomous vehicle",
        "drone",
        "ros",
    ],
    TechnicalGap.HEALTHCARE_COMPLIANCE_NEED: [
        "healthcare",
        "hipaa",
        "medical",
        "clinical",
        "patient data",
        "health",
    ],
    TechnicalGap.AI_CYBERSECURITY_NEED: [
        "cybersecurity",
        "threat detection",
        "security",
        "intrusion detection",
        "anomaly detection",
    ],
}

# Evidence kind keywords for filtering
_EVIDENCE_GENERAL_KEYWORDS = [
    "AI signal",
    "Company desc",
    "Tech stack",
    "Customer",
    "Funding",
]

_REGULATED_SECTORS: list[str] = [
    "HealthTech",
    "FinTech",
    "LegalTech",
]

_PRIORITY_SECTORS: list[str] = [
    "HealthTech",
    "FinTech",
    "AgTech",
    "LegalTech",
    "EdTech",
]

_CONFIDENCE_TO_FACTOR: dict[ConfidenceLevel, float] = {
    ConfidenceLevel.HIGH: 1.0,
    ConfidenceLevel.MEDIUM: 0.7,
    ConfidenceLevel.LOW: 0.4,
}
_NO_EVIDENCE_FACTOR = 0.3

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _combined_text(profile: StartupProfile) -> str:
    return " ".join(
        [
            profile.description,
            profile.product_summary,
            *profile.ai_signals,
            *profile.tech_stack_signals,
            *profile.funding_signals,
            *profile.customers,
        ]
    ).lower()


def _count_keyword_matches(text: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


def _filter_evidence(
    evidence_list: list[ValidatedEvidence],
    keywords: list[str],
) -> list[ValidatedEvidence]:
    result: list[ValidatedEvidence] = []
    for ev in evidence_list:
        lower = f"{ev.claim} {ev.quote_or_evidence}".lower()
        if any(kw.lower() in lower for kw in keywords):
            result.append(ev)
    return result


def _evidence_confidence_penalty(
    evidence_list: list[ValidatedEvidence],
) -> tuple[float, ConfidenceLevel]:
    if not evidence_list:
        return _NO_EVIDENCE_FACTOR, ConfidenceLevel.LOW
    factors = [_CONFIDENCE_TO_FACTOR.get(ev.confidence, 0.4) for ev in evidence_list]
    avg = sum(factors) / len(factors)
    if avg >= 0.8:
        return avg, ConfidenceLevel.HIGH
    if avg >= 0.5:
        return avg, ConfidenceLevel.MEDIUM
    return avg, ConfidenceLevel.LOW


def _keyword_in_text(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _text_has_keywords(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


# ---------------------------------------------------------------------------
# Individual gap detectors
# ---------------------------------------------------------------------------


def _detect_gap(
    gap: TechnicalGap,
    profile: StartupProfile,
    validated_evidence: list[ValidatedEvidence],
    text: str,
) -> GapWithEvidence:
    keywords = _GAP_KEYWORDS.get(gap, [])
    evidence = _filter_evidence(validated_evidence, keywords + _EVIDENCE_GENERAL_KEYWORDS)
    _, conf = _evidence_confidence_penalty(evidence)
    kw_count = _count_keyword_matches(text, keywords) if keywords else 0
    detected = kw_count > 0 or bool(evidence)

    if not detected:
        return GapWithEvidence(
            gap=gap,
            detected=False,
            confidence=ConfidenceLevel.LOW,
            evidence_tag=EvidenceTag.HYPOTHESIS,
            reasoning=f"No signals for {gap.value} detected.",
            evidence_used=[],
        )

    if kw_count > 0 and evidence:
        tag = EvidenceTag.FACT
        confidence = conf
    elif kw_count > 0:
        tag = EvidenceTag.INFERRED
        confidence = ConfidenceLevel.LOW
    else:
        tag = EvidenceTag.HYPOTHESIS
        confidence = ConfidenceLevel.LOW

    reasons: list[str] = []
    if kw_count > 0:
        reasons.append(f"keyword matches ({kw_count})")
    if evidence:
        reasons.append(f"supporting evidence ({len(evidence)})")

    return GapWithEvidence(
        gap=gap,
        detected=True,
        confidence=confidence,
        evidence_tag=tag,
        reasoning="; ".join(reasons) + f". Gap: {gap.value}.",
        evidence_used=evidence,
    )


def _detect_external_api_dependency(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    gap = TechnicalGap.EXTERNAL_API_DEPENDENCY
    evidence = _filter_evidence(validated_evidence, _GAP_KEYWORDS[gap])
    _, conf = _evidence_confidence_penalty(evidence)
    kw_count = _count_keyword_matches(text, _GAP_KEYWORDS[gap])
    api_in_tech = _keyword_in_text(" ".join(profile.tech_stack_signals).lower(), ["gpt", "openai"])
    has_gpu_tech = _keyword_in_text(
        " ".join(profile.tech_stack_signals).lower(),
        ["pytorch", "tensorflow", "cuda", "tensorrt", "triton"],
    )
    detected = kw_count > 0 or api_in_tech

    if not detected:
        return GapWithEvidence(
            gap=gap,
            detected=False,
            confidence=ConfidenceLevel.LOW,
            evidence_tag=EvidenceTag.HYPOTHESIS,
            reasoning="No external API dependency signals.",
            evidence_used=[],
        )

    reasons: list[str] = []
    if kw_count > 0:
        reasons.append(f"keyword matches ({kw_count})")
    if api_in_tech:
        reasons.append("API dependency in tech stack")
    if not has_gpu_tech:
        reasons.append("no GPU/NVIDIA tech found — likely pure API wrapper")

    tag = EvidenceTag.FACT if evidence else EvidenceTag.INFERRED

    return GapWithEvidence(
        gap=gap,
        detected=True,
        confidence=conf if evidence else ConfidenceLevel.MEDIUM,
        evidence_tag=tag,
        reasoning="; ".join(reasons) + f". Gap: {gap.value}.",
        evidence_used=evidence,
    )


def _detect_inference_cost(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    gap = TechnicalGap.HIGH_INFERENCE_COST
    evidence = _filter_evidence(validated_evidence, _GAP_KEYWORDS[gap])
    _, conf = _evidence_confidence_penalty(evidence)
    kw_count = _count_keyword_matches(text, _GAP_KEYWORDS[gap])

    has_nvidia = _keyword_in_text(
        " ".join(profile.tech_stack_signals).lower(),
        ["pytorch", "tensorflow", "cuda", "tensorrt", "triton"],
    )
    has_inference_keywords = _keyword_in_text(
        text,
        [
            "low latency",
            "real-time",
            "inference",
            "high volume",
        ],
    )
    readiness_scale_low = (
        production_readiness is not None
        and production_readiness.score_breakdown.get("scale_and_inference") is not None
        and production_readiness.score_breakdown["scale_and_inference"].adjusted_score < 30
    )

    detected = kw_count > 0 or (has_inference_keywords and not has_nvidia)

    if not detected:
        return GapWithEvidence(
            gap=gap,
            detected=False,
            confidence=ConfidenceLevel.LOW,
            evidence_tag=EvidenceTag.HYPOTHESIS,
            reasoning="No inference cost signals.",
            evidence_used=[],
        )

    reasons: list[str] = []
    if kw_count > 0:
        reasons.append(f"keyword matches ({kw_count})")
    if has_inference_keywords and not has_nvidia:
        reasons.append("inference workload without NVIDIA tech")
    if readiness_scale_low:
        reasons.append("low scale readiness score")

    tag = EvidenceTag.FACT if evidence else EvidenceTag.INFERRED

    return GapWithEvidence(
        gap=gap,
        detected=True,
        confidence=conf if evidence else ConfidenceLevel.MEDIUM,
        evidence_tag=tag,
        reasoning="; ".join(reasons) + f". Gap: {gap.value}.",
        evidence_used=evidence,
    )


def _detect_latency(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    return _detect_gap(TechnicalGap.HIGH_LATENCY, profile, validated_evidence, text)


def _detect_agent_governance(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    gap = TechnicalGap.AGENT_GOVERNANCE_GAP
    evidence = _filter_evidence(validated_evidence, _GAP_KEYWORDS[gap])
    _, conf = _evidence_confidence_penalty(evidence)
    kw_count = _count_keyword_matches(text, _GAP_KEYWORDS[gap])

    has_guardrails = _keyword_in_text(
        " ".join(profile.ai_signals + profile.tech_stack_signals).lower(),
        ["guardrails", "governance", "safety", "alignment"],
    )

    detected = kw_count > 0 and not has_guardrails

    if not detected:
        return GapWithEvidence(
            gap=gap,
            detected=False,
            confidence=ConfidenceLevel.LOW,
            evidence_tag=EvidenceTag.HYPOTHESIS,
            reasoning="No agent governance gap detected.",
            evidence_used=evidence,
        )

    tag = EvidenceTag.FACT if evidence else EvidenceTag.INFERRED
    reasons: list[str] = [f"agent keywords ({kw_count})"]
    if not has_guardrails:
        reasons.append("no guardrails/governance found")

    return GapWithEvidence(
        gap=gap,
        detected=True,
        confidence=conf if evidence else ConfidenceLevel.MEDIUM,
        evidence_tag=tag,
        reasoning="; ".join(reasons) + f". Gap: {gap.value}.",
        evidence_used=evidence,
    )


def _detect_observability(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    gap = TechnicalGap.OBSERVABILITY_GAP
    evidence = _filter_evidence(validated_evidence, _GAP_KEYWORDS[gap])
    _, conf = _evidence_confidence_penalty(evidence)
    kw_count = _count_keyword_matches(text, _GAP_KEYWORDS[gap])

    has_observability = _keyword_in_text(
        " ".join(profile.tech_stack_signals + profile.ai_signals).lower(),
        ["monitoring", "observability", "logging", "telemetry"],
    )

    is_advanced_ai = classification is not None and classification.classification in (
        AINativeLevel.AI_ENABLED,
        AINativeLevel.AI_NATIVE,
        AINativeLevel.AI_NATIVE_SERVICE,
    )
    detected = not has_observability and is_advanced_ai

    if not detected and kw_count == 0:
        return GapWithEvidence(
            gap=gap,
            detected=False,
            confidence=ConfidenceLevel.LOW,
            evidence_tag=EvidenceTag.HYPOTHESIS,
            reasoning="No observability signals.",
            evidence_used=evidence,
        )

    detected = not has_observability
    tag = EvidenceTag.FACT if evidence else EvidenceTag.INFERRED

    return GapWithEvidence(
        gap=gap,
        detected=detected,
        confidence=conf if evidence else ConfidenceLevel.MEDIUM,
        evidence_tag=tag,
        reasoning=f"observability: kw={kw_count}, has={has_observability}. Gap: {gap.value}.",
        evidence_used=evidence,
    )


def _detect_model_evaluation(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    gap = TechnicalGap.MODEL_EVALUATION_GAP
    evidence = _filter_evidence(validated_evidence, _GAP_KEYWORDS[gap])
    _, conf = _evidence_confidence_penalty(evidence)
    kw_count = _count_keyword_matches(text, _GAP_KEYWORDS[gap])

    has_eval = kw_count > 0 or bool(evidence)
    is_ai_native = classification is not None and classification.classification in (
        AINativeLevel.AI_ENABLED,
        AINativeLevel.AI_NATIVE,
        AINativeLevel.AI_NATIVE_SERVICE,
    )

    detected = is_ai_native and not has_eval

    if not detected:
        return GapWithEvidence(
            gap=gap,
            detected=False,
            confidence=ConfidenceLevel.LOW,
            evidence_tag=EvidenceTag.HYPOTHESIS,
            reasoning="No model evaluation gap detected.",
            evidence_used=evidence,
        )

    tag = EvidenceTag.FACT if evidence else EvidenceTag.INFERRED
    return GapWithEvidence(
        gap=gap,
        detected=True,
        confidence=conf if evidence else ConfidenceLevel.LOW,
        evidence_tag=tag,
        reasoning=f"AI-native startup with no evaluation signals ({kw_count}). Gap: {gap.value}.",
        evidence_used=evidence,
    )


def _detect_privacy_deployment(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    gap = TechnicalGap.PRIVACY_OR_CONTROLLED_DEPLOYMENT_GAP
    evidence = _filter_evidence(validated_evidence, _GAP_KEYWORDS[gap])
    _, conf = _evidence_confidence_penalty(evidence)
    kw_count = _count_keyword_matches(text, _GAP_KEYWORDS[gap])

    in_regulated = profile.sector in _REGULATED_SECTORS
    has_privacy_tech = _keyword_in_text(
        " ".join(profile.tech_stack_signals).lower(),
        ["kubernetes", "docker", "on-prem"],
    )

    detected = in_regulated or kw_count > 0

    if not detected:
        return GapWithEvidence(
            gap=gap,
            detected=False,
            confidence=ConfidenceLevel.LOW,
            evidence_tag=EvidenceTag.HYPOTHESIS,
            reasoning="No privacy/controlled deployment gap detected.",
            evidence_used=evidence,
        )

    reasons: list[str] = []
    if in_regulated:
        reasons.append(f"regulated sector: {profile.sector}")
    if kw_count > 0:
        reasons.append(f"keyword matches ({kw_count})")
    if has_privacy_tech:
        reasons.append("has deployment tech (mitigating)")

    tag = EvidenceTag.FACT if evidence else EvidenceTag.INFERRED
    return GapWithEvidence(
        gap=gap,
        detected=True,
        confidence=conf if evidence else ConfidenceLevel.MEDIUM,
        evidence_tag=tag,
        reasoning="; ".join(reasons) + f". Gap: {gap.value}.",
        evidence_used=evidence,
    )


def _detect_data_pipeline(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    gap = TechnicalGap.SLOW_DATA_PIPELINE
    evidence = _filter_evidence(validated_evidence, _GAP_KEYWORDS[gap])
    _, conf = _evidence_confidence_penalty(evidence)
    kw_count = _count_keyword_matches(text, _GAP_KEYWORDS[gap])

    has_data_tech = _keyword_in_text(
        " ".join(profile.tech_stack_signals).lower(),
        [
            "kafka",
            "spark",
            "hadoop",
            "airflow",
            "snowflake",
            "bigquery",
            "redshift",
            "data pipeline",
        ],
    )

    detected = kw_count > 0 or (
        has_data_tech
        and not _keyword_in_text(
            " ".join(profile.tech_stack_signals).lower(),
            ["rapids", "cudf", "cuml"],
        )
    )

    if not detected:
        return GapWithEvidence(
            gap=gap,
            detected=False,
            confidence=ConfidenceLevel.LOW,
            evidence_tag=EvidenceTag.HYPOTHESIS,
            reasoning="No data pipeline signals.",
            evidence_used=evidence,
        )

    tag = EvidenceTag.FACT if evidence else EvidenceTag.INFERRED
    reasons: list[str] = []
    if kw_count > 0:
        reasons.append(f"keyword matches ({kw_count})")
    if has_data_tech:
        reasons.append("data tech present (potential optimization area)")

    return GapWithEvidence(
        gap=gap,
        detected=True,
        confidence=conf if evidence else ConfidenceLevel.MEDIUM,
        evidence_tag=tag,
        reasoning="; ".join(reasons) + f". Gap: {gap.value}.",
        evidence_used=evidence,
    )


def _detect_tabular_processing(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    return _detect_gap(TechnicalGap.HEAVY_TABULAR_PROCESSING, profile, validated_evidence, text)


def _detect_voice_need(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    return _detect_gap(TechnicalGap.VOICE_NEED, profile, validated_evidence, text)


def _detect_simulation_need(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    return _detect_gap(TechnicalGap.SIMULATION_NEED, profile, validated_evidence, text)


def _detect_computer_vision_need(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    return _detect_gap(TechnicalGap.COMPUTER_VISION_NEED, profile, validated_evidence, text)


def _detect_robotics_need(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    return _detect_gap(TechnicalGap.ROBOTICS_NEED, profile, validated_evidence, text)


def _detect_healthcare_compliance(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    gap = TechnicalGap.HEALTHCARE_COMPLIANCE_NEED
    evidence = _filter_evidence(validated_evidence, _GAP_KEYWORDS[gap])
    _, conf = _evidence_confidence_penalty(evidence)
    kw_count = _count_keyword_matches(text, _GAP_KEYWORDS[gap])

    in_health = profile.sector == "HealthTech"
    detected = in_health or kw_count > 0

    if not detected:
        return GapWithEvidence(
            gap=gap,
            detected=False,
            confidence=ConfidenceLevel.LOW,
            evidence_tag=EvidenceTag.HYPOTHESIS,
            reasoning="No healthcare compliance signals.",
            evidence_used=evidence,
        )

    tag = EvidenceTag.FACT if evidence else EvidenceTag.INFERRED
    reasons: list[str] = []
    if in_health:
        reasons.append("HealthTech sector")
    if kw_count > 0:
        reasons.append(f"keyword matches ({kw_count})")

    return GapWithEvidence(
        gap=gap,
        detected=True,
        confidence=(conf if evidence else ConfidenceLevel.HIGH if in_health else ConfidenceLevel.MEDIUM),
        evidence_tag=tag,
        reasoning="; ".join(reasons) + f". Gap: {gap.value}.",
        evidence_used=evidence,
    )


def _detect_cybersecurity_need(
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None,
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    text: str,
) -> GapWithEvidence:
    return _detect_gap(TechnicalGap.AI_CYBERSECURITY_NEED, profile, validated_evidence, text)


# ---------------------------------------------------------------------------
# Registration of all detectors
# ---------------------------------------------------------------------------

_DETECTORS: list[tuple[TechnicalGap, Callable]] = [
    (TechnicalGap.EXTERNAL_API_DEPENDENCY, _detect_external_api_dependency),
    (TechnicalGap.HIGH_INFERENCE_COST, _detect_inference_cost),
    (TechnicalGap.HIGH_LATENCY, _detect_latency),
    (TechnicalGap.AGENT_GOVERNANCE_GAP, _detect_agent_governance),
    (TechnicalGap.OBSERVABILITY_GAP, _detect_observability),
    (TechnicalGap.MODEL_EVALUATION_GAP, _detect_model_evaluation),
    (TechnicalGap.PRIVACY_OR_CONTROLLED_DEPLOYMENT_GAP, _detect_privacy_deployment),
    (TechnicalGap.SLOW_DATA_PIPELINE, _detect_data_pipeline),
    (TechnicalGap.HEAVY_TABULAR_PROCESSING, _detect_tabular_processing),
    (TechnicalGap.VOICE_NEED, _detect_voice_need),
    (TechnicalGap.SIMULATION_NEED, _detect_simulation_need),
    (TechnicalGap.COMPUTER_VISION_NEED, _detect_computer_vision_need),
    (TechnicalGap.ROBOTICS_NEED, _detect_robotics_need),
    (TechnicalGap.HEALTHCARE_COMPLIANCE_NEED, _detect_healthcare_compliance),
    (TechnicalGap.AI_CYBERSECURITY_NEED, _detect_cybersecurity_need),
]

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def diagnose_gaps(
    startup_name: str,
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    production_readiness: ProductionReadinessResult | None = None,
    defensibility: DefensibilityScoreResult | None = None,
    inception_fit: InceptionFitScoreResult | None = None,
) -> GapDiagnosisResult:
    """Run all gap detectors and return a structured diagnosis.

    Parameters
    ----------
    startup_name:
        Name of the startup being diagnosed.
    profile:
        Extracted startup profile with signals and evidence.
    classification:
        AI-native classification result.
    validated_evidence:
        Evidence objects with kind and confidence already validated.
    production_readiness:
        Production Readiness result (optional).
    defensibility:
        Defensibility Score result (optional).
    inception_fit:
        Inception Fit Score result (optional).

    Returns
    -------
    GapDiagnosisResult
        All diagnosed gaps with evidence, confidence, reasoning, and
        missing evidence.
    """
    text = _combined_text(profile)

    detected_gaps: list[GapWithEvidence] = []
    all_evidence: list[ValidatedEvidence] = []
    missing: list[str] = []

    for gap, detector in _DETECTORS:
        result = detector(
            profile,
            classification,
            validated_evidence,
            production_readiness,
            defensibility,
            inception_fit,
            text,
        )
        detected_gaps.append(result)
        all_evidence.extend(result.evidence_used)

        if result.detected and result.evidence_tag == EvidenceTag.INFERRED:
            missing.append(f"Gap '{gap.value}' detected by inference only — collect direct evidence to confirm.")

    conf_factors = [_CONFIDENCE_TO_FACTOR.get(g.confidence, 0.4) for g in detected_gaps if g.detected]
    if conf_factors:
        avg_conf = sum(conf_factors) / len(conf_factors)
        if avg_conf >= 0.8:
            overall_conf = ConfidenceLevel.HIGH
        elif avg_conf >= 0.5:
            overall_conf = ConfidenceLevel.MEDIUM
        else:
            overall_conf = ConfidenceLevel.LOW
    else:
        overall_conf = ConfidenceLevel.LOW

    detected_names = [g.gap.value for g in detected_gaps if g.detected]
    lines: list[str] = [
        f"Gap Diagnosis for {startup_name}",
        f"Overall confidence: {overall_conf.value}",
        f"Gaps detected: {len([g for g in detected_gaps if g.detected])}",
    ]
    if detected_names:
        lines.append(f"Detected: {', '.join(detected_names)}")
    lines.append("")
    for g in detected_gaps:
        status = "✅" if g.detected else "⬜"
        lines.append(
            f"  {status} {g.gap.value}: detected={g.detected}, conf={g.confidence.value}, tag={g.evidence_tag.value}"
        )
        lines.append(f"    reasoning: {g.reasoning}")
    if missing:
        lines.append("")
        lines.append("Missing evidence:")
        for m in missing:
            lines.append(f"  - {m}")

    return GapDiagnosisResult(
        startup_name=startup_name,
        diagnosed_gaps=detected_gaps,
        confidence=overall_conf,
        reasoning="\n".join(lines),
        evidence_used=all_evidence,
        missing_evidence=missing,
    )

"""Heuristic AI-native classification from a StartupProfile."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.extraction.schemas import AINativeLevel, ConfidenceLevel, Evidence, StartupProfile


class ClassificationResult(BaseModel):
    startup_name: str
    classification: AINativeLevel
    confidence: ConfidenceLevel
    reasoning: str
    evidence_used: list[Evidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    probabilities: dict[str, float] = Field(default_factory=dict)
    uncertainty: float = 1.0
    model_version: str = "heuristic-prior-v1"
    model_available: bool = False
    classification_features: list[str] = Field(default_factory=list)


_CORE_PATTERNS: list[str] = [
    "ai-powered",
    "ai platform",
    "powered by ai",
    "ai-native",
    "uses machine learning",
    "uses deep learning",
    "deep learning for",
    "our ai",
    "llm",
    "large language model",
    "nlp platform",
    "computer vision to",
    "predictive model",
    "ai-driven",
    "baseado em ia",
    "inteligencia artificial",
    "inteligência artificial",
    "llm-powered",
    "modelo de linguagem",
    "aprendizado de maquina",
    "ia generativa",
    "generative ai",
]

_ENABLED_PATTERNS: list[str] = [
    "ai features",
    "includes ai",
    "ai capabilities",
    "with ai",
    "ai functionality",
    "recursos de ia",
    "funcionalidades de ia",
]

_SERVICE_PATTERNS: list[str] = [
    "proprietary data",
    "exclusive data",
    "dados proprietarios",
    "workflow integration",
    "process automation",
    "automacao de processos",
    "custom model",
    "trained on",
    "fine-tuned",
    "fine tuning",
    "professional services",
    "vertical solution",
    "industry-specific",
    "enterprise integration",
    "dados exclusivos",
    "integracao de workflow",
]

_AI_TECH_KEYWORDS: list[str] = [
    "tensorflow",
    "pytorch",
    "langchain",
    "hugging face",
    "transformers",
    "keras",
    "jax",
    "onnx",
    "mlflow",
    "kubeflow",
    "ray",
    "spark ml",
]


def _count_matches(text: str, patterns: list[str]) -> int:
    text_lower = text.lower()
    return sum(1 for p in patterns if p in text_lower)


def _extract_matched(text: str, patterns: list[str]) -> list[str]:
    text_lower = text.lower()
    return [p for p in patterns if p in text_lower]


def _pick_confidence(
    classification: AINativeLevel,
    ai_count: int,
    profile_score: float,
    core_score: int,
) -> ConfidenceLevel:
    if profile_score < 0.3:
        return ConfidenceLevel.LOW

    if classification == AINativeLevel.NON_AI:
        return ConfidenceLevel.HIGH if profile_score > 0.3 else ConfidenceLevel.MEDIUM

    if classification == AINativeLevel.AI_ASSISTED:
        return ConfidenceLevel.LOW

    if classification == AINativeLevel.AI_ENABLED:
        return ConfidenceLevel.MEDIUM if ai_count >= 3 else ConfidenceLevel.LOW

    if classification == AINativeLevel.AI_NATIVE:
        return ConfidenceLevel.HIGH if ai_count >= 7 and core_score >= 4 else ConfidenceLevel.MEDIUM

    if classification == AINativeLevel.AI_NATIVE_SERVICE:
        return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.LOW


def _build_missing_evidence(classification: AINativeLevel) -> list[str]:
    missing: list[str] = []

    if classification in (AINativeLevel.NON_AI, AINativeLevel.AI_ASSISTED):
        missing.append("Evidence that AI is part of the product offering")
    if classification in (
        AINativeLevel.NON_AI,
        AINativeLevel.AI_ASSISTED,
        AINativeLevel.AI_ENABLED,
    ):
        missing.append("Evidence that the product depends on AI for core value")
    if classification in (
        AINativeLevel.NON_AI,
        AINativeLevel.AI_ASSISTED,
        AINativeLevel.AI_ENABLED,
        AINativeLevel.AI_NATIVE,
    ):
        missing.append("Evidence of proprietary data or workflow integration (required for AI-native service)")

    return missing


def _build_reasoning(
    classification: AINativeLevel,
    ai_count: int,
    core_score: int,
    enabled_score: int,
    service_score: int,
    tech_score: int,
    matched_core: list[str],
    matched_service: list[str],
) -> str:
    parts: list[str] = []

    if classification == AINativeLevel.NON_AI:
        return "No AI signals detected in the available evidence."

    if classification == AINativeLevel.AI_ASSISTED:
        parts.append(f"{ai_count} AI signal(s) found")
        parts.append("no evidence that AI is part of the product offering")
        return ". ".join(parts) + "."

    if classification == AINativeLevel.AI_ENABLED:
        parts.append(f"AI signals found ({ai_count})")
        parts.append("product mentions AI features but AI is not the core value driver")
        if matched_core:
            parts.append(f"core pattern(s) matched: {', '.join(matched_core[:3])}")
        return ". ".join(parts) + "."

    if classification == AINativeLevel.AI_NATIVE:
        parts.append(f"strong AI signals ({ai_count}) with core dependency score {core_score}")
        parts.append("product explicitly depends on AI for core value delivery")
        if matched_core:
            parts.append(f"patterns: {', '.join(matched_core[:4])}")
        return ". ".join(parts) + "."

    if classification == AINativeLevel.AI_NATIVE_SERVICE:
        parts.append(
            f"AI-native (score {core_score}) with service indicators "
            f"({service_score}): {', '.join(matched_service[:3])}"
        )
        parts.append("combines AI with proprietary data or workflow integration")
        return ". ".join(parts) + "."

    return "Classification could not be determined."


def classify_ai_native(profile: StartupProfile) -> ClassificationResult:
    """Classify a startup's AI-native maturity using heuristic rules only.

    Parameters
    ----------
    profile:
        A validated ``StartupProfile`` with extracted signals and evidence.

    Returns
    -------
    ClassificationResult
        The classification level, confidence, reasoning, evidence used,
        and a list of evidence gaps.
    """
    combined = f"{profile.product_summary} {profile.description}"
    ai_count = len(profile.ai_signals)

    core_score = _count_matches(combined, _CORE_PATTERNS)
    enabled_score = _count_matches(combined, _ENABLED_PATTERNS)
    service_score = _count_matches(combined, _SERVICE_PATTERNS)

    tech_text = " ".join(profile.tech_stack_signals).lower()
    tech_score = _count_matches(tech_text, _AI_TECH_KEYWORDS)

    matched_core = _extract_matched(combined, _CORE_PATTERNS)
    matched_service = _extract_matched(combined, _SERVICE_PATTERNS)

    if ai_count == 0 and core_score == 0:
        classification = AINativeLevel.NON_AI
    elif service_score >= 2 and core_score >= 2 and ai_count >= 3:
        classification = AINativeLevel.AI_NATIVE_SERVICE
    elif core_score >= 4 and ai_count >= 5:
        classification = AINativeLevel.AI_NATIVE
    elif core_score >= 2 or enabled_score >= 1 or (ai_count >= 3 and core_score >= 1):
        classification = AINativeLevel.AI_ENABLED
    else:
        classification = AINativeLevel.AI_ASSISTED

    confidence = _pick_confidence(classification, ai_count, profile.confidence_score, core_score)
    missing = _build_missing_evidence(classification)
    reasoning = _build_reasoning(
        classification,
        ai_count,
        core_score,
        enabled_score,
        service_score,
        tech_score,
        matched_core,
        matched_service,
    )

    evidence_used: list[Evidence] = [
        s
        for s in profile.sources
        if any(kw in s.claim.lower() for kw in ("ai signal", "tech stack", "company description", "funding"))
    ]
    from src.classification.ai_native_model import predict_ai_native

    prediction = predict_ai_native(
        profile,
        heuristic_classification=classification,
        heuristic_confidence=confidence,
    )

    return ClassificationResult(
        startup_name=profile.startup_name,
        classification=classification,
        confidence=confidence,
        reasoning=reasoning,
        evidence_used=evidence_used,
        missing_evidence=missing,
        probabilities=prediction.probabilities,
        uncertainty=prediction.uncertainty,
        model_version=prediction.model_version,
        model_available=prediction.model_available,
        classification_features=prediction.features_used,
    )

# ruff: noqa: E501

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.classification.ai_native_classifier import ClassificationResult
from src.diagnosis.schemas import EvidenceTag, GapDiagnosisResult, GapWithEvidence
from src.extraction.schemas import (
    ConfidenceLevel,
    ImplementationComplexity,
    RecommendationPriority,
    StartupProfile,
    TechnicalGap,
)
from src.quality.decision_calibration_registry import (
    DecisionCalibrationRecord,
    get_project_decision_inventory,
    validate_decision_for_production,
)
from src.rag.schemas import RagPipelineOutput
from src.recommendation.schemas import (
    PerGapRecommendation,
    RecommendationResult,
    RecommendedNextAction,
    SuggestedTechnicalExperiment,
)
# Runtime-compatible aliases — replaced scoring determinístico with Any
CompositeResult = Any
DefensibilityScoreResult = Any
InceptionFitScoreResult = Any
ProductionReadinessResult = Any
from src.validation.evidence_validator import ValidatedEvidence

_COMPLEXITY_MAP: dict[str, ImplementationComplexity] = {
    "NVIDIA NIM": ImplementationComplexity.LOW,
    "cuDF": ImplementationComplexity.LOW,
    "cuML": ImplementationComplexity.LOW,
    "TensorRT-LLM": ImplementationComplexity.MEDIUM,
    "Triton Inference Server": ImplementationComplexity.MEDIUM,
    "NVIDIA RAPIDS": ImplementationComplexity.MEDIUM,
    "NVIDIA Riva": ImplementationComplexity.MEDIUM,
    "NVIDIA NeMo": ImplementationComplexity.MEDIUM,
    "NeMo Guardrails": ImplementationComplexity.MEDIUM,
    "NVIDIA TensorRT": ImplementationComplexity.MEDIUM,
    "MONAI": ImplementationComplexity.MEDIUM,
    "NVIDIA Omniverse": ImplementationComplexity.HIGH,
    "NVIDIA Isaac": ImplementationComplexity.HIGH,
    "NVIDIA Clara": ImplementationComplexity.HIGH,
    "NVIDIA Morpheus": ImplementationComplexity.HIGH,
    "NVIDIA AI Enterprise": ImplementationComplexity.HIGH,
}

_EXPERIMENT_TEMPLATES: dict[TechnicalGap, dict[str, str]] = {
    TechnicalGap.HIGH_INFERENCE_COST: {
        "title": "Benchmark inference cost with TensorRT-LLM",
        "hypothesis": "TensorRT-LLM reduz custo por 1k requests em pelo menos 40% vs solucao atual",
        "metric": "custo por 1k requests (USD)",
        "duration": "2-4 semanas",
        "step": "Agendar acesso ao NVIDIA LaunchPad para TensorRT-LLM",
    },
    TechnicalGap.HIGH_LATENCY: {
        "title": "Benchmark latency p50/p95 with Triton Inference Server",
        "hypothesis": "Triton Inference Server reduz latencia p50 em 50% e p95 em 60% vs solucao atual",
        "metric": "latencia p50 e p95 (ms)",
        "duration": "2-4 semanas",
        "step": "Configurar Triton Inference Server com modelo atual da startup",
    },
    TechnicalGap.EXTERNAL_API_DEPENDENCY: {
        "title": "Benchmark NIM self-hosted inference cost vs external API",
        "hypothesis": "NIM auto-hospedado reduz custo de inferencia em 60% vs API externa (ex.: OpenAI)",
        "metric": "custo por 1k requests, latencia p50",
        "duration": "3-5 semanas",
        "step": "Solicitar acesso ao NVIDIA NIM para o modelo de maior uso da startup",
    },
    TechnicalGap.AGENT_GOVERNANCE_GAP: {
        "title": "Evaluate NeMo Guardrails for agent safety",
        "hypothesis": "NeMo Guardrails detecta e bloqueia pelo menos 90% dos comportamentos nao autorizados em agentes LLM",
        "metric": "taxa de deteccao de violacoes, false positive rate",
        "duration": "4-6 semanas",
        "step": "Workshop de integracao NeMo Guardrails com arquiteto NVIDIA",
    },
    TechnicalGap.SLOW_DATA_PIPELINE: {
        "title": "Benchmark ETL throughput with RAPIDS cuDF",
        "hypothesis": "cuDF acelera pipeline ETL em pelo menos 5x vs CPU para datasets > 10GB",
        "metric": "throughput (GB/s), tempo total de ETL",
        "duration": "2-4 semanas",
        "step": "Portar pipeline ETL atual para cuDF com suporte NVIDIA",
    },
    TechnicalGap.HEAVY_TABULAR_PROCESSING: {
        "title": "Benchmark ML training speed with cuML",
        "hypothesis": "cuML reduz tempo de treinamento em pelo menos 3x vs sklearn para datasets tabulares",
        "metric": "tempo de treinamento (segundos), accuracy comparada",
        "duration": "2-4 semanas",
        "step": "Executar benchmark cuML vs sklearn com dataset representativo da startup",
    },
    TechnicalGap.PRIVACY_OR_CONTROLLED_DEPLOYMENT_GAP: {
        "title": "Validate on-prem deployment with NVIDIA AI Enterprise",
        "hypothesis": "NVIDIA AI Enterprise suporta deploy on-prem com soberania de dados e compliance regulatorio",
        "metric": "tempo de setup, conformidade com requisitos de privacidade",
        "duration": "4-8 semanas",
        "step": "Reuniao com arquiteto NVIDIA para definir requisitos de deploy controlado",
    },
    TechnicalGap.VOICE_NEED: {
        "title": "Benchmark Riva STT/TTS accuracy and latency",
        "hypothesis": "Riva oferece STT com WER < 5% e latencia < 200ms para audio em portugues brasileiro",
        "metric": "WER (Word Error Rate), latencia STT/TTS",
        "duration": "3-5 semanas",
        "step": "Avaliar Riva com amostras de audio da aplicacao da startup",
    },
    TechnicalGap.COMPUTER_VISION_NEED: {
        "title": "Benchmark CV inference throughput with TensorRT",
        "hypothesis": "TensorRT otimiza inferencia CV para throughput 3x maior vs framework original",
        "metric": "throughput (fps), latencia por frame",
        "duration": "2-4 semanas",
        "step": "Otimizar modelo CV da startup com TensorRT",
    },
    TechnicalGap.OBSERVABILITY_GAP: {
        "title": "Evaluate AI Enterprise monitoring for production ML",
        "hypothesis": "NVIDIA AI Enterprise fornece monitoramento de modelos com deteccao de drift em tempo real",
        "metric": "tempo de deteccao de drift, cobertura de metricas",
        "duration": "4-6 semanas",
        "step": "Workshop de observabilidade ML com NVIDIA AI Enterprise",
    },
    TechnicalGap.MODEL_EVALUATION_GAP: {
        "title": "Evaluate NeMo evaluation harness for LLM benchmarking",
        "hypothesis": "NeMo fornece harness de avaliacao comparavel a padroes da industria para LLMs",
        "metric": "accuracy, precision, recall em benchmark set",
        "duration": "3-5 semanas",
        "step": "Configurar NeMo evaluation harness com dataset de validacao da startup",
    },
    TechnicalGap.SIMULATION_NEED: {
        "title": "Prototype digital twin with Omniverse",
        "hypothesis": "Omniverse permite criar digital twin funcional em 4 semanas para simulacao fisica",
        "metric": "tempo de prototipagem, fidelidade da simulacao",
        "duration": "4-8 semanas",
        "step": "Workshop Omniverse com equipe de engenharia da startup",
    },
    TechnicalGap.ROBOTICS_NEED: {
        "title": "Evaluate Isaac Sim for robotics training pipeline",
        "hypothesis": "Isaac Sim reduz tempo de treinamento de modelos roboticos em 50% via simulacao",
        "metric": "tempo de treinamento, transfer learning success rate",
        "duration": "6-10 semanas",
        "step": "Avaliacao tecnica Isaac Sim com caso de uso robotico da startup",
    },
    TechnicalGap.HEALTHCARE_COMPLIANCE_NEED: {
        "title": "Validate Clara/MONAI compliance for healthcare deployment",
        "hypothesis": "Clara e MONAI fornecem ferramentas compliance-ready para IA em saude com suporte HIPAA",
        "metric": "cobertura de compliance, tempo de auditoria",
        "duration": "4-8 semanas",
        "step": "Consultoria de compliance NVIDIA Clara com time regulatorio da startup",
    },
    TechnicalGap.AI_CYBERSECURITY_NEED: {
        "title": "Benchmark Morpheus threat detection throughput",
        "hypothesis": "Morpheus processa deteccao de ameacas em tempo real com throughput 10x maior vs CPU",
        "metric": "throughput (eventos/segundo), latencia de deteccao",
        "duration": "4-6 semanas",
        "step": "Prova de conceito Morpheus com dados de rede da startup",
    },
}


def _determine_action(
    gap: GapWithEvidence,
    recommended_motion: str,
) -> RecommendedNextAction:
    if recommended_motion == "not_recommended":
        return RecommendedNextAction.NOT_RECOMMENDED

    if not gap.detected:
        return RecommendedNextAction.MONITOR

    if gap.confidence == ConfidenceLevel.LOW:
        return RecommendedNextAction.VALIDATE_MANUALLY

    if recommended_motion in ("lack_evidence_more_research",):
        return RecommendedNextAction.VALIDATE_MANUALLY

    if recommended_motion in ("monitor_and_nurture",) and gap.confidence in (
        ConfidenceLevel.LOW,
        ConfidenceLevel.MEDIUM,
    ):
        return RecommendedNextAction.MONITOR

    if gap.confidence == ConfidenceLevel.HIGH and recommended_motion in (
        "immediate_outreach",
        "high_priority_outreach",
    ):
        return RecommendedNextAction.APPROACH_NOW

    return RecommendedNextAction.VALIDATE_MANUALLY


def _determine_priority(
    action: RecommendedNextAction,
    gap_confidence: ConfidenceLevel,
) -> RecommendationPriority:
    if action == RecommendedNextAction.APPROACH_NOW:
        if gap_confidence == ConfidenceLevel.HIGH:
            return RecommendationPriority.HIGH
        return RecommendationPriority.MEDIUM

    if action == RecommendedNextAction.VALIDATE_MANUALLY:
        if gap_confidence == ConfidenceLevel.HIGH:
            return RecommendationPriority.MEDIUM
        return RecommendationPriority.LOW

    return RecommendationPriority.LOW


def _compute_overall_priority(
    recommendations: list[PerGapRecommendation],
) -> RecommendationPriority:
    priorities = {r.priority for r in recommendations if r.detected}
    if RecommendationPriority.HIGH in priorities:
        return RecommendationPriority.HIGH
    if RecommendationPriority.MEDIUM in priorities:
        return RecommendationPriority.MEDIUM
    return RecommendationPriority.LOW


def _compute_overall_confidence(
    recommendations: list[PerGapRecommendation],
) -> ConfidenceLevel:
    detected = [r for r in recommendations if r.detected]
    if not detected:
        return ConfidenceLevel.LOW

    confidences = [r.confidence for r in detected]
    if all(c == ConfidenceLevel.HIGH for c in confidences):
        return ConfidenceLevel.HIGH
    if any(c == ConfidenceLevel.HIGH for c in confidences):
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _determine_complexity(tech_name: str) -> ImplementationComplexity:
    return _COMPLEXITY_MAP.get(tech_name, ImplementationComplexity.MEDIUM)


def _build_technical_justification(
    gap: GapWithEvidence,
    tech_names: list[str],
) -> str:
    if not tech_names:
        return ""
    tech_list = ", ".join(tech_names)
    tag = gap.evidence_tag.value
    return (
        f"Gap '{gap.gap.value}' was {tag} (confidence: {gap.confidence.value}). "
        f"Recommended technologies: {tech_list}. "
        f"{gap.reasoning}"
    )


def _build_business_justification(
    gap: GapWithEvidence,
    profile: StartupProfile,
    classification: ClassificationResult,
    recommended_motion: str,
) -> str:
    sector = profile.sector
    ai_level = classification.classification.value
    return (
        f"Startup {profile.startup_name} ({sector}, {ai_level}) presents "
        f"a {gap.confidence.value}-confidence {gap.evidence_tag.value} gap "
        f"in '{gap.gap.value}'. "
        f"NVIDIA recommended motion: {recommended_motion}. "
        f"Addressing this gap creates opportunity for NVIDIA technology adoption."
    )


def _suggest_experiment(
    gap: TechnicalGap,
    top_tech: str,
) -> SuggestedTechnicalExperiment | None:
    template = _EXPERIMENT_TEMPLATES.get(gap)
    if template is None:
        return None
    return SuggestedTechnicalExperiment(
        title=template["title"],
        target_gap=gap,
        hypothesis=template["hypothesis"],
        success_metric=template["metric"],
        estimated_duration=template["duration"],
        nvidia_technology=top_tech,
        next_step=template["step"],
    )


def build_per_gap_recommendation(
    gap: GapWithEvidence,
    tech_names: list[str],
    profile: StartupProfile,
    classification: ClassificationResult,
    recommended_motion: str,
    rag_context: RagPipelineOutput | None = None,
) -> PerGapRecommendation:
    if rag_context is not None and rag_context.missing_context:
        return PerGapRecommendation(
            diagnosed_gap=gap.gap,
            detected=gap.detected,
            recommended_nvidia_technologies=[],
            technical_justification="RAG context unavailable — cannot recommend NVIDIA technologies without evidence.",
            business_justification="",
            priority=RecommendationPriority.LOW,
            implementation_complexity=ImplementationComplexity.MEDIUM,
            suggested_experiment=None,
            action=RecommendedNextAction.NOT_RECOMMENDED,
            next_action_for_nvidia_team="Ingest NVIDIA corpus and verify RAG pipeline before making recommendations.",
            evidence_used=[],
            missing_evidence=[f"RAG context missing: {rag_context.rag_quality_summary}"],
            confidence=ConfidenceLevel.LOW,
        )
    action = _determine_action(gap, recommended_motion)
    priority = _determine_priority(action, gap.confidence)

    max_complexity = ImplementationComplexity.LOW
    for t in tech_names:
        c = _determine_complexity(t)
        if c.value > max_complexity.value:
            max_complexity = c

    missing: list[str] = []
    if gap.evidence_tag == EvidenceTag.INFERRED:
        missing.append(f"Gap '{gap.gap.value}' detected by inference only — collect direct evidence to confirm.")

    experiment = None
    if action == RecommendedNextAction.APPROACH_NOW and tech_names:
        experiment = _suggest_experiment(gap.gap, tech_names[0])

    next_action = ""
    if action == RecommendedNextAction.APPROACH_NOW:
        if experiment:
            next_action = experiment.next_step
        else:
            next_action = f"Contact startup to discuss {', '.join(tech_names)} adoption"
    elif action == RecommendedNextAction.VALIDATE_MANUALLY:
        next_action = (
            f"Manually validate gap '{gap.gap.value}' — "
            f"current evidence is {gap.evidence_tag.value} with {gap.confidence.value} confidence"
        )
    elif action == RecommendedNextAction.MONITOR:
        next_action = f"Monitor startup for signals related to '{gap.gap.value}'"
    else:
        next_action = "No action recommended at this time"

    return PerGapRecommendation(
        diagnosed_gap=gap.gap,
        detected=gap.detected,
        recommended_nvidia_technologies=tech_names,
        technical_justification=_build_technical_justification(gap, tech_names),
        business_justification=_build_business_justification(gap, profile, classification, recommended_motion),
        priority=priority,
        implementation_complexity=max_complexity,
        suggested_experiment=experiment,
        action=action,
        next_action_for_nvidia_team=next_action,
        evidence_used=gap.evidence_used,
        missing_evidence=missing,
        confidence=gap.confidence,
    )


def build_recommendations(
    startup_name: str,
    profile: StartupProfile,
    classification: ClassificationResult,
    validated_evidence: list[ValidatedEvidence],
    defensibility: DefensibilityScoreResult | None,
    inception_fit: InceptionFitScoreResult | None,
    production_readiness: ProductionReadinessResult | None,
    composite: CompositeResult | None,
    final_priority_score: float,
    recommended_motion: str,
    gap_diagnosis: GapDiagnosisResult,
    rag_context: RagPipelineOutput | None = None,
) -> RecommendationResult:
    recommendations: list[PerGapRecommendation] = []

    for gap in gap_diagnosis.diagnosed_gaps:
        tech_names = [
            c.technology_name for c in gap_diagnosis.nvidia_technology_candidates if c.addresses_gap == gap.gap
        ]

        rec = build_per_gap_recommendation(
            gap=gap,
            tech_names=tech_names,
            profile=profile,
            classification=classification,
            recommended_motion=recommended_motion,
            rag_context=rag_context,
        )
        recommendations.append(rec)

    overall_priority = _compute_overall_priority(recommendations)
    overall_confidence = _compute_overall_confidence(recommendations)

    top: PerGapRecommendation | None = None
    for r in recommendations:
        if r.action == RecommendedNextAction.APPROACH_NOW:
            if top is None or r.priority.value > top.priority.value:
                top = r

    all_evidence: list[ValidatedEvidence] = list(validated_evidence)
    all_missing: list[str] = list(gap_diagnosis.missing_evidence)
    for r in recommendations:
        if r.detected:
            all_missing.extend(r.missing_evidence)

    lines: list[str] = [
        f"Recommendations for {startup_name}",
        f"Overall priority: {overall_priority.value}",
        f"Overall confidence: {overall_confidence.value}",
        f"Gaps diagnosed: {len([r for r in recommendations if r.detected])}",
        f"Recommendations generated: {len(recommendations)}",
    ]
    for r in recommendations:
        lines.append(
            f"  [{r.action.value}] {r.diagnosed_gap.value}: "
            f"priority={r.priority.value}, "
            f"confidence={r.confidence.value}, "
            f"techs={len(r.recommended_nvidia_technologies)}"
        )

    return RecommendationResult(
        startup_name=startup_name,
        overall_priority=overall_priority,
        overall_confidence=overall_confidence,
        recommendations=recommendations,
        top_recommendation=top,
        reasoning="\n".join(lines),
        evidence_used=all_evidence,
        missing_evidence=all_missing,
    )


# ---------------------------------------------------------------------------
# Mapping-based recommendation models
# ---------------------------------------------------------------------------


class RecommendationRankingStatus(str, Enum):
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"
    BLOCKED_NO_NVIDIA_MAPPINGS = "blocked_no_nvidia_mappings"
    BLOCKED_UNCALIBRATED_MAPPING = "blocked_uncalibrated_mapping"
    BLOCKED_UNCALIBRATED_RECOMMENDATION = "blocked_uncalibrated_recommendation"
    FAILED = "failed"


class NvidiaRecommendationRecord(BaseModel):
    recommendation_id: str
    gap_id: str
    gap_type: str
    nvidia_technology: str
    recommendation_type: str = "technology_adoption"
    reason: str
    mapping_score: float = Field(default=0.0, ge=0.0, le=1.0)
    mapping_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    recommendation_priority_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: float = Field(default=1.0, ge=0.0, le=1.0)
    business_impact: float = Field(default=0.5, ge=0.0, le=1.0)
    implementation_complexity: float = Field(default=0.5, ge=0.0, le=1.0)
    supporting_rag_context_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    calibration_decision_ids: list[str] = Field(default_factory=list)
    production_allowed: bool = False
    blockers: list[str] = Field(default_factory=list)
    recommendation_action: str = "not_recommended"
    next_best_action: str = ""
    evidence_support_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rag_support_score: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_utility: float = Field(default=0.0, ge=0.0, le=1.0)
    why_not: list[str] = Field(default_factory=list)


class NvidiaRecommendationMetrics(BaseModel):
    mapping_count: int = 0
    production_allowed_mapping_count: int = 0
    recommendation_count: int = 0
    production_allowed_recommendation_count: int = 0
    blocked_recommendation_count: int = 0
    needs_review_recommendation_count: int = 0
    average_mapping_score: float = 0.0
    average_mapping_confidence: float = 0.0
    average_recommendation_priority_score: float = 0.0
    average_recommendation_confidence: float = 0.0
    evidence_supported_recommendation_rate: float = 0.0
    rag_supported_recommendation_rate: float = 0.0
    missing_recommendation_calibration_count: int = 0
    recommendation_uncertainty_mean: float = 0.0


# ---------------------------------------------------------------------------
# Required calibration decisions for recommendation ranking
# ---------------------------------------------------------------------------

REQUIRED_RECOMMENDATION_DECISIONS: list[str] = [
    "recommendation.priority_score_weights",
    "recommendation.production_threshold",
    "recommendation.confidence_threshold",
    "recommendation.uncertainty_penalty",
    "recommendation.minimum_mapping_confidence",
    "recommendation.minimum_evidence_support",
]

# ---------------------------------------------------------------------------
# Business impact bridge: new GapType -> old TechnicalGap -> business impact
# ---------------------------------------------------------------------------

_BUSINESS_IMPACT_MAP: dict[str, float] = {
    "compute_acceleration_gap": 0.75,
    "inference_performance_gap": 0.80,
    "training_scalability_gap": 0.65,
    "mlops_deployment_gap": 0.70,
    "data_pipeline_gap": 0.60,
    "model_optimization_gap": 0.65,
    "computer_vision_gap": 0.60,
    "genai_llm_gap": 0.70,
    "cybersecurity_ai_gap": 0.70,
    "nvidia_ecosystem_fit_gap": 0.50,
    "evidence_coverage_gap": 0.40,
    "technical_depth_gap": 0.40,
}

_NEXT_BEST_ACTION_MAP: dict[str, str] = {
    "approach_now": "Engage startup to discuss NVIDIA technology adoption and schedule technical workshop.",
    "validate_manually": "Manually validate gap evidence before proceeding with NVIDIA recommendation.",
    "monitor": "Monitor startup for signals that strengthen the case for this NVIDIA technology.",
    "not_recommended": "No action recommended — insufficient mapping confidence or evidence support.",
}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _lookup_calibration_group(
    decision_ids: list[str],
    inventory: list[DecisionCalibrationRecord] | None = None,
) -> tuple[dict[str, Any] | None, bool, list[str]]:
    if inventory is None:
        inventory = get_project_decision_inventory()
    values: dict[str, Any] = {}
    blockers: list[str] = []
    for decision_id in decision_ids:
        found = False
        for rec in inventory:
            if rec.decision_id == decision_id:
                found = True
                validation = validate_decision_for_production(rec)
                if not validation.passed:
                    blockers.append(f"Decision '{decision_id}' blocked for production: {'; '.join(validation.reasons)}")
                elif rec.calibration_status.value in ("uncalibrated", "blocked"):
                    blockers.append(f"Decision '{decision_id}' is {rec.calibration_status.value}")
                else:
                    values[decision_id] = rec.current_value
                break
        if not found:
            blockers.append(f"Decision '{decision_id}' not found in registry")
    if blockers:
        return None, False, blockers
    return values, True, []


def _lookup_weight_dict(
    decision_id: str,
    values: dict[str, Any],
) -> dict[str, float] | None:
    v = values.get(decision_id)
    if isinstance(v, dict):
        result: dict[str, float] = {}
        for k, val in v.items():
            if isinstance(val, (int, float)):
                result[k] = float(val)
        return result
    return None


def _lookup_float(
    decision_id: str,
    values: dict[str, Any],
) -> float | None:
    v = values.get(decision_id)
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _compute_weighted_score(
    features: dict[str, float],
    weights: dict[str, float],
) -> float:
    weight_sum = sum(weights.values())
    if weight_sum == 0.0:
        return 0.0
    raw = sum(weights.get(k, 0.0) * v for k, v in features.items() if k in weights)
    raw /= weight_sum
    return max(0.0, min(1.0, raw))


def _invalid_calibration_blockers(
    weights: dict[str, float] | None,
    values: dict[str, float | None],
) -> list[str]:
    blockers: list[str] = []
    if weights is None:
        blockers.append("Decision 'recommendation.priority_score_weights' current_value is not a dict.")
    elif not weights:
        blockers.append("Decision 'recommendation.priority_score_weights' current_value is empty.")
    elif sum(weights.values()) <= 0.0:
        blockers.append("Decision 'recommendation.priority_score_weights' weight sum is zero.")

    for decision_id, value in values.items():
        if value is None:
            blockers.append(f"Decision '{decision_id}' current_value is not numeric.")
    return blockers


def _get_business_impact(gap_type: str) -> float:
    return _BUSINESS_IMPACT_MAP.get(gap_type, 0.5)


def _get_implementation_complexity(tech_name: str) -> float:
    complexity = _COMPLEXITY_MAP.get(tech_name)
    if complexity is None:
        return 0.5
    value_map: dict[ImplementationComplexity, float] = {
        ImplementationComplexity.LOW: 0.0,
        ImplementationComplexity.MEDIUM: 0.5,
        ImplementationComplexity.HIGH: 1.0,
    }
    return value_map.get(complexity, 0.5)


def _build_next_best_action(
    production_allowed: bool,
    mapping_score: float,
    mapping_confidence: float,
    ev_support: bool,
    rag_support: bool,
) -> str:
    if not production_allowed:
        return _NEXT_BEST_ACTION_MAP["not_recommended"]
    if mapping_score < 0.5 or mapping_confidence < 0.5:
        return _NEXT_BEST_ACTION_MAP["validate_manually"]
    if not ev_support and not rag_support:
        return _NEXT_BEST_ACTION_MAP["monitor"]
    return _NEXT_BEST_ACTION_MAP["approach_now"]


def _determine_recommendation_action(
    production_allowed: bool,
    mapping_score: float,
    mapping_confidence: float,
    ev_support: bool,
    rag_support: bool,
) -> str:
    if not production_allowed:
        return "not_recommended"
    if mapping_score >= 0.7 and mapping_confidence >= 0.6 and (ev_support or rag_support):
        return "approach_now"
    if mapping_score >= 0.4 and mapping_confidence >= 0.4:
        return "validate_manually"
    if ev_support or rag_support:
        return "monitor"
    return "not_recommended"


# ---------------------------------------------------------------------------
# Main ranking function
# ---------------------------------------------------------------------------


def rank_recommendations_from_mappings(
    run_id: str,
    nvidia_technology_mappings: list[dict[str, Any]],
    mapping_status: str,
    inventory: list[DecisionCalibrationRecord] | None = None,
) -> dict[str, Any]:
    if inventory is None:
        inventory = get_project_decision_inventory()

    # ── 1. No mappings → blocked ──────────────────────────────────────
    if not nvidia_technology_mappings:
        return {
            "run_id": run_id,
            "nvidia_recommendations": [],
            "nvidia_recommendation_metrics": NvidiaRecommendationMetrics(
                mapping_count=0,
                recommendation_count=0,
                blocked_recommendation_count=1,
                missing_recommendation_calibration_count=len(REQUIRED_RECOMMENDATION_DECISIONS),
            ).model_dump(mode="json"),
            "ranking_status": RecommendationRankingStatus.BLOCKED_NO_NVIDIA_MAPPINGS.value,
            "production_allowed": False,
            "blockers": ["No NVIDIA technology mappings available. Run build_nvidia_technology_mappings first."],
        }

    # ── 2. Mapping blocked/uncalibrated → blocked_uncalibrated_mapping ─
    if mapping_status in (
        "blocked_uncalibrated_mapping",
        "failed",
        "needs_more_evidence",
    ):
        return {
            "run_id": run_id,
            "nvidia_recommendations": [],
            "nvidia_recommendation_metrics": NvidiaRecommendationMetrics(
                mapping_count=len(nvidia_technology_mappings),
                recommendation_count=0,
                blocked_recommendation_count=len(nvidia_technology_mappings),
            ).model_dump(mode="json"),
            "ranking_status": RecommendationRankingStatus.BLOCKED_UNCALIBRATED_MAPPING.value,
            "production_allowed": False,
            "blockers": [f"Mapping status is '{mapping_status}' — cannot generate recommendations."],
        }

    # ── 3. Validate recommendation calibration decisions ──────────────
    cal_values, cal_ok, cal_blockers = _lookup_calibration_group(REQUIRED_RECOMMENDATION_DECISIONS, inventory=inventory)

    if not cal_ok:
        metrics = NvidiaRecommendationMetrics(
            mapping_count=len(nvidia_technology_mappings),
            recommendation_count=0,
            blocked_recommendation_count=len(nvidia_technology_mappings),
            missing_recommendation_calibration_count=len(cal_blockers),
        )
        return {
            "run_id": run_id,
            "nvidia_recommendations": [],
            "nvidia_recommendation_metrics": metrics.model_dump(mode="json"),
            "ranking_status": RecommendationRankingStatus.BLOCKED_UNCALIBRATED_RECOMMENDATION.value,
            "production_allowed": False,
            "blockers": cal_blockers,
        }

    assert cal_values is not None

    # ── 4. Extract calibrated parameters ──────────────────────────────
    ps_weights = _lookup_weight_dict("recommendation.priority_score_weights", cal_values)
    production_threshold = _lookup_float("recommendation.production_threshold", cal_values)
    confidence_threshold = _lookup_float("recommendation.confidence_threshold", cal_values)
    uncertainty_penalty = _lookup_float("recommendation.uncertainty_penalty", cal_values)
    min_mapping_confidence = _lookup_float("recommendation.minimum_mapping_confidence", cal_values)
    min_evidence_support = _lookup_float("recommendation.minimum_evidence_support", cal_values)

    invalid_blockers = _invalid_calibration_blockers(
        ps_weights,
        {
            "recommendation.production_threshold": production_threshold,
            "recommendation.confidence_threshold": confidence_threshold,
            "recommendation.uncertainty_penalty": uncertainty_penalty,
            "recommendation.minimum_mapping_confidence": min_mapping_confidence,
            "recommendation.minimum_evidence_support": min_evidence_support,
        },
    )
    if invalid_blockers:
        metrics = NvidiaRecommendationMetrics(
            mapping_count=len(nvidia_technology_mappings),
            recommendation_count=0,
            blocked_recommendation_count=len(nvidia_technology_mappings),
            missing_recommendation_calibration_count=len(invalid_blockers),
        )
        return {
            "run_id": run_id,
            "nvidia_recommendations": [],
            "nvidia_recommendation_metrics": metrics.model_dump(mode="json"),
            "ranking_status": RecommendationRankingStatus.BLOCKED_UNCALIBRATED_RECOMMENDATION.value,
            "production_allowed": False,
            "blockers": invalid_blockers,
        }

    assert ps_weights is not None
    assert production_threshold is not None
    assert confidence_threshold is not None
    assert uncertainty_penalty is not None
    assert min_mapping_confidence is not None
    assert min_evidence_support is not None

    # ── 5. Build recommendations from mappings ────────────────────────
    recommendations: list[NvidiaRecommendationRecord] = []
    for i, mapping_dict in enumerate(nvidia_technology_mappings):
        mapping = parse_mapping_dict(mapping_dict)
        gap_type = mapping.get("gap_type", "unknown")
        nvidia_technology = mapping.get("nvidia_technology", "unknown")

        mapping_score = float(mapping.get("mapping_score", 0.0))
        mapping_confidence_val = float(mapping.get("mapping_confidence", 0.0))
        uncertainty = float(mapping.get("uncertainty", 1.0))
        rag_ids = list(mapping.get("supporting_rag_context_ids", []))
        ev_ids = list(mapping.get("supporting_evidence_ids", []))
        mapping_prod_allowed = bool(mapping.get("production_allowed", False))
        mapping_blockers = list(mapping.get("blockers", []))
        mapping_cal_ids = list(mapping.get("calibration_decision_ids", []))
        raw_gap_id: Any = mapping.get("gap_id", mapping.get("mapping_id", f"map-{run_id}-{i}"))
        gap_id = str(raw_gap_id)

        evidence_support_score = min(1.0, len(ev_ids) / 5.0)
        rag_support_score = min(1.0, len(rag_ids) / 5.0)
        combined_support_score = min(1.0, evidence_support_score + rag_support_score)
        ev_support = len(ev_ids) > 0
        rag_support = len(rag_ids) > 0

        biz_impact = _get_business_impact(gap_type)
        complexity = _get_implementation_complexity(nvidia_technology)

        # ── Compute recommendation_priority_score ────────────────────
        if ps_weights:
            features = {
                "mapping_score": mapping_score,
                "mapping_confidence": mapping_confidence_val,
                "gap_severity_score": float(mapping.get("features", {}).get("gap_severity_score", 0.5)),
                "gap_confidence_score": float(mapping.get("features", {}).get("gap_confidence_score", 0.5)),
                "evidence_support": evidence_support_score,
                "rag_support": rag_support_score,
                "business_impact": biz_impact,
                "implementation_complexity_inverse": 1.0 - complexity,
            }
            raw_priority = _compute_weighted_score(features, ps_weights)
            priority_score = max(0.0, min(1.0, raw_priority - uncertainty * uncertainty_penalty))
        else:
            priority_score = 0.0

        # ── Determine production_allowed for this recommendation ─────
        rec_production_allowed = mapping_prod_allowed
        rec_blockers = list(mapping_blockers)

        if mapping_score < production_threshold:
            rec_production_allowed = False
            rec_blockers.append(
                f"Mapping score ({round(mapping_score, 4)}) below production threshold ({production_threshold})."
            )

        if mapping_confidence_val < min_mapping_confidence:
            rec_production_allowed = False
            rec_blockers.append(
                f"Mapping confidence ({round(mapping_confidence_val, 4)}) below minimum ({min_mapping_confidence})."
            )

        if mapping_confidence_val < confidence_threshold:
            rec_blockers.append(
                f"Mapping confidence ({round(mapping_confidence_val, 4)}) below confidence threshold ({confidence_threshold})."
            )

        if combined_support_score < min_evidence_support:
            rec_production_allowed = False
            rec_blockers.append(
                f"Evidence/RAG support ({round(combined_support_score, 4)}) below minimum ({min_evidence_support})."
            )
        if not ev_support:
            rec_production_allowed = False
            rec_blockers.append("Missing startup evidence support for this recommendation.")
        if not rag_support:
            rec_production_allowed = False
            rec_blockers.append("Missing NVIDIA RAG context support for this recommendation.")

        # confidence = mapping_confidence * (1 - uncertainty_penalty * uncertainty)
        confidence_val = max(
            0.0,
            mapping_confidence_val * (1.0 - uncertainty_penalty * uncertainty),
        )

        recommendation_action = _determine_recommendation_action(
            production_allowed=rec_production_allowed,
            mapping_score=mapping_score,
            mapping_confidence=mapping_confidence_val,
            ev_support=ev_support,
            rag_support=rag_support,
        )
        next_action = _build_next_best_action(
            production_allowed=rec_production_allowed,
            mapping_score=mapping_score,
            mapping_confidence=mapping_confidence_val,
            ev_support=ev_support,
            rag_support=rag_support,
        )

        reason_parts: list[str] = [
            f"Gap '{gap_type}' mapped to '{nvidia_technology}'",
            f"mapping_score={round(mapping_score, 4)}",
            f"mapping_confidence={round(mapping_confidence_val, 4)}",
        ]
        if rec_production_allowed:
            reason_parts.append("Production allowed.")
        else:
            reason_parts.append("Production blocked.")

        expected_utility = max(0.0, min(1.0, priority_score * confidence_val * (1.0 - uncertainty)))
        why_not = list(dict.fromkeys(rec_blockers))

        recommendations.append(
            NvidiaRecommendationRecord(
                recommendation_id=f"rec-{run_id}-{i}",
                gap_id=gap_id,
                gap_type=gap_type,
                nvidia_technology=nvidia_technology,
                reason="; ".join(reason_parts),
                mapping_score=mapping_score,
                mapping_confidence=mapping_confidence_val,
                recommendation_priority_score=round(priority_score, 4),
                confidence=round(confidence_val, 4),
                uncertainty=round(uncertainty, 4),
                business_impact=round(biz_impact, 4),
                implementation_complexity=round(complexity, 4),
                supporting_rag_context_ids=rag_ids,
                supporting_evidence_ids=ev_ids,
                calibration_decision_ids=REQUIRED_RECOMMENDATION_DECISIONS + mapping_cal_ids,
                production_allowed=rec_production_allowed,
                blockers=rec_blockers,
                recommendation_action=recommendation_action,
                next_best_action=next_action,
                evidence_support_score=round(evidence_support_score, 4),
                rag_support_score=round(rag_support_score, 4),
                expected_utility=round(expected_utility, 4),
                why_not=why_not,
            )
        )

    # ── 6. Sort by priority_score descending ──────────────────────────
    recommendations.sort(key=lambda r: r.recommendation_priority_score, reverse=True)

    # ── 7. Compute metrics ───────────────────────────────────────────
    metrics = compute_recommendation_metrics(recommendations)

    # ── 8. Determine overall ranking_status ──────────────────────────
    total_recs = len(recommendations)
    prod_recs = sum(1 for r in recommendations if r.production_allowed)

    if prod_recs > 0:
        ranking_status_val = RecommendationRankingStatus.PASSED.value
    elif total_recs > 0:
        ranking_status_val = RecommendationRankingStatus.NEEDS_REVIEW.value
    else:
        ranking_status_val = RecommendationRankingStatus.FAILED.value

    return {
        "run_id": run_id,
        "nvidia_recommendations": [r.model_dump(mode="json") for r in recommendations],
        "nvidia_recommendation_metrics": metrics.model_dump(mode="json"),
        "ranking_status": ranking_status_val,
        "production_allowed": prod_recs > 0,
        "blockers": [],
    }


def parse_mapping_dict(mapping_dict: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw mapping dict (may have nested 'features' or flat fields)."""
    result = dict(mapping_dict)
    features = result.get("features") or {}
    if isinstance(features, dict):
        result["features"] = features
    else:
        result["features"] = {}
    return result


def compute_recommendation_metrics(
    recommendations: list[NvidiaRecommendationRecord],
) -> NvidiaRecommendationMetrics:
    total = len(recommendations)
    prod_allowed = sum(1 for r in recommendations if r.production_allowed)
    blocked = sum(
        1
        for r in recommendations
        if not r.production_allowed
        and any("calibrat" in b.lower() or "uncalibrat" in b.lower() or "not found" in b.lower() for b in r.blockers)
    )
    needs_review = total - prod_allowed - blocked

    mapping_scores = [r.mapping_score for r in recommendations]
    mapping_confs = [r.mapping_confidence for r in recommendations]
    priority_scores = [r.recommendation_priority_score for r in recommendations]
    conf_scores = [r.confidence for r in recommendations]
    uncertainties = [r.uncertainty for r in recommendations]

    ev_supported = sum(1 for r in recommendations if len(r.supporting_evidence_ids) > 0)
    rag_supported = sum(1 for r in recommendations if len(r.supporting_rag_context_ids) > 0)

    return NvidiaRecommendationMetrics(
        mapping_count=total,
        production_allowed_mapping_count=prod_allowed,
        recommendation_count=total,
        production_allowed_recommendation_count=prod_allowed,
        blocked_recommendation_count=blocked,
        needs_review_recommendation_count=needs_review,
        average_mapping_score=_mean(mapping_scores),
        average_mapping_confidence=_mean(mapping_confs),
        average_recommendation_priority_score=_mean(priority_scores),
        average_recommendation_confidence=_mean(conf_scores),
        evidence_supported_recommendation_rate=ev_supported / max(1, total),
        rag_supported_recommendation_rate=rag_supported / max(1, total),
        missing_recommendation_calibration_count=len(REQUIRED_RECOMMENDATION_DECISIONS),
        recommendation_uncertainty_mean=_mean(uncertainties),
    )

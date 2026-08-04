"""Deterministic next-action enrichment for recommendation product spikes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.extraction.schemas import TechnicalGap
from src.recommendation.schemas import PerGapRecommendation, RecommendedNextAction


class NextActionEnrichmentConfig(BaseModel):
    enabled: bool = True
    require_evidence_reference: bool = True
    default_owner: str = "NVIDIA technical solution architect"
    default_timeframe: str = "10 business days"


class EnrichedNextAction(BaseModel):
    owner: str
    technology: str
    metric: str
    threshold: str
    timeframe: str
    evidence_requirement: str
    success_decision: str
    next_step: str
    trace: dict[str, str] = Field(default_factory=dict)


_GAP_ACTIONS: dict[TechnicalGap, dict[str, str]] = {
    TechnicalGap.HIGH_INFERENCE_COST: {
        "metric": "cost per 1k inference requests and GPU utilization",
        "threshold": ">=25% cost reduction with equal or better p95 latency",
        "evidence_requirement": "current inference bill, request volume, model family, and deployment target",
        "success_decision": "advance to NVIDIA inference optimization workshop",
    },
    TechnicalGap.HIGH_LATENCY: {
        "metric": "p95 latency and throughput under representative load",
        "threshold": ">=20% p95 latency reduction or >=15% throughput gain",
        "evidence_requirement": "baseline p50/p95 latency, model artifact, and traffic shape",
        "success_decision": "run a Triton deployment plan with startup engineering",
    },
    TechnicalGap.EXTERNAL_API_DEPENDENCY: {
        "metric": "self-hosted inference cost, data-control fit, and p95 latency",
        "threshold": "validated data-control path and >=20% cost or latency improvement",
        "evidence_requirement": "external API usage, privacy constraints, and model compatibility",
        "success_decision": "scope NVIDIA NIM proof of value",
    },
    TechnicalGap.AGENT_GOVERNANCE_GAP: {
        "metric": "policy violation catch rate and false-positive rate",
        "threshold": ">=90% critical violation catch rate with acceptable false positives",
        "evidence_requirement": "agent workflows, tool policies, and failure examples",
        "success_decision": "prototype NeMo Guardrails policy pack",
    },
    TechnicalGap.SLOW_DATA_PIPELINE: {
        "metric": "ETL throughput and end-to-end job duration",
        "threshold": ">=3x throughput improvement on representative data",
        "evidence_requirement": "current pipeline profile and dataset size distribution",
        "success_decision": "scope RAPIDS acceleration sprint",
    },
}


def enrich_next_action(
    recommendation: PerGapRecommendation,
    config: NextActionEnrichmentConfig | None = None,
) -> EnrichedNextAction | None:
    """Return a structured next action for an existing recommendation.

    This helper is opt-in and does not mutate the original recommendation.
    """
    cfg = config or NextActionEnrichmentConfig()
    if not cfg.enabled or recommendation.action != RecommendedNextAction.APPROACH_NOW:
        return None

    technology = _select_technology(recommendation)
    template = _GAP_ACTIONS.get(recommendation.diagnosed_gap, _default_template())
    evidence_requirement = template["evidence_requirement"]
    if cfg.require_evidence_reference and recommendation.evidence_used:
        evidence_requirement = (
            f"{evidence_requirement}; cite {len(recommendation.evidence_used)} supporting evidence item(s)"
        )

    next_step = (
        f"{cfg.default_owner} to run {technology} validation: measure {template['metric']} "
        f"against threshold {template['threshold']} within {cfg.default_timeframe}."
    )
    return EnrichedNextAction(
        owner=cfg.default_owner,
        technology=technology,
        metric=template["metric"],
        threshold=template["threshold"],
        timeframe=cfg.default_timeframe,
        evidence_requirement=evidence_requirement,
        success_decision=template["success_decision"],
        next_step=next_step,
        trace={
            "diagnosed_gap": recommendation.diagnosed_gap.value,
            "action": recommendation.action.value,
            "priority": recommendation.priority.value,
            "confidence": recommendation.confidence.value,
        },
    )


def score_next_action(action_text: str, enriched: EnrichedNextAction | None = None) -> float:
    """Score actionability using explicit fields evaluators expect."""
    text = action_text.lower()
    checks = {
        "owner": bool(enriched and enriched.owner) or "owner" in text or "architect" in text,
        "technology": bool(enriched and enriched.technology) or "nvidia" in text,
        "metric": bool(enriched and enriched.metric) or "metric" in text or "latency" in text or "cost" in text,
        "threshold": bool(enriched and enriched.threshold) or "%" in text or "threshold" in text,
        "timeframe": bool(enriched and enriched.timeframe) or "days" in text or "weeks" in text,
        "evidence": bool(enriched and enriched.evidence_requirement) or "evidence" in text or "baseline" in text,
        "decision": bool(enriched and enriched.success_decision) or "decision" in text or "advance" in text,
    }
    return round(sum(1 for value in checks.values() if value) / len(checks), 4)


def _select_technology(recommendation: PerGapRecommendation) -> str:
    if recommendation.recommended_nvidia_technologies:
        return recommendation.recommended_nvidia_technologies[0]
    if recommendation.suggested_experiment:
        return recommendation.suggested_experiment.nvidia_technology
    return "NVIDIA technical stack"


def _default_template() -> dict[str, str]:
    return {
        "metric": "technical success metric agreed with startup engineering",
        "threshold": "measurable improvement over baseline without reducing evidence confidence",
        "evidence_requirement": "baseline architecture, current bottleneck, and RAG-supported NVIDIA fit",
        "success_decision": "advance only if evidence-backed metric improves over baseline",
    }

from __future__ import annotations

from scripts import run_next_action_enrichment_product_spike
from src.extraction.schemas import ConfidenceLevel, ImplementationComplexity, RecommendationPriority, TechnicalGap
from src.recommendation.next_action_enrichment import (
    NextActionEnrichmentConfig,
    enrich_next_action,
    score_next_action,
)
from src.recommendation.schemas import PerGapRecommendation, RecommendedNextAction


def _recommendation(
    gap: TechnicalGap = TechnicalGap.HIGH_LATENCY,
    technology: str = "Triton Inference Server",
) -> PerGapRecommendation:
    return PerGapRecommendation(
        diagnosed_gap=gap,
        detected=True,
        recommended_nvidia_technologies=[technology],
        priority=RecommendationPriority.HIGH,
        implementation_complexity=ImplementationComplexity.MEDIUM,
        action=RecommendedNextAction.APPROACH_NOW,
        next_action_for_nvidia_team="Contact startup to discuss adoption.",
        confidence=ConfidenceLevel.HIGH,
    )


def test_enrich_next_action_adds_measurable_fields() -> None:
    enriched = enrich_next_action(_recommendation(), NextActionEnrichmentConfig())

    assert enriched is not None
    assert enriched.technology == "Triton Inference Server"
    assert "p95 latency" in enriched.metric
    assert "%" in enriched.threshold
    assert enriched.owner == "NVIDIA technical solution architect"
    assert enriched.trace["diagnosed_gap"] == "high_latency"


def test_enrich_next_action_is_opt_in_for_approach_now_only() -> None:
    recommendation = _recommendation()
    recommendation.action = RecommendedNextAction.MONITOR

    assert enrich_next_action(recommendation, NextActionEnrichmentConfig()) is None
    assert enrich_next_action(_recommendation(), NextActionEnrichmentConfig(enabled=False)) is None


def test_score_next_action_improves_with_enrichment() -> None:
    recommendation = _recommendation()
    enriched = enrich_next_action(recommendation)

    baseline = score_next_action(recommendation.next_action_for_nvidia_team)
    candidate = score_next_action(recommendation.next_action_for_nvidia_team, enriched)

    assert candidate > baseline
    assert candidate == 1.0


def test_next_action_enrichment_product_spike_report_promotes_product_spike() -> None:
    report = run_next_action_enrichment_product_spike.build_report(min_delta=0.35)

    assert report["decision"] == "PROMOTE_TO_PRODUCT_SPIKE"
    assert report["quality_delta"] >= 0.35
    assert report["regression_count"] == 0
    assert report["case_count"] == 3

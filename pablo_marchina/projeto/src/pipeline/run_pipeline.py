"""Legacy offline pipeline shim.

Product runtime MUST use ``POST /workflows/product-runs`` and the LangGraph
orchestration path.  This module is retained only for historical/offline tests
and raises in ``APP_MODE=product`` so it cannot become a second runtime path.
"""

from __future__ import annotations

import logging
import os

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from src.classification.ai_native_classifier import (
    ClassificationResult,
    classify_ai_native,
)
from src.diagnosis import (
    GapDiagnosisResult,
    build_technology_candidates,
    diagnose_gaps,
)
from src.extraction.extractor import extract_profile
from src.extraction.schemas import ConfidenceLevel, Evidence, StartupProfile
from src.sourcing.evidence_manager import EvidenceManager
from src.rag.embeddings import EmbeddingProvider
from src.rag.rag_pipeline import run_rag_pipeline
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import PackingConfig, RagPipelineOutput, RerankingConfig
from src.rag.vector_store import VectorStore
from src.recommendation import RecommendationResult, build_recommendations
from src.validation.evidence_validator import (
    ValidatedEvidence,
    validate_evidence_batch,
)

class DefensibilityScoreResult(BaseModel):
    total_score: float
    confidence: ConfidenceLevel
    evidence_used: list[ValidatedEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class InceptionFitScoreResult(BaseModel):
    total_score: float
    confidence: ConfidenceLevel
    evidence_used: list[ValidatedEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class ScoreComponent(BaseModel):
    adjusted_score: float
    evidence_count: int = 0


class ProductionReadinessResult(BaseModel):
    production_readiness_score: float
    confidence: ConfidenceLevel
    score_breakdown: dict[str, ScoreComponent] = Field(default_factory=dict)
    evidence_used: list[ValidatedEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class CompositeResult(BaseModel):
    startup_id: str
    composite_score: float
    confidence: ConfidenceLevel
    reasoning: str
    missing_components: list[str] = Field(default_factory=list)


class RankedStartup(BaseModel):
    startup_id: str
    startup_name: str
    sector: str
    composite_score: float
    confidence: ConfidenceLevel
    motion: str


def compute_defensibility_score(
    profile: StartupProfile,
    classification: ClassificationResult,
    evidence: list[ValidatedEvidence],
) -> DefensibilityScoreResult:
    evidence_score = min(40.0, len(evidence) * 8.0)
    ai_signal_score = min(30.0, len(profile.ai_signals) * 5.0)
    confidence_score = float(profile.confidence_score or 0.0) * 30.0
    total = round(min(100.0, evidence_score + ai_signal_score + confidence_score), 2)
    return DefensibilityScoreResult(
        total_score=total,
        confidence=_confidence_from_score(total, classification.confidence),
        evidence_used=list(evidence),
        missing_evidence=[] if evidence else ["validated_public_evidence"],
    )


def compute_inception_fit_score(
    profile: StartupProfile,
    classification: ClassificationResult,
    defensibility_score: float,
    evidence: list[ValidatedEvidence],
) -> InceptionFitScoreResult:
    tech_score = min(35.0, len(profile.tech_stack_signals) * 7.0)
    ai_score = min(35.0, len(profile.ai_signals) * 5.0)
    total = round(min(100.0, tech_score + ai_score + defensibility_score * 0.3), 2)
    return InceptionFitScoreResult(
        total_score=total,
        confidence=_confidence_from_score(total, classification.confidence),
        evidence_used=list(evidence),
        missing_evidence=[] if profile.tech_stack_signals else ["technical_stack_evidence"],
    )


def compute_production_readiness(
    profile: StartupProfile,
    classification: ClassificationResult,
    evidence: list[ValidatedEvidence],
) -> ProductionReadinessResult:
    production_terms = ("api", "deploy", "production", "security", "monitor", "cloud", "latency", "scale")
    text = f"{profile.description} {profile.product_summary} {' '.join(profile.tech_stack_signals)}".lower()
    production_score = min(50.0, sum(1 for term in production_terms if term in text) * 8.0)
    evidence_score = min(30.0, len(evidence) * 6.0)
    confidence_score = float(profile.confidence_score or 0.0) * 20.0
    total = round(min(100.0, production_score + evidence_score + confidence_score), 2)
    return ProductionReadinessResult(
        production_readiness_score=total,
        confidence=_confidence_from_score(total, classification.confidence),
        score_breakdown={
            "scale_and_inference": ScoreComponent(
                adjusted_score=round(production_score + evidence_score * 0.5, 2),
                evidence_count=len(evidence),
            ),
            "operations": ScoreComponent(
                adjusted_score=round(confidence_score + evidence_score * 0.5, 2),
                evidence_count=len(evidence),
            ),
        },
        evidence_used=list(evidence),
        missing_evidence=[] if production_score > 0 else ["production_readiness_evidence"],
    )


def compute_composite_score(
    *,
    startup_id: str,
    defensibility: DefensibilityScoreResult,
    inception_fit: InceptionFitScoreResult,
    production_readiness: ProductionReadinessResult,
    classification_result: ClassificationResult,
) -> CompositeResult:
    total = round(
        defensibility.total_score * 0.35
        + inception_fit.total_score * 0.35
        + production_readiness.production_readiness_score * 0.30,
        2,
    )
    return CompositeResult(
        startup_id=startup_id,
        composite_score=total,
        confidence=_confidence_from_score(total, classification_result.confidence),
        reasoning=(
            f"defensibility={defensibility.total_score}; "
            f"inception_fit={inception_fit.total_score}; "
            f"production_readiness={production_readiness.production_readiness_score}"
        ),
        missing_components=[
            component
            for component, missing in {
                "defensibility": defensibility.missing_evidence,
                "inception_fit": inception_fit.missing_evidence,
                "production_readiness": production_readiness.missing_evidence,
            }.items()
            if missing
        ],
    )


def build_ranked_list(
    scores: list[CompositeResult],
    names: dict[str, tuple[str, str]],
    classifications: dict[str, ClassificationResult],
) -> list[RankedStartup]:
    ranked: list[RankedStartup] = []
    for score in scores:
        startup_name, sector = names.get(score.startup_id, (score.startup_id, ""))
        classification = classifications.get(score.startup_id)
        motion = _motion_from_score(score.composite_score, score.confidence)
        if classification and classification.classification.value == "non_ai":
            motion = "not_recommended"
        ranked.append(
            RankedStartup(
                startup_id=score.startup_id,
                startup_name=startup_name,
                sector=sector,
                composite_score=score.composite_score,
                confidence=score.confidence,
                motion=motion,
            )
        )
    return sorted(ranked, key=lambda item: item.composite_score, reverse=True)


def _confidence_from_score(score: float, fallback: ConfidenceLevel) -> ConfidenceLevel:
    if score >= 70:
        return ConfidenceLevel.HIGH
    if score >= 40:
        return ConfidenceLevel.MEDIUM
    return fallback if fallback == ConfidenceLevel.LOW else ConfidenceLevel.LOW


def _motion_from_score(score: float, confidence: ConfidenceLevel) -> str:
    if confidence == ConfidenceLevel.LOW:
        return "lack_evidence_more_research"
    if score >= 75:
        return "immediate_outreach"
    if score >= 55:
        return "high_priority_outreach"
    if score >= 35:
        return "monitor_and_nurture"
    return "not_recommended"


class PipelineResult(BaseModel):
    startup_name: str
    startup_profile: StartupProfile
    ai_native_classification: ClassificationResult
    validated_evidence: list[ValidatedEvidence]
    defensibility_score: DefensibilityScoreResult
    inception_fit_score: InceptionFitScoreResult
    production_readiness_score: ProductionReadinessResult
    composite_score: CompositeResult
    ranked: list[RankedStartup]
    final_priority_score: float
    recommended_motion: str
    gap_diagnosis: GapDiagnosisResult | None = None
    recommendation: RecommendationResult | None = None
    reasoning: str
    evidence_used: list[ValidatedEvidence] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    rag_output: RagPipelineOutput | None = None


def _ensure_not_product_runtime() -> None:
    if os.getenv("APP_MODE", "").casefold() == "product":
        raise RuntimeError(
            "src.pipeline.run_pipeline is legacy/offline only. "
            "Use WorkflowOrchestrationService / POST /workflows/product-runs."
        )


def run_full_pipeline(
    startup_name: str,
    raw_text: str | None = None,
    url: str = "https://example.com",
    profile: StartupProfile | None = None,
    evidence_list: list[Evidence] | None = None,
    chunk_index: ChunkIndex | None = None,
    embedding_model: EmbeddingProvider | None = None,
    vector_store: VectorStore | None = None,
    reranking_config: RerankingConfig | None = None,
    packing_config: PackingConfig | None = None,
) -> PipelineResult:
    """Execute the legacy offline Startup AI Radar pipeline.

    Pipeline order:
      1. Extraction (if raw_text is provided)
      2. AI-native classification
      3. Evidence validation
      4. AI-Native Defensibility Score
      5. NVIDIA Inception Fit Score
      6. Production AI Readiness
      7. Composite Score + Confidence-aware Ranking
      8. Gap Diagnosis
      9. NVIDIA Technology Mapping
     10. Product RAG (hybrid retrieval, reranking, context packing)
     11. Legacy recommendation formatter (blocked in APP_MODE=product)

    Parameters
    ----------
    startup_name:
        Name of the startup (used as a hint for extraction and as ID).
    raw_text:
        Raw scraped text to extract a profile from. If None, *profile* must
        be provided.
    url:
        Source URL for extraction metadata.
    profile:
        Pre-extracted StartupProfile. If None, *raw_text* must be provided.
    evidence_list:
        Raw Evidence objects to validate. If None, extracted from
        *profile* sources.
    chunk_index:
        Lexical index for RAG. If None, tries ``build_default_index()``.
    embedding_model:
        Embedding provider for semantic RAG. If None, lexical fallback.
    vector_store:
        Vector store for semantic RAG. Must be QdrantStore in production.
    reranking_config:
        Reranking weights. If None, reranking is skipped.
    packing_config:
        Packing limits. If None, packing is skipped.

    Returns
    -------
    PipelineResult
        All intermediate and final outputs including gaps, recommendations,
        and RAG output.
    """
    _ensure_not_product_runtime()

    # Step 1: Extraction
    if profile is None:
        if raw_text is None:
            raise ValueError("Either raw_text or profile must be provided.")
        profile = extract_profile(
            clean_text=raw_text,
            url=url,
            startup_name_hint=startup_name,
        )

    # Step 2: AI-native classification
    classification = classify_ai_native(profile)

    # Step 3: Evidence validation
    raw_evidence = evidence_list if evidence_list is not None else profile.sources
    validated_evidence = validate_evidence_batch(raw_evidence)

    # Step 3.5: Evidence cross-validation
    evidence_mgr = EvidenceManager()
    for ev in validated_evidence:
        evidence_mgr.add_claim(ev.quote_or_evidence, str(ev.source_url), 0.7)
    cross_validation = evidence_mgr.cross_validate()
    if cross_validation.contradictions:
        logger.warning(
            "Cross-validation found %d contradictory pairs across %d claims",
            len(cross_validation.contradictions),
            cross_validation.total_claims,
        )

    # Step 4: AI-Native Defensibility Score
    defensibility = compute_defensibility_score(profile, classification, validated_evidence)

    # Step 5: NVIDIA Inception Fit Score
    inception_fit = compute_inception_fit_score(
        profile,
        classification,
        defensibility.total_score,
        validated_evidence,
    )

    # Step 6: Production AI Readiness
    production_readiness = compute_production_readiness(
        profile,
        classification,
        validated_evidence,
    )

    # Step 7: Composite Score + Ranking
    composite = compute_composite_score(
        startup_id=startup_name,
        defensibility=defensibility,
        inception_fit=inception_fit,
        production_readiness=production_readiness,
        classification_result=classification,
    )

    names = {startup_name: (profile.startup_name, profile.sector)}
    classifications = {startup_name: classification}
    ranked = build_ranked_list([composite], names, classifications)

    top = ranked[0] if ranked else None
    final_priority_score = top.composite_score if top else 0.0
    recommended_motion = top.motion if top else "lack_evidence_more_research"

    # Step 8: Gap Diagnosis
    gap_diag = diagnose_gaps(
        startup_name=startup_name,
        profile=profile,
        classification=classification,
        validated_evidence=validated_evidence,
        production_readiness=production_readiness,
        defensibility=defensibility,
        inception_fit=inception_fit,
    )

    # Step 9: NVIDIA Technology Mapping
    candidates = build_technology_candidates(gap_diag.diagnosed_gaps)
    gap_diagnosis = gap_diag.model_copy(update={"nvidia_technology_candidates": candidates})

    # Step 10: Product RAG (required for recommendations)
    rag_output = run_rag_pipeline(
        gap_diagnosis=gap_diagnosis,
        chunk_index=chunk_index,
        embedding_model=embedding_model,
        vector_store=vector_store,
        reranking_config=reranking_config,
        packing_config=packing_config,
    )

    # Step 11: Legacy recommendation formatter (requires RAG context)
    recommendation = build_recommendations(
        startup_name=startup_name,
        profile=profile,
        classification=classification,
        validated_evidence=validated_evidence,
        defensibility=defensibility,
        inception_fit=inception_fit,
        production_readiness=production_readiness,
        composite=composite,
        final_priority_score=final_priority_score,
        recommended_motion=recommended_motion,
        gap_diagnosis=gap_diagnosis,
        rag_context=rag_output,
    )

    # Aggregate evidence_used and missing_evidence
    all_missing: list[str] = list(defensibility.missing_evidence)
    all_missing.extend(inception_fit.missing_evidence)
    all_missing.extend(production_readiness.missing_evidence)
    all_missing.extend(gap_diagnosis.missing_evidence)
    all_missing.extend(recommendation.missing_evidence)

    all_evidence: list[ValidatedEvidence] = list(defensibility.evidence_used)
    all_evidence.extend(inception_fit.evidence_used)
    all_evidence.extend(production_readiness.evidence_used)
    all_evidence.extend(gap_diagnosis.evidence_used)
    all_evidence.extend(recommendation.evidence_used)

    def_total = defensibility.total_score
    def_conf = defensibility.confidence.value
    inc_total = inception_fit.total_score
    inc_conf = inception_fit.confidence.value
    pr_score = production_readiness.production_readiness_score
    pr_conf = production_readiness.confidence.value
    comp_score = composite.composite_score
    comp_conf = composite.confidence.value
    detected_gaps = len([g for g in gap_diagnosis.diagnosed_gaps if g.detected])
    rec_count = len(recommendation.recommendations)
    lines: list[str] = [
        f"Pipeline complete for {startup_name}",
        f"  Defensibility: {def_total}/100 ({def_conf})",
        f"  Inception Fit: {inc_total}/100 ({inc_conf})",
        f"  Production Readiness: {pr_score}/100 ({pr_conf})",
        f"  Composite: {comp_score}/100 ({comp_conf})",
        f"  Motion: {recommended_motion}",
        f"  Gaps detected: {detected_gaps}",
        f"  Recommendations: {rec_count}",
    ]
    if all_missing:
        lines.append(f"  Missing evidence items: {len(all_missing)}")

    return PipelineResult(
        startup_name=startup_name,
        startup_profile=profile,
        ai_native_classification=classification,
        validated_evidence=validated_evidence,
        defensibility_score=defensibility,
        inception_fit_score=inception_fit,
        production_readiness_score=production_readiness,
        composite_score=composite,
        ranked=ranked,
        final_priority_score=final_priority_score,
        recommended_motion=recommended_motion,
        gap_diagnosis=gap_diagnosis,
        recommendation=recommendation,
        reasoning="\n".join(lines),
        evidence_used=all_evidence,
        missing_evidence=all_missing,
        rag_output=rag_output,
    )

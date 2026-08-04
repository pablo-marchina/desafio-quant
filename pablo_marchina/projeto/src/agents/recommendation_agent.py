"""Legacy/offline recommendation helpers.

The product runtime uses the LangGraph nodes ``map_nvidia_technologies`` and
``rank_recommendations``.  These helpers are retained for offline compatibility
and are blocked when ``APP_MODE=product`` to preserve a single runtime path.
"""

from __future__ import annotations

from typing import Any
import os


def _ensure_not_product_runtime() -> None:
    if os.getenv("APP_MODE", "").casefold() == "product":
        raise RuntimeError(
            "src.agents.recommendation_agent is legacy/offline only. "
            "Use the LangGraph recommendation nodes in the single product workflow."
        )


def diagnose_gaps(
    startup_name: str,
    profile_raw: dict[str, Any] | None,
    validated_evidence_dicts: list[dict[str, Any]],
    classification_raw: dict[str, Any] | None,
    defensibility_raw: dict[str, Any] | None,
    inception_fit_raw: dict[str, Any] | None,
    production_readiness_raw: dict[str, Any] | None,
) -> tuple[list[str], dict[str, Any], list[str]]:
    _ensure_not_product_runtime()

    from src.classification.ai_native_classifier import ClassificationResult
    from src.diagnosis.gap_diagnosis import diagnose_gaps as _run_diagnosis
    from src.extraction.schemas import StartupProfile
    from src.scoring.defensibility_score import DefensibilityScoreResult
    from src.scoring.inception_fit_score import InceptionFitScoreResult
    from src.scoring.production_readiness import ProductionReadinessResult
    from src.validation.evidence_validator import ValidatedEvidence

    errors: list[str] = []
    gaps: list[str] = []
    gap_diagnosis: dict[str, Any] = {}

    if not profile_raw:
        return gaps, gap_diagnosis, errors

    try:
        profile = StartupProfile.model_validate(profile_raw)
    except Exception as exc:
        return gaps, gap_diagnosis, [f"Failed to deserialize startup_profile: {exc}"]

    validated_evidence_objs: list[ValidatedEvidence] = []
    for ev_dict in validated_evidence_dicts:
        try:
            validated_evidence_objs.append(ValidatedEvidence.model_validate(ev_dict))
        except Exception as exc:
            errors.append(f"Failed to deserialize validated_evidence: {exc}")

    classification: ClassificationResult | None = None
    if classification_raw:
        try:
            classification = ClassificationResult.model_validate(classification_raw)
        except Exception as exc:
            errors.append(f"Failed to deserialize classification_result: {exc}")
    if classification is None:
        errors.append("No classification result available for gap diagnosis")
        return gaps, gap_diagnosis, errors

    defensibility: DefensibilityScoreResult | None = None
    if defensibility_raw is not None:
        try:
            defensibility = DefensibilityScoreResult.model_validate(defensibility_raw)
        except Exception:
            pass

    inception_fit: InceptionFitScoreResult | None = None
    if inception_fit_raw is not None:
        try:
            inception_fit = InceptionFitScoreResult.model_validate(inception_fit_raw)
        except Exception:
            pass

    production_readiness: ProductionReadinessResult | None = None
    if production_readiness_raw is not None:
        try:
            production_readiness = ProductionReadinessResult.model_validate(production_readiness_raw)
        except Exception:
            pass

    try:
        result = _run_diagnosis(
            startup_name=startup_name,
            profile=profile,
            classification=classification,
            validated_evidence=validated_evidence_objs,
            defensibility=defensibility,
            inception_fit=inception_fit,
            production_readiness=production_readiness,
        )
    except Exception as exc:
        return gaps, gap_diagnosis, [f"Gap diagnosis failed: {exc}"]

    gaps = [g.gap.value for g in result.diagnosed_gaps if g.detected]
    gap_diagnosis = result.model_dump(mode="json")
    return gaps, gap_diagnosis, errors


def rank_recommendations(
    startup_name: str,
    profile_raw: dict[str, Any] | None,
    classification_raw: dict[str, Any] | None,
    validated_evidence_dicts: list[dict[str, Any]],
    defensibility_raw: dict[str, Any] | None,
    inception_fit_raw: dict[str, Any] | None,
    production_readiness_raw: dict[str, Any] | None,
    scores_raw: dict[str, Any] | None,
    gap_diagnosis_raw: dict[str, Any] | None,
    rag_contexts: list[str],
) -> tuple[list[str], list[str]]:
    _ensure_not_product_runtime()

    from src.classification.ai_native_classifier import ClassificationResult
    from src.diagnosis.schemas import GapDiagnosisResult
    from src.extraction.schemas import StartupProfile
    from src.rag.schemas import RagPipelineOutput
    from src.recommendation.recommendation_engine import build_recommendations
    from src.recommendation.schemas import RecommendationResult
    from src.scoring.composite_ranking import CompositeResult
    from src.scoring.defensibility_score import DefensibilityScoreResult
    from src.scoring.inception_fit_score import InceptionFitScoreResult
    from src.scoring.production_readiness import ProductionReadinessResult
    from src.validation.evidence_validator import ValidatedEvidence

    recommendations: list[str] = []
    errors: list[str] = []

    if not profile_raw or not classification_raw or not gap_diagnosis_raw:
        return recommendations, errors

    try:
        profile = StartupProfile.model_validate(profile_raw)
    except Exception as exc:
        return recommendations, [f"Failed to deserialize startup_profile: {exc}"]

    try:
        classification = ClassificationResult.model_validate(classification_raw)
    except Exception as exc:
        return recommendations, [f"Failed to deserialize classification_result: {exc}"]

    try:
        gap_diagnosis = GapDiagnosisResult.model_validate(gap_diagnosis_raw)
    except Exception as exc:
        return recommendations, [f"Failed to deserialize gap_diagnosis: {exc}"]

    validated_evidence_objs: list[ValidatedEvidence] = []
    for ev_dict in validated_evidence_dicts:
        try:
            validated_evidence_objs.append(ValidatedEvidence.model_validate(ev_dict))
        except Exception as exc:
            errors.append(f"Failed to deserialize validated_evidence: {exc}")

    defensibility: DefensibilityScoreResult | None = None
    if defensibility_raw is not None:
        try:
            defensibility = DefensibilityScoreResult.model_validate(defensibility_raw)
        except Exception:
            pass

    inception_fit: InceptionFitScoreResult | None = None
    if inception_fit_raw is not None:
        try:
            inception_fit = InceptionFitScoreResult.model_validate(inception_fit_raw)
        except Exception:
            pass

    production_readiness: ProductionReadinessResult | None = None
    if production_readiness_raw is not None:
        try:
            production_readiness = ProductionReadinessResult.model_validate(production_readiness_raw)
        except Exception:
            pass

    composite: CompositeResult | None = None
    composite_score = 0.0
    if scores_raw and "composite" in scores_raw:
        composite_score = float(scores_raw["composite"])
        try:
            from src.extraction.schemas import ConfidenceLevel

            composite = CompositeResult(
                startup_id=startup_name,
                composite_score=composite_score,
                defensibility_score=float(scores_raw.get("defensibility", 0)),
                inception_fit_score=float(scores_raw.get("inception_fit", 0)),
                production_readiness_score=float(scores_raw.get("production_readiness", 0)),
                classification_score=0.0,
                confidence=ConfidenceLevel(scores_raw.get("composite_confidence", "low")),
                confidence_penalty_applied=0.0,
                reasoning="",
            )
        except Exception:
            pass

    rag_context: RagPipelineOutput | None = None
    if rag_contexts:
        rag_context = RagPipelineOutput(
            missing_context=False,
            rag_quality_summary=f"Retrieved {len(rag_contexts)} context chunks",
        )

    try:
        result: RecommendationResult = build_recommendations(
            startup_name=startup_name,
            profile=profile,
            classification=classification,
            validated_evidence=validated_evidence_objs,
            defensibility=defensibility,
            inception_fit=inception_fit,
            production_readiness=production_readiness,
            composite=composite,
            final_priority_score=composite_score,
            recommended_motion="monitor_and_nurture",
            gap_diagnosis=gap_diagnosis,
            rag_context=rag_context,
        )
    except Exception as exc:
        return recommendations, [f"Recommendation generation failed: {type(exc).__name__}: {exc}"]

    for rec in result.recommendations:
        line = (
            f"[{rec.action.value}] {rec.diagnosed_gap.value}: "
            f"priority={rec.priority.value}, "
            f"confidence={rec.confidence.value}, "
            f"techs={', '.join(rec.recommended_nvidia_technologies)}"
        )
        recommendations.append(line)

    return recommendations, errors

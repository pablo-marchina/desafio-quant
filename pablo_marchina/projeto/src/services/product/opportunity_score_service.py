from __future__ import annotations

from math import isfinite
from typing import Any

from sqlalchemy.orm import Session

from src.database.models import (
    ActivationDossierRecord,
    ActivationRecommendationRecord,
    AnalysisRun,
    ClaimRecord,
    GapDiagnosisRecord,
    NvidiaMappingRecord,
    ProductQualityRun,
    ScoreRecord,
)
from src.repositories.claim import ClaimRepository
from src.repositories.opportunity_score import OpportunityScoreRepository

# ---------------------------------------------------------------------------
# Component weights (must sum to 1.0)
# ---------------------------------------------------------------------------
_W_COMPOSITE_RANKING = 0.20
_W_EVIDENCE_COVERAGE = 0.15
_W_GAP_RESOLUTION = 0.12
_W_NVIDIA_MAPPING = 0.10
_W_ACTIVATION_READINESS = 0.10
_W_DOSSIER_COMPLETENESS = 0.10
_W_QUALITY_SCORE = 0.08
_W_CLAIM_SUPPORT = 0.07
_W_REVIEW_STATUS = 0.05
_W_PRODUCTION_READINESS = 0.03

_COMPONENT_WEIGHTS: list[tuple[str, float]] = [
    ("composite_ranking", _W_COMPOSITE_RANKING),
    ("evidence_coverage", _W_EVIDENCE_COVERAGE),
    ("gap_resolution", _W_GAP_RESOLUTION),
    ("nvidia_mapping", _W_NVIDIA_MAPPING),
    ("activation_readiness", _W_ACTIVATION_READINESS),
    ("dossier_completeness", _W_DOSSIER_COMPLETENESS),
    ("quality_score", _W_QUALITY_SCORE),
    ("claim_support", _W_CLAIM_SUPPORT),
    ("review_status", _W_REVIEW_STATUS),
    ("production_readiness", _W_PRODUCTION_READINESS),
]

# ---------------------------------------------------------------------------
# Score tiers
# ---------------------------------------------------------------------------
TIER_CRITICAL = "critical"
TIER_HIGH = "high"
TIER_MEDIUM = "medium"
TIER_LOW = "low"
TIER_NOT_RECOMMENDED = "not_recommended"


def _determine_tier(score: float, has_contraindication: bool) -> str:
    if has_contraindication:
        return TIER_NOT_RECOMMENDED
    if score >= 0.85:
        return TIER_CRITICAL
    if score >= 0.70:
        return TIER_HIGH
    if score >= 0.50:
        return TIER_MEDIUM
    if score >= 0.30:
        return TIER_LOW
    return TIER_NOT_RECOMMENDED


# ---------------------------------------------------------------------------
# Penalty definitions
# ---------------------------------------------------------------------------

PENALTY_UNSUPPORTED_CLAIMS = "unsupported_claims"
PENALTY_LOW_EVIDENCE_COVERAGE = "low_evidence_coverage"
PENALTY_CRITICAL_UNSUPPORTED = "critical_unsupported"
PENALTY_DEGRADED_STATES = "degraded_states"
PENALTY_LOW_CONFIDENCE = "low_confidence"
PENALTY_CONTRAINDICATION = "contraindication"
PENALTY_INCOMPLETE_DATA = "incomplete_data"
PENALTY_NON_AI = "non_ai_classification"


def _compute_claim_penalties(
    claims: list[ClaimRecord],
    total_claims: int,
) -> list[dict[str, Any]]:
    penalties: list[dict[str, Any]] = []
    if total_claims == 0:
        return penalties

    unsupported = sum(1 for c in claims if c.support_level == "unsupported")
    critical_unsupported = sum(
        1 for c in claims if c.support_level == "unsupported" and c.claim_type in ("ai_native_claim", "gap_claim")
    )

    if unsupported > 0:
        unsupported_rate = unsupported / total_claims
        penalty = min(unsupported_rate * 0.15, 0.15)
        penalties.append(
            {
                "type": PENALTY_UNSUPPORTED_CLAIMS,
                "value": round(penalty, 4),
                "detail": f"{unsupported}/{total_claims} claims unsupported",
            }
        )

    if critical_unsupported > 0:
        penalty = min(critical_unsupported * 0.10, 0.20)
        penalties.append(
            {
                "type": PENALTY_CRITICAL_UNSUPPORTED,
                "value": round(penalty, 4),
                "detail": f"{critical_unsupported} critical claims unsupported",
            }
        )

    return penalties


def _compute_evidence_coverage_penalty(
    evidence_coverage: float | None,
) -> list[dict[str, Any]]:
    if evidence_coverage is None:
        return []
    if evidence_coverage < 0.30:
        return [
            {
                "type": PENALTY_LOW_EVIDENCE_COVERAGE,
                "value": 0.10,
                "detail": f"Evidence coverage {evidence_coverage:.2f} < 0.30",
            }
        ]
    if evidence_coverage < 0.50:
        return [
            {
                "type": PENALTY_LOW_EVIDENCE_COVERAGE,
                "value": 0.05,
                "detail": f"Evidence coverage {evidence_coverage:.2f} < 0.50",
            }
        ]
    return []


def _compute_degraded_penalty(
    degraded_count: int,
) -> list[dict[str, Any]]:
    if degraded_count == 0:
        return []
    penalty = min(degraded_count * 0.03, 0.12)
    return [
        {
            "type": PENALTY_DEGRADED_STATES,
            "value": round(penalty, 4),
            "detail": f"{degraded_count} degraded states",
        }
    ]


def _compute_contraindication_penalty(
    claim_records: list[ClaimRecord],
) -> list[dict[str, Any]]:
    contraindicated = [
        c
        for c in claim_records
        if c.claim_type == "risk_claim"
        and c.support_level in ("strong", "medium")
        and "not_recommended" in c.claim_text.lower()
    ]
    if contraindicated:
        return [
            {
                "type": PENALTY_CONTRAINDICATION,
                "value": 1.0,
                "detail": f"{len(contraindicated)} contraindication claims found",
            }
        ]
    return []


def _compute_non_ai_penalty(
    classification_score: float | None,
) -> list[dict[str, Any]]:
    if classification_score is not None and classification_score < 0.1:
        return [
            {
                "type": PENALTY_NON_AI,
                "value": 1.0,
                "detail": "Classification indicates NON_AI",
            }
        ]
    return []


def _compute_low_confidence_penalty(
    composite_confidence: str | None,
) -> list[dict[str, Any]]:
    if composite_confidence == "low":
        return [
            {
                "type": PENALTY_LOW_CONFIDENCE,
                "value": 0.05,
                "detail": "Composite ranking confidence is low",
            }
        ]
    return []


def _compute_incomplete_data_penalty(
    missing_components: list[str],
    component_names_present: list[str],
) -> list[dict[str, Any]]:
    if missing_components:
        total = max(len(component_names_present) + len(missing_components), 1)
        rate = len(missing_components) / total
        return [
            {
                "type": PENALTY_INCOMPLETE_DATA,
                "value": round(rate * 0.10, 4),
                "detail": f"Missing components: {', '.join(missing_components)}",
            }
        ]
    return []


# ---------------------------------------------------------------------------
# Component value extractors
# ---------------------------------------------------------------------------


def _get_composite_ranking(
    scores: dict[str, ScoreRecord],
    output_snapshot: dict[str, Any],
) -> tuple[float | None, str | None]:
    composite_conf: str | None = None
    if "composite" in scores:
        composite_conf = scores["composite"].confidence
    elif output_snapshot.get("composite_score", {}).get("confidence"):
        composite_conf = output_snapshot["composite_score"]["confidence"]

    composite_val: float | None = None
    if "composite" in scores:
        composite_val = scores["composite"].value
    elif output_snapshot.get("composite_score", {}).get("composite_score"):
        raw = output_snapshot["composite_score"]["composite_score"]
        if isinstance(raw, (int, float)) and isfinite(raw):
            composite_val = raw / 100.0

    return composite_val, composite_conf


def _get_evidence_coverage(
    analysis_run_id: str,
    session: Session,
) -> float | None:
    try:
        cov = ClaimRepository(session).get_evidence_coverage_summary(analysis_run_id)
        if cov["total_claims"] > 0:
            val = cov.get("evidence_coverage")
            if val is not None and isinstance(val, (int, float)):
                return float(val)
    except Exception:
        pass
    return None


def _get_gap_resolution(
    gaps: list[GapDiagnosisRecord],
) -> float:
    if not gaps:
        return 0.5
    detected = sum(1 for g in gaps if g.detected)
    if detected == 0:
        return 1.0
    resolved = sum(1 for g in gaps if not g.detected)
    return resolved / len(gaps)


def _get_nvidia_mapping_score(
    mappings: list[NvidiaMappingRecord],
) -> float:
    if not mappings:
        return 0.0
    high_priority = sum(1 for m in mappings if m.priority in ("high", "critical"))
    return min(high_priority / max(len(mappings), 1), 1.0)


def _get_activation_readiness(
    recommendations: list[ActivationRecommendationRecord],
) -> float:
    if not recommendations:
        return 0.0
    with_next_step = sum(1 for r in recommendations if r.next_step)
    high_confidence = sum(1 for r in recommendations if r.confidence in ("high", "medium"))
    step_ratio = with_next_step / len(recommendations)
    conf_ratio = high_confidence / len(recommendations)
    score = step_ratio * 0.5 + conf_ratio * 0.5
    return score


def _get_dossier_completeness(
    dossiers: list[ActivationDossierRecord],
) -> float:
    if not dossiers:
        return 0.0
    latest = max(dossiers, key=lambda d: d.version)
    return latest.evidence_coverage


def _get_quality_score(
    quality_runs: list[ProductQualityRun],
) -> float | None:
    if not quality_runs:
        return None
    latest = max(quality_runs, key=lambda q: q.created_at)
    if latest.status in ("completed", "degraded") and latest.summary_json:
        raw = latest.summary_json.get("export_readiness_score")
        if raw is not None and isinstance(raw, (int, float)):
            return float(raw)
    return None


def _get_claim_support(
    claims: list[ClaimRecord],
) -> float:
    if not claims:
        return 0.0
    supported = sum(1 for c in claims if c.support_level in ("strong", "medium"))
    return supported / len(claims)


def _get_review_status_score(
    analysis_run: AnalysisRun,
) -> float:
    reviews = analysis_run.reviews
    if not reviews:
        return 0.3
    latest = max(reviews, key=lambda r: r.created_at)
    decision_map = {
        "approve": 1.0,
        "needs_more_evidence": 0.5,
        "monitor": 0.5,
        "contact": 0.7,
        "reject": 0.0,
        "not_recommended": 0.0,
    }
    return decision_map.get(latest.decision, 0.3)


def _get_production_readiness(
    scores: dict[str, ScoreRecord],
) -> float | None:
    if "production_readiness" in scores:
        return scores["production_readiness"].value / 100.0
    return None


# ---------------------------------------------------------------------------
# Evidence refs aggregation
# ---------------------------------------------------------------------------


def _aggregate_evidence_refs(
    claims: list[ClaimRecord],
    recommendations: list[ActivationRecommendationRecord],
    dossiers: list[ActivationDossierRecord],
    rag_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()

    for c in claims:
        for ref in c.evidence_refs_json:
            ref_id = ref.get("id") or str(ref)
            if ref_id not in seen:
                seen.add(ref_id)
                refs.append(ref)

    for r in recommendations:
        for ref in r.evidence_refs_json:
            ref_id = ref.get("id") or str(ref)
            if ref_id not in seen:
                seen.add(ref_id)
                refs.append(ref)

    for d in dossiers:
        dossier_refs = d.dossier_json.get("evidence_refs", [])
        if isinstance(dossier_refs, list):
            for ref in dossier_refs:
                ref_id = ref.get("id") or str(ref)
                if ref_id not in seen:
                    seen.add(ref_id)
                    refs.append(ref)

    rag_chunks = rag_snapshot.get("rag_chunks", [])
    if isinstance(rag_chunks, list):
        for chunk in rag_chunks:
            chunk_id = chunk.get("chunk_id") or str(chunk)
            if chunk_id not in seen:
                seen.add(chunk_id)
                refs.append({"id": chunk_id, "source": "rag_chunk"})

    return refs


# ---------------------------------------------------------------------------
# Recommended action
# ---------------------------------------------------------------------------


def _determine_recommended_action(
    recommendations: list[ActivationRecommendationRecord],
    dossiers: list[ActivationDossierRecord],
    composite_conf: str | None,
    score_tier: str,
) -> str:
    if score_tier == TIER_NOT_RECOMMENDED:
        return "not_recommended"

    if recommendations:
        top = min(recommendations, key=lambda r: r.priority)
        if top.next_step:
            return top.next_step
        if top.recommended_motion:
            return top.recommended_motion

    if dossiers:
        latest = max(dossiers, key=lambda d: d.version)
        if latest.recommended_motion:
            return latest.recommended_motion
        next_action = latest.dossier_json.get("next_action")
        if next_action and isinstance(next_action, str):
            return next_action

    if composite_conf == "low":
        return "needs_more_evidence"

    return "needs_more_evidence"


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------


class OpportunityScoreService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = OpportunityScoreRepository(session)

    def compute_score(
        self,
        analysis_run_id: str,
    ) -> dict[str, Any]:
        analysis_run = self.session.get(AnalysisRun, analysis_run_id)
        if analysis_run is None:
            raise ValueError(f"Analysis run {analysis_run_id} not found")

        scores_map = {s.score_type: s for s in analysis_run.scores}
        gaps = list(analysis_run.gaps)
        mappings = list(analysis_run.mappings)
        recommendations = list(analysis_run.activation_recommendations)
        dossiers = list(analysis_run.dossiers)
        quality_runs = list(analysis_run.quality_runs)

        claim_repo = ClaimRepository(self.session)
        claims = list(claim_repo.list_claims_for_analysis_run(analysis_run_id))

        output_snapshot = analysis_run.output_snapshot_json or {}
        rag_snapshot = output_snapshot.get("rag", {})

        composite_val, composite_conf = _get_composite_ranking(scores_map, output_snapshot)

        evidence_coverage = _get_evidence_coverage(analysis_run_id, self.session)
        gap_resolution = _get_gap_resolution(gaps)
        nvidia_mapping_score = _get_nvidia_mapping_score(mappings)
        activation_readiness = _get_activation_readiness(recommendations)
        dossier_completeness = _get_dossier_completeness(dossiers)
        quality_score = _get_quality_score(quality_runs)
        claim_support = _get_claim_support(claims)
        review_status_score = _get_review_status_score(analysis_run)
        production_readiness = _get_production_readiness(scores_map)

        component_values: dict[str, float | None] = {
            "composite_ranking": composite_val,
            "evidence_coverage": evidence_coverage,
            "gap_resolution": gap_resolution,
            "nvidia_mapping": nvidia_mapping_score,
            "activation_readiness": activation_readiness,
            "dossier_completeness": dossier_completeness,
            "quality_score": quality_score,
            "claim_support": claim_support,
            "review_status": review_status_score,
            "production_readiness": production_readiness,
        }

        present_components: list[tuple[str, float, float]] = []
        missing_components: list[str] = []
        for name, val in component_values.items():
            if val is not None:
                weight = dict(_COMPONENT_WEIGHTS)[name]
                present_components.append((name, val, weight))
            else:
                missing_components.append(name)

        total_weight = sum(w for _, _, w in present_components)
        if not present_components or total_weight == 0:
            base_score = 0.0
        else:
            base_score = sum(val * (weight / total_weight) for _, val, weight in present_components)

        # Compute penalties
        all_penalties: list[dict[str, Any]] = []
        all_penalties.extend(_compute_claim_penalties(claims, len(claims)))
        all_penalties.extend(_compute_evidence_coverage_penalty(evidence_coverage))

        degraded_count = sum(1 for rc in analysis_run.readiness_checks if rc.status in ("degraded", "error"))
        all_penalties.extend(_compute_degraded_penalty(degraded_count))

        all_penalties.extend(_compute_contraindication_penalty(claims))

        classification_score = None
        if composite_val is not None:
            classification_score = composite_val
        all_penalties.extend(_compute_non_ai_penalty(classification_score))

        all_penalties.extend(_compute_low_confidence_penalty(composite_conf))
        all_penalties.extend(_compute_incomplete_data_penalty(missing_components, list(component_values.keys())))

        penalty_total = sum(p["value"] for p in all_penalties)
        has_contraindication = any(p["type"] == PENALTY_CONTRAINDICATION for p in all_penalties)
        has_non_ai = any(p["type"] == PENALTY_NON_AI for p in all_penalties)

        final_score = max(0.0, min(1.0, base_score - penalty_total))
        score_tier = _determine_tier(final_score, has_contraindication or has_non_ai)

        evidence_refs = _aggregate_evidence_refs(claims, recommendations, dossiers, rag_snapshot)

        recommended_action = _determine_recommended_action(recommendations, dossiers, composite_conf, score_tier)

        # Build reasoning
        reasoning_lines = [
            f"Opportunity Score: {final_score:.4f} (tier: {score_tier})",
        ]
        for name, val, weight in present_components:
            orig_weight = dict(_COMPONENT_WEIGHTS)[name]
            redistributed_weight = weight / total_weight if total_weight > 0 else 0
            reasoning_lines.append(f"  {name}: {val:.4f} (w: {orig_weight}, redist: {redistributed_weight:.4f})")
        if missing_components:
            reasoning_lines.append(f"  Missing components: {', '.join(missing_components)}")
        if all_penalties:
            reasoning_lines.append(f"  Penalties: {penalty_total:.4f}")
            for p in all_penalties:
                reasoning_lines.append(f"    - {p['type']}: {p['value']} ({p['detail']})")
        reasoning_lines.append(f"  Recommended action: {recommended_action}")

        # Persist
        self.repo.replace_latest_for_analysis_run(
            analysis_run_id=analysis_run_id,
            opportunity_score=round(final_score, 4),
            score_tier=score_tier,
            components={
                name: {"value": val, "weight": dict(_COMPONENT_WEIGHTS)[name]} for name, val in component_values.items()
            },
            penalties=all_penalties,
            penalty_total=round(penalty_total, 4),
            evidence_refs=evidence_refs,
            recommended_action=recommended_action,
            reasoning="\n".join(reasoning_lines),
        )
        self.session.commit()

        return {
            "opportunity_score": round(final_score, 4),
            "score_tier": score_tier,
            "components": component_values,
            "penalties": all_penalties,
            "penalty_total": round(penalty_total, 4),
            "evidence_ref_count": len(evidence_refs),
            "recommended_action": recommended_action,
            "reasoning": "\n".join(reasoning_lines),
        }

    def get_latest_score(
        self,
        analysis_run_id: str,
    ) -> dict[str, Any] | None:
        record = self.repo.get_latest_for_analysis_run(analysis_run_id)
        if record is None:
            return None
        return {
            "id": record.id,
            "analysis_run_id": record.analysis_run_id,
            "score_version": record.score_version,
            "opportunity_score": record.opportunity_score,
            "score_tier": record.score_tier,
            "components": record.components_json,
            "penalties": record.penalties_json,
            "penalty_total": record.penalty_total,
            "evidence_refs": record.evidence_refs_json,
            "recommended_action": record.recommended_action,
            "reasoning": record.reasoning,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def list_ranked_opportunities(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        min_score: float | None = None,
        tier: str | None = None,
        recommended_action: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        from src.services.product.opportunity_service import OpportunityService

        opp_service = OpportunityService(self.session)
        items, total = opp_service.list_opportunities(offset=0, limit=10000)

        startup_run_map: dict[str, str] = {}
        for item in items:
            rid = item.get("latest_analysis_run_id")
            sid = item.get("startup_id")
            if rid and sid:
                startup_run_map[rid] = sid

        run_ids = list(startup_run_map.keys())
        latest_scores = self.repo.list_latest_for_runs(run_ids)

        ranked: list[dict[str, Any]] = []
        for run_id, sid in startup_run_map.items():
            score_record = latest_scores.get(run_id)
            if score_record is None:
                continue

            if min_score is not None and score_record.opportunity_score < min_score:
                continue
            if tier is not None and score_record.score_tier != tier:
                continue
            if recommended_action is not None:
                if score_record.recommended_action != recommended_action:
                    continue

            startup_info = next(
                (item for item in items if item.get("startup_id") == sid),
                {},
            )

            ranked.append(
                {
                    "startup_id": sid,
                    "startup_name": startup_info.get("startup_name", ""),
                    "sector": startup_info.get("sector", ""),
                    "latest_analysis_run_id": run_id,
                    "opportunity_score": score_record.opportunity_score,
                    "score_tier": score_record.score_tier,
                    "components": score_record.components_json,
                    "penalties": score_record.penalties_json,
                    "penalty_total": score_record.penalty_total,
                    "evidence_ref_count": len(score_record.evidence_refs_json),
                    "recommended_action": score_record.recommended_action,
                    "reasoning": score_record.reasoning,
                    "score_version": score_record.score_version,
                    "created_at": score_record.created_at,
                }
            )

        ranked.sort(key=lambda r: r["opportunity_score"], reverse=True)
        total = len(ranked)
        page = ranked[offset : offset + limit]
        return page, total

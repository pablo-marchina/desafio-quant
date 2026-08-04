from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.briefing.schemas import (
    ActionBrief,
    ActionBriefMetrics,
    ActionBriefStatus,
    AuditTrail,
    Blockers,
    CalibrationSnapshot,
    QualityGateSnapshot,
    TopRecommendation,
)


def _utc_now_str() -> str:
    return datetime.now(UTC).isoformat()


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item)]


def _quality_status_blocks(quality_status: str | None) -> bool:
    if quality_status is None:
        return False
    return quality_status == "failed" or quality_status.startswith("blocked")


def _quality_status_needs_review(quality_status: str | None) -> bool:
    return quality_status == "needs_review"


def _unique(values: list[str]) -> list[str]:
    return sorted(set(values))


def _gap_metric(
    gap_diagnosis_metrics: dict[str, Any] | None,
    gap_diagnosis_summary: dict[str, Any] | None,
    field: str,
) -> float:
    if gap_diagnosis_metrics and isinstance(gap_diagnosis_metrics.get(field), (int, float)):
        return float(gap_diagnosis_metrics[field])
    if gap_diagnosis_summary and isinstance(gap_diagnosis_summary, dict):
        gaps_raw = gap_diagnosis_summary.get("gaps", [])
        values = [float(g[field]) for g in gaps_raw if isinstance(g, dict) and isinstance(g.get(field), (int, float))]
        return _mean(values)
    return 0.0


def _claim_ids_for_gap(claims: list[dict[str, Any]], gap_type: str) -> list[str]:
    if not gap_type:
        return []
    gap_words = gap_type.replace("_", " ").lower()
    claim_ids: list[str] = []
    for claim in claims:
        text = str(claim.get("claim_text", "")).lower()
        if gap_words not in text:
            continue
        claim_id = claim.get("claim_id") or claim.get("id")
        if claim_id:
            claim_ids.append(str(claim_id))
    return _unique(claim_ids)


def _quality_snapshot(quality: dict[str, Any] | None) -> QualityGateSnapshot:
    if not quality:
        return QualityGateSnapshot()
    return QualityGateSnapshot(
        status=str(quality.get("status", "")),
        failed_checks=_ids(quality.get("failed_checks", [])),
        warning_checks=_ids(quality.get("warning_checks", [])),
    )


def _missing_calibration_count(
    state: dict[str, Any],
    nvidia_rec_metrics: dict[str, Any],
    gap_diagnosis_metrics: dict[str, Any] | None,
    scoring_summary: dict[str, Any] | None,
) -> int:
    total = int(nvidia_rec_metrics.get("missing_recommendation_calibration_count", 0) or 0)
    mapping_metrics = state.get("nvidia_mapping_calibration_metrics", {})
    if isinstance(mapping_metrics, dict):
        total += int(mapping_metrics.get("missing_calibration_count", 0) or 0)
    if gap_diagnosis_metrics:
        total += int(gap_diagnosis_metrics.get("missing_calibration_count", 0) or 0)
    if scoring_summary:
        total += int(scoring_summary.get("missing_calibration_count", 0) or 0)
    return total


def _has_uncalibrated_status(state: dict[str, Any]) -> bool:
    nvidia_mapping_summary = state.get("nvidia_mapping_summary")
    evidence_validation = state.get("evidence_validation")
    scoring_summary = state.get("startup_scoring_summary")
    statuses = [
        state.get("rag_retrieval_status"),
        state.get("gap_diagnosis_status"),
        scoring_summary.get("scoring_status") if isinstance(scoring_summary, dict) else None,
        (nvidia_mapping_summary.get("mapping_status") if isinstance(nvidia_mapping_summary, dict) else None),
        evidence_validation.get("status") if isinstance(evidence_validation, dict) else None,
    ]
    return any(isinstance(status, str) and "blocked_uncalibrated" in status for status in statuses)


def _top_recommendation(
    rec: dict[str, Any],
    *,
    claims: list[dict[str, Any]],
    ai_native_score_value: float | None,
    nvidia_fit_score_value: float | None,
    gap_diagnosis_metrics: dict[str, Any] | None,
    gap_diagnosis_summary: dict[str, Any] | None,
) -> TopRecommendation:
    gap_type = str(rec.get("gap_type", ""))
    evidence_ids = _ids(rec.get("supporting_evidence_ids", []))
    rag_ids = _ids(rec.get("supporting_rag_context_ids", []))
    calibration_ids = _ids(rec.get("calibration_decision_ids", []))
    gap_severity = _gap_metric(
        gap_diagnosis_metrics,
        gap_diagnosis_summary,
        "average_gap_severity",
    )
    gap_confidence = _gap_metric(
        gap_diagnosis_metrics,
        gap_diagnosis_summary,
        "average_gap_confidence",
    )

    reason_parts = [
        f"gap_type={gap_type}",
        f"nvidia_technology={rec.get('nvidia_technology', '')}",
        f"mapping_score={_number(rec.get('mapping_score'))}",
        f"mapping_confidence={_number(rec.get('mapping_confidence'))}",
        f"priority_score={_number(rec.get('recommendation_priority_score'))}",
        f"confidence={_number(rec.get('confidence'))}",
        f"uncertainty={_number(rec.get('uncertainty'), 1.0)}",
        f"business_impact={_number(rec.get('business_impact'))}",
        f"implementation_complexity={_number(rec.get('implementation_complexity'))}",
        f"supporting_evidence_count={len(evidence_ids)}",
        f"supporting_rag_context_count={len(rag_ids)}",
        "production_allowed=true",
    ]

    return TopRecommendation(
        recommendation_id=str(rec.get("recommendation_id", "")),
        nvidia_technology=str(rec.get("nvidia_technology", "")),
        gap_id=str(rec.get("gap_id", "")),
        gap_type=gap_type,
        recommendation_priority_score=_number(rec.get("recommendation_priority_score")),
        recommendation_confidence=_number(rec.get("confidence")),
        uncertainty=_number(rec.get("uncertainty"), 1.0),
        mapping_score=_number(rec.get("mapping_score")),
        mapping_confidence=_number(rec.get("mapping_confidence")),
        business_impact=_number(rec.get("business_impact")),
        implementation_complexity=_number(rec.get("implementation_complexity")),
        ai_native_score_value=ai_native_score_value,
        nvidia_fit_score_value=nvidia_fit_score_value,
        gap_severity_score=gap_severity,
        gap_confidence_score=gap_confidence,
        supporting_evidence_ids=evidence_ids,
        supporting_rag_context_ids=rag_ids,
        supporting_claim_ids=_claim_ids_for_gap(claims, gap_type),
        calibration_decision_ids=calibration_ids,
        next_best_action=str(rec.get("next_best_action", "")),
        reason_grounded_in_scores="; ".join(reason_parts),
        production_allowed=True,
    )


def _recommendation_blocker(rec: dict[str, Any], source: str) -> Blockers:
    blockers = _ids(rec.get("blockers", []))
    if rec.get("production_allowed", False):
        if not rec.get("supporting_evidence_ids"):
            blockers.append("production_allowed recommendation missing evidence support")
        if not rec.get("supporting_rag_context_ids"):
            blockers.append("production_allowed recommendation missing RAG support")
    description = (
        f"Recommendation {rec.get('recommendation_id', '?')} "
        f"({rec.get('nvidia_technology', '?')}) blocked: "
        + ("; ".join(blockers) if blockers else "production_allowed=false")
    )
    calibration_block = any("calibrat" in blocker.lower() for blocker in blockers)
    return Blockers(
        blocker_id=str(rec.get("recommendation_id", "")),
        description=description,
        source=source,
        severity="high" if calibration_block else "medium",
    )


def build_quantitative_brief(state: dict[str, Any]) -> dict[str, Any]:
    run_id = str(state.get("run_id", "unknown"))
    startup_id = state.get("startup_id")
    scores: dict[str, Any] = state.get("scores", {})
    quality: dict[str, Any] | None = state.get("quality")
    nvidia_rec_metrics: dict[str, Any] = state.get("nvidia_recommendation_metrics", {})
    all_recommendations: list[dict[str, Any]] = list(state.get("nvidia_recommendations", []))
    claims: list[dict[str, Any]] = list(state.get("claims", []))
    accepted_evidence_items: list[dict[str, Any]] = list(state.get("accepted_evidence_items", []))
    evidence_items: list[dict[str, Any]] = list(state.get("evidence_items", []))
    rag_contexts: list[Any] = list(state.get("rag_contexts", []))
    existing_blockers = _ids(state.get("blockers", []))
    executed_nodes = _ids(state.get("executed_nodes", []))
    gap_diagnosis_metrics: dict[str, Any] | None = state.get("gap_diagnosis_metrics")
    gap_diagnosis_summary: dict[str, Any] | None = state.get("gap_diagnosis_summary")
    scoring_summary: dict[str, Any] | None = state.get("startup_scoring_summary")

    ai_native_score_value = (
        _number(scores.get("ai_native_score")) if scores.get("ai_native_score") is not None else None
    )
    nvidia_fit_score_value = (
        _number(scores.get("nvidia_fit_score")) if scores.get("nvidia_fit_score") is not None else None
    )

    raw_production_recs = [rec for rec in all_recommendations if rec.get("production_allowed", False)]
    final_recs = [
        rec
        for rec in raw_production_recs
        if rec.get("supporting_evidence_ids") and rec.get("supporting_rag_context_ids")
    ]
    inconsistent_recs = [rec for rec in raw_production_recs if rec not in final_recs]
    blocked_recs = [rec for rec in all_recommendations if not rec.get("production_allowed", False)]

    recommendation_count = len(all_recommendations)
    final_recommendation_count = len(final_recs)
    blocked_recommendation_count = recommendation_count - final_recommendation_count

    priority_scores = [
        _number(rec.get("recommendation_priority_score"))
        for rec in final_recs
        if isinstance(rec.get("recommendation_priority_score"), (int, float))
    ]
    confidence_scores = [
        _number(rec.get("confidence")) for rec in final_recs if isinstance(rec.get("confidence"), (int, float))
    ]
    uncertainty_scores = [
        _number(rec.get("uncertainty"), 1.0) for rec in final_recs if isinstance(rec.get("uncertainty"), (int, float))
    ]

    average_priority_score = _mean(priority_scores)
    average_confidence = _mean(confidence_scores)
    uncertainty_mean = _mean(uncertainty_scores)
    rag_supported_count = sum(1 for rec in final_recs if rec.get("supporting_rag_context_ids"))
    evidence_supported_count = sum(1 for rec in final_recs if rec.get("supporting_evidence_ids"))
    rag_supported_rate = rag_supported_count / max(1, final_recommendation_count)
    evidence_supported_rate = evidence_supported_count / max(1, final_recommendation_count)

    total_gap_count = 0
    if gap_diagnosis_metrics:
        total_gap_count = int(gap_diagnosis_metrics.get("total_gap_count", 0) or 0)
    elif gap_diagnosis_summary and isinstance(gap_diagnosis_summary, dict):
        total_gap_count = len(gap_diagnosis_summary.get("gaps", []))
    covered_gap_count = len(
        {
            str(rec.get("gap_id") or rec.get("gap_type"))
            for rec in final_recs
            if rec.get("gap_id") or rec.get("gap_type")
        }
    )

    accepted_evidence_count = len(accepted_evidence_items)
    rag_context_count = len(rag_contexts)
    unsupported_critical_claims_count = int(state.get("unsupported_critical_claims_count", 0) or 0)
    calibration_decision_ids: list[str] = []
    for rec in all_recommendations:
        calibration_decision_ids.extend(_ids(rec.get("calibration_decision_ids", [])))
    calibration_decision_ids = _unique(calibration_decision_ids)
    missing_calibration_count = _missing_calibration_count(
        state,
        nvidia_rec_metrics,
        gap_diagnosis_metrics,
        scoring_summary,
    )

    blockers = list(existing_blockers)
    inconsistency_blockers: list[str] = []
    for rec in inconsistent_recs:
        rec_id = rec.get("recommendation_id", "?")
        if not rec.get("supporting_evidence_ids"):
            inconsistency_blockers.append(
                f"Recommendation {rec_id} is production_allowed but has no supporting_evidence_ids"
            )
        if not rec.get("supporting_rag_context_ids"):
            inconsistency_blockers.append(
                f"Recommendation {rec_id} is production_allowed but has no supporting_rag_context_ids"
            )

    ranking_status = state.get("ranking_status")
    quality_status = quality.get("status") if quality else None
    has_uncalibrated_inputs = missing_calibration_count > 0 or _has_uncalibrated_status(state)

    brief_status: ActionBriefStatus
    updates_status: str
    review_required: bool
    inconsistency = False

    if ranking_status != "passed":
        brief_status = ActionBriefStatus.BLOCKED_RANKING_NOT_PASSED
        updates_status = "brief_blocked"
        review_required = True
        blockers.append(f"generate_brief: ranking_status is '{ranking_status}' (expected 'passed')")
    elif _quality_status_blocks(quality_status):
        brief_status = ActionBriefStatus.BLOCKED_QUALITY_GATE
        updates_status = "brief_blocked"
        review_required = True
        blockers.append(f"generate_brief: quality status is '{quality_status}'")
    elif unsupported_critical_claims_count > 0:
        brief_status = ActionBriefStatus.FAILED_UNSUPPORTED_CRITICAL_CLAIM
        updates_status = "brief_failed"
        review_required = False
        blockers.append(
            f"generate_brief: {unsupported_critical_claims_count} critical claim(s) without supported evidence"
        )
    elif has_uncalibrated_inputs:
        brief_status = ActionBriefStatus.BLOCKED_UNCALIBRATED_INPUTS
        updates_status = "brief_blocked"
        review_required = True
        blockers.append(
            f"generate_brief: uncalibrated inputs detected (missing_calibration_count={missing_calibration_count})"
        )
    elif inconsistency_blockers:
        brief_status = ActionBriefStatus.FAILED
        updates_status = "brief_failed"
        review_required = False
        inconsistency = True
        blockers.extend(inconsistency_blockers)
    elif not raw_production_recs:
        brief_status = ActionBriefStatus.BLOCKED_NO_PRODUCTION_RECOMMENDATIONS
        updates_status = "brief_blocked"
        review_required = True
        blockers.append("generate_brief: no recommendations with production_allowed=true")
    elif not final_recs:
        brief_status = ActionBriefStatus.FAILED
        updates_status = "brief_failed"
        review_required = False
        blockers.append("generate_brief: no production recommendations have both evidence and RAG support")
    elif _quality_status_needs_review(quality_status):
        brief_status = ActionBriefStatus.NEEDS_REVIEW
        updates_status = "brief_needs_review"
        review_required = True
        blockers.append(f"generate_brief: quality status is '{quality_status}'")
    else:
        brief_status = ActionBriefStatus.PASSED
        updates_status = "brief_generated"
        review_required = False

    blockers = _unique(blockers)

    top_records = [
        _top_recommendation(
            rec,
            claims=claims,
            ai_native_score_value=ai_native_score_value,
            nvidia_fit_score_value=nvidia_fit_score_value,
            gap_diagnosis_metrics=gap_diagnosis_metrics,
            gap_diagnosis_summary=gap_diagnosis_summary,
        )
        for rec in final_recs
    ]

    blocked_entries = [_recommendation_blocker(rec, source="rank_recommendations") for rec in blocked_recs]
    blocked_entries.extend(_recommendation_blocker(rec, source="generate_brief") for rec in inconsistent_recs)
    for blocker in blockers:
        if not any(entry.description == blocker for entry in blocked_entries):
            blocked_entries.append(
                Blockers(
                    description=blocker,
                    source="generate_brief",
                    severity="high",
                )
            )

    next_best_actions: list[str] = []
    for top_rec in top_records:
        if top_rec.next_best_action and top_rec.next_best_action not in next_best_actions:
            next_best_actions.append(top_rec.next_best_action)
    if not next_best_actions:
        first_blocker = blockers[0] if blockers else "brief blockers"
        next_best_actions.append(f"Resolve blocker before brief generation: {first_blocker}")

    evidence_ids = _ids([item.get("id") or item.get("evidence_id") for item in accepted_evidence_items])
    evidence_ids.extend(_ids([item.get("id") or item.get("evidence_id") for item in evidence_items]))
    evidence_ids = _unique(evidence_ids)
    rag_context_ids: list[str] = []
    for rec in final_recs:
        rag_context_ids.extend(_ids(rec.get("supporting_rag_context_ids", [])))
    rag_context_ids = _unique(rag_context_ids)

    audit_trail = AuditTrail(
        executed_nodes=executed_nodes,
        calibration_decision_ids=calibration_decision_ids,
        evidence_ids=evidence_ids,
        rag_context_ids=rag_context_ids,
        blockers=blockers,
        quality_gate_status=str(quality_status) if quality_status else None,
    )

    calibration_snapshot = CalibrationSnapshot(
        calibration_decision_count=len(calibration_decision_ids),
        missing_calibration_count=missing_calibration_count,
    )
    quality_gate_snapshot = _quality_snapshot(quality)

    evidence_validation = state.get("evidence_validation")
    evidence_status = (
        evidence_validation.get("status", "unknown") if isinstance(evidence_validation, dict) else "unknown"
    )
    evidence_summary = (
        f"evidence_items={len(evidence_items)} | "
        f"accepted={accepted_evidence_count} | "
        f"unsupported_critical_claims={unsupported_critical_claims_count} | "
        f"status={evidence_status}"
    )
    rag_summary = (
        f"rag_contexts={rag_context_count} | "
        f"rag_supported_recommendations={rag_supported_count}/{final_recommendation_count} | "
        f"status={state.get('rag_retrieval_status', 'unknown')}"
    )
    gap_summary = (
        f"total_gaps={total_gap_count} | "
        f"covered_by_recommendations={covered_gap_count} | "
        f"status={state.get('gap_diagnosis_status', 'unknown')}"
    )
    scoring_status = scoring_summary.get("scoring_status", "unknown") if scoring_summary else "unknown"
    scoring_summary_text = (
        f"ai_native_score={ai_native_score_value} | nvidia_fit_score={nvidia_fit_score_value} | status={scoring_status}"
    )

    risk_parts: list[str] = []
    if unsupported_critical_claims_count > 0:
        risk_parts.append(f"unsupported_critical_claims={unsupported_critical_claims_count}")
    if accepted_evidence_count == 0 and evidence_items:
        risk_parts.append("no_accepted_evidence")
    if rag_context_count == 0:
        risk_parts.append("no_rag_contexts")
    if inconsistency:
        risk_parts.append("inconsistency_detected")
    if missing_calibration_count > 0:
        risk_parts.append(f"missing_calibration_count={missing_calibration_count}")
    risk_summary = " | ".join(risk_parts) if risk_parts else "none"

    executive_summary: dict[str, Any] = {
        "production_allowed_recommendations": final_recommendation_count,
        "raw_production_allowed_recommendations": len(raw_production_recs),
        "average_priority_score": round(average_priority_score, 4),
        "average_confidence": round(average_confidence, 4),
        "average_uncertainty": round(uncertainty_mean, 4),
        "covered_gaps": covered_gap_count,
        "total_gaps": total_gap_count,
        "accepted_evidence": accepted_evidence_count,
        "rag_supported_recommendation_rate": round(rag_supported_rate, 4),
        "critical_blockers": max(0, len(blockers) - len(existing_blockers)),
        "consistency_check": "failed" if inconsistency else "passed",
    }
    if unsupported_critical_claims_count > 0:
        executive_summary["unsupported_critical_claims"] = unsupported_critical_claims_count

    recommendation_summary_parts = [
        f"{rec.nvidia_technology}(priority={rec.recommendation_priority_score}, "
        f"confidence={rec.recommendation_confidence}, "
        f"uncertainty={rec.uncertainty})"
        for rec in top_records
    ]
    recommendation_summary = (
        "; ".join(recommendation_summary_parts)
        if recommendation_summary_parts
        else "no production_allowed recommendations"
    )

    action_brief = ActionBrief(
        run_id=run_id,
        startup_id=str(startup_id) if startup_id is not None else None,
        generated_at=_utc_now_str(),
        brief_status=brief_status,
        executive_summary_quantitative=executive_summary,
        recommendation_summary=recommendation_summary,
        top_recommendations=top_records,
        evidence_summary=evidence_summary,
        rag_summary=rag_summary,
        gap_summary=gap_summary,
        scoring_summary=scoring_summary_text,
        risk_summary=risk_summary,
        blockers=blocked_entries,
        next_best_actions=next_best_actions,
        audit_trail=audit_trail,
        quality_gate_snapshot=quality_gate_snapshot,
        calibration_snapshot=calibration_snapshot,
        review_required=review_required,
    )

    brief_metrics = ActionBriefMetrics(
        recommendation_count=recommendation_count,
        production_allowed_recommendation_count=final_recommendation_count,
        blocked_recommendation_count=blocked_recommendation_count,
        average_recommendation_priority_score=round(average_priority_score, 4),
        average_recommendation_confidence=round(average_confidence, 4),
        recommendation_uncertainty_mean=round(uncertainty_mean, 4),
        covered_gap_count=covered_gap_count,
        total_gap_count=total_gap_count,
        accepted_evidence_count=accepted_evidence_count,
        supporting_rag_context_count=rag_context_count,
        rag_supported_recommendation_rate=round(rag_supported_rate, 4),
        evidence_supported_recommendation_rate=round(evidence_supported_rate, 4),
        unsupported_critical_claims_count=unsupported_critical_claims_count,
        blocker_count=len(blockers),
        calibration_decision_count=len(calibration_decision_ids),
        missing_calibration_count=missing_calibration_count,
    )

    return {
        "action_brief": action_brief.model_dump(mode="json"),
        "brief_metrics": brief_metrics.model_dump(mode="json"),
        "brief_status": brief_status.value,
        "status": updates_status,
        "review_required": review_required,
        "blockers": blockers,
        "startup_brief": "",
    }

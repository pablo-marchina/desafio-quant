from __future__ import annotations

from typing import Any

from src.orchestration.state import ProductWorkflowState


def workflow_state_to_output_snapshot(state: ProductWorkflowState) -> dict[str, Any]:
    profile = state.startup_profile or {}
    evidence_score = state.evidence_weighted_scores or state.scores or {}
    mapping_result = state.node_outputs.get("nvidia_mapping_result", {})
    recommendation_result = state.node_outputs.get("nvidia_recommendation_result", {})
    ranked = state.ranked_recommendations or []
    structured_recommendations = (
        recommendation_result.get("nvidia_recommendations", [])
        if isinstance(recommendation_result, dict)
        else []
    )
    top_ranked = ranked[0] if ranked else {}
    final_priority_score = _as_float(
        top_ranked.get("expected_utility"),
        _as_float(evidence_score.get("score"), _as_float(state.scores.get("probabilistic_score"), 0.0)),
    )
    return {
        "workflow_id": state.workflow_id,
        "startup_id": state.startup_id,
        "startup_name": profile.get("startup_name") or profile.get("name") or state.metadata_json.get("startup_name", ""),
        "recommended_motion": _recommended_motion(final_priority_score, _as_float(evidence_score.get("uncertainty"), 1.0)),
        "final_priority_score": round(final_priority_score, 4),
        "confidence": evidence_score.get("confidence", state.scores.get("confidence", 0.0)),
        "uncertainty": evidence_score.get("uncertainty", state.scores.get("uncertainty", 1.0)),
        "classification_result": state.classification_result,
        "scores": state.scores,
        "evidence_weighted_scores": state.evidence_weighted_scores,
        "validated_evidence": state.node_outputs.get("validated_evidence", []),
        "evidence_items": state.evidence_items,
        "gap_diagnosis": state.node_outputs.get("gap_output", {}),
        "nvidia_contexts": state.nvidia_contexts,
        "nvidia_mappings": state.nvidia_mappings,
        "nvidia_mapping_metrics": mapping_result.get("nvidia_mapping_metrics", {})
        if isinstance(mapping_result, dict)
        else {},
        "mapping_status": mapping_result.get("mapping_status", "") if isinstance(mapping_result, dict) else "",
        "recommendations": state.recommendations,
        "nvidia_recommendations": structured_recommendations,
        "nvidia_recommendation_metrics": recommendation_result.get("nvidia_recommendation_metrics", {})
        if isinstance(recommendation_result, dict)
        else {},
        "ranking_status": recommendation_result.get("ranking_status", "")
        if isinstance(recommendation_result, dict)
        else "",
        "ranked_recommendations": ranked,
        "technique_results": state.technique_results,
        "decision_ledger_path": state.decision_ledger_path,
        "feedback_adjustments": state.feedback_adjustments,
        "quality_gates_result": state.quality_gates_result,
        "review_required": state.review_required,
        "review_decision": state.review_decision,
        "completed_nodes": state.completed_nodes,
        "degraded_nodes": state.degraded_nodes,
        "failed_nodes": state.failed_nodes,
        "error_message": state.error_message,
    }


def _recommended_motion(score: float, uncertainty: float) -> str:
    if uncertainty >= 0.65:
        return "lack_evidence_more_research"
    if score >= 0.75:
        return "immediate_outreach"
    if score >= 0.55:
        return "high_priority_outreach"
    if score >= 0.35:
        return "monitor_and_nurture"
    return "not_recommended"


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return default
    return default

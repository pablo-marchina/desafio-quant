from __future__ import annotations

from src.orchestration.node_impl import (
    _gap_results_for_mapping,
    _gap_type_for_runtime_gap,
    _rag_contexts_by_gap,
)
from src.orchestration.state import ProductWorkflowState


def _gap(gap_id: str, gap_type: str, *, production_allowed: bool) -> dict:
    return {
        "gap_id": gap_id,
        "gap_type": gap_type,
        "severity_score": 0.5,
        "confidence_score": 0.6,
        "uncertainty": 0.2,
        "status": "needs_review",
        "features": {
            "severity": {
                "missing_required_signal_count": 0.0,
                "weak_evidence_count": 0.0,
                "rejected_evidence_count": 0.0,
                "unsupported_claim_count": 0.0,
                "low_confidence_evidence_count": 0.0,
                "relevant_signal_absence": 0.0,
                "nvidia_fit_opportunity_signal_count": 0.5,
                "implementation_complexity_proxy": 0.5,
                "business_impact_proxy": 0.5,
                "uncertainty_penalty": 0.2,
            },
            "confidence": {
                "supporting_evidence_count": 0.5,
                "supporting_source_count": 0.5,
                "average_evidence_confidence": 0.6,
                "average_source_quality": 0.6,
                "cross_source_agreement_count": 0.5,
                "contradiction_count": 0.0,
                "extraction_success_rate": 1.0,
                "source_category_coverage": 0.5,
            },
        },
        "weights": {},
        "thresholds": {},
        "supporting_evidence_ids": ["evidence-1"],
        "production_allowed": production_allowed,
        "explanation": "test",
        "blockers": [],
        "calibration_decision_ids": [
            "gap_diagnosis.severity_weights",
            "gap_diagnosis.confidence_weights",
            "gap_diagnosis.production_threshold",
            "gap_diagnosis.uncertainty_penalty",
            "gap_diagnosis.minimum_evidence_coverage",
        ],
    }


def test_runtime_gap_id_preserves_semantic_gap_type() -> None:
    assert _gap_type_for_runtime_gap("gap-3-mlops_deployment_gap") == "mlops_deployment_gap"
    assert _gap_type_for_runtime_gap("gap-6-computer_vision_gap") == "computer_vision_gap"


def test_rag_context_is_grouped_by_runtime_id_and_semantic_type() -> None:
    context = {
        "context_id": "ctx-1",
        "gap_types": ["gap-3-mlops_deployment_gap"],
        "product": "NVIDIA AI Enterprise",
        "content": "MLOps deployment guidance",
    }
    grouped = _rag_contexts_by_gap([context], ["gap-3-mlops_deployment_gap"])
    assert grouped["gap-3-mlops_deployment_gap"] == [context]
    assert grouped["mlops_deployment_gap"] == [context]


def test_mapping_receives_only_selected_runtime_gaps() -> None:
    selected_id = "gap-3-mlops_deployment_gap"
    state = ProductWorkflowState(
        workflow_id="workflow-test",
        gap_ids=[selected_id],
        node_outputs={
            "gap_output": {
                "gaps": [
                    _gap(selected_id, "mlops_deployment_gap", production_allowed=True),
                    _gap("gap-6-computer_vision_gap", "computer_vision_gap", production_allowed=False),
                ]
            }
        },
    )
    gaps = _gap_results_for_mapping(state)
    assert [gap.gap_id for gap in gaps] == [selected_id]

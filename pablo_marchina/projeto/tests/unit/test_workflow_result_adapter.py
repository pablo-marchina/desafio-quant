from __future__ import annotations

from src.orchestration.result_adapter import workflow_state_to_output_snapshot
from src.orchestration.state import ProductWorkflowState


def test_workflow_state_to_output_snapshot_publishes_product_fields() -> None:
    state = ProductWorkflowState(
        workflow_id="wf-1",
        startup_id="startup-1",
        startup_profile={"startup_name": "Radar AI"},
        evidence_weighted_scores={"score": 0.81, "confidence": 0.77, "uncertainty": 0.12},
        ranked_recommendations=[
            {"technology": "NVIDIA NIM", "expected_utility": 0.76, "expected_utility_rank": 1}
        ],
        node_outputs={
            "nvidia_recommendation_result": {
                "ranking_status": "passed",
                "nvidia_recommendations": [
                    {
                        "nvidia_technology": "NVIDIA NIM",
                        "supporting_rag_context_ids": ["rag-1"],
                    }
                ],
                "nvidia_recommendation_metrics": {"rag_supported_recommendation_rate": 1.0},
            }
        },
        decision_ledger_path="data/decision_ledger.csv",
        technique_results=[{"technique": "multi_query", "success": True}],
        completed_nodes=["score_startup_probabilistic", "rank_with_expected_utility"],
    )

    snapshot = workflow_state_to_output_snapshot(state)

    assert snapshot["startup_name"] == "Radar AI"
    assert snapshot["recommended_motion"] == "immediate_outreach"
    assert snapshot["final_priority_score"] == 0.76
    assert snapshot["decision_ledger_path"] == "data/decision_ledger.csv"
    assert snapshot["technique_results"][0]["technique"] == "multi_query"
    assert snapshot["ranking_status"] == "passed"
    assert snapshot["nvidia_recommendations"][0]["supporting_rag_context_ids"] == ["rag-1"]


def test_workflow_state_to_output_snapshot_requires_more_evidence_when_uncertain() -> None:
    state = ProductWorkflowState(
        workflow_id="wf-2",
        startup_profile={"startup_name": "Sparse AI"},
        evidence_weighted_scores={"score": 0.9, "confidence": 0.2, "uncertainty": 0.8},
    )

    snapshot = workflow_state_to_output_snapshot(state)

    assert snapshot["recommended_motion"] == "lack_evidence_more_research"

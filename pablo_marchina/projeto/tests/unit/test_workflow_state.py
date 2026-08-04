from __future__ import annotations

from src.orchestration.state import NodeStatus, ProductWorkflowState, WorkflowStatus


def test_workflow_status_constants() -> None:
    assert WorkflowStatus.QUEUED == "queued"
    assert WorkflowStatus.RUNNING == "running"
    assert WorkflowStatus.COMPLETED == "completed"
    assert WorkflowStatus.DEGRADED == "degraded"
    assert WorkflowStatus.FAILED == "failed"
    assert WorkflowStatus.CANCELLED == "cancelled"


def test_node_status_constants() -> None:
    assert NodeStatus.PENDING == "pending"
    assert NodeStatus.RUNNING == "running"
    assert NodeStatus.COMPLETED == "completed"
    assert NodeStatus.SKIPPED == "skipped"
    assert NodeStatus.DEGRADED == "degraded"
    assert NodeStatus.FAILED == "failed"


def test_product_workflow_state_defaults() -> None:
    state = ProductWorkflowState(workflow_id="wf-1", current_node="start")
    assert state.workflow_id == "wf-1"
    assert state.current_node == "start"
    assert state.startup_id is None
    assert state.completed_nodes == []
    assert state.failed_nodes == []
    assert state.degraded_nodes == []
    assert state.node_outputs == {}
    assert state.evidence_ids == []
    assert state.claim_ids == []
    assert state.error_message is None
    assert state.metadata_json == {}


def test_product_workflow_state_full() -> None:
    state = ProductWorkflowState(
        workflow_id="wf-2",
        startup_id="startup-1",
        discovery_candidate_id="candidate-1",
        analysis_run_id="run-1",
        current_node="diagnose_gaps",
        completed_nodes=["load", "collect"],
        failed_nodes=[],
        degraded_nodes=["rag"],
        node_outputs={"rag": {"status": "skipped"}},
        evidence_ids=["ev-1"],
        claim_ids=["cl-1"],
        score_ids=["sc-1"],
        gap_ids=["gp-1"],
        mapping_ids=["mp-1"],
        activation_recommendation_ids=["ar-1"],
        dossier_id="dos-1",
        quality_run_id="qr-1",
        readiness_check_ids=["rc-1"],
        error_message=None,
        metadata_json={"rag_available": False},
    )
    assert state.workflow_id == "wf-2"
    assert state.dossier_id == "dos-1"
    assert state.metadata_json == {"rag_available": False}


def test_product_workflow_state_serialization() -> None:
    state = ProductWorkflowState(
        workflow_id="wf-3",
        startup_id="s-1",
        current_node="validate_evidence",
        completed_nodes=["load"],
    )
    data = state.model_dump(mode="json")
    assert data["workflow_id"] == "wf-3"
    assert data["startup_id"] == "s-1"
    assert data["current_node"] == "validate_evidence"
    assert data["completed_nodes"] == ["load"]

    restored = ProductWorkflowState(**data)
    assert restored.workflow_id == "wf-3"
    assert restored.startup_id == "s-1"
    assert restored.completed_nodes == ["load"]

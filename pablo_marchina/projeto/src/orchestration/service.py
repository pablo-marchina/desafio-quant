from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.orchestration.runner import WorkflowRunner, _has_langgraph
from src.orchestration.state import ProductWorkflowState, WorkflowStatus
from src.repositories.workflow import WorkflowRepository


class WorkflowOrchestrationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = WorkflowRepository(session)

    def enqueue_workflow(
        self,
        *,
        startup_id: str | None = None,
        discovery_candidate_id: str | None = None,
        analysis_run_id: str | None = None,
        use_rag: bool = True,
        graph_version: str = "1.0",
        initial_status: str = WorkflowStatus.QUEUED,
    ) -> Any:
        if not use_rag:
            raise ValueError("RAG is mandatory for the single product workflow; use_rag=false is not allowed.")
        if not any((startup_id, discovery_candidate_id, analysis_run_id)):
            raise ValueError("A startup_id, discovery_candidate_id, or analysis_run_id is required.")
        if initial_status not in {WorkflowStatus.QUEUED, WorkflowStatus.RUNNING}:
            raise ValueError("initial_status must be queued or running.")

        workflow_run = self.repo.create_workflow_run(
            startup_id=startup_id,
            discovery_candidate_id=discovery_candidate_id,
            analysis_run_id=analysis_run_id,
            graph_version=graph_version,
            state_json={},
        )
        state = ProductWorkflowState(
            workflow_id=workflow_run.id,
            startup_id=startup_id,
            discovery_candidate_id=discovery_candidate_id,
            analysis_run_id=analysis_run_id,
            status=initial_status,
            metadata_json={
                "_rag_available": True,
                "_langgraph_available": _has_langgraph(),
            },
        )
        workflow_run.status = initial_status
        if initial_status == WorkflowStatus.RUNNING:
            workflow_run.started_at = datetime.now(UTC)
        workflow_run.state_json = state.model_dump(mode="json")
        self.session.commit()
        return workflow_run

    def run_existing_workflow(self, workflow_id: str) -> ProductWorkflowState:
        run = self.repo.get_workflow_run(workflow_id)
        if run is None:
            raise LookupError(f"Workflow run not found: {workflow_id}")
        if run.status in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.DEGRADED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }:
            raise RuntimeError(f"Workflow {workflow_id} is already terminal with status={run.status}")

        state_data = dict(run.state_json or {})
        state_data.update(
            {
                "workflow_id": run.id,
                "startup_id": run.startup_id,
                "discovery_candidate_id": run.discovery_candidate_id,
                "analysis_run_id": run.analysis_run_id,
                "status": run.status,
                "current_node": run.current_node or state_data.get("current_node", ""),
            }
        )
        metadata = dict(state_data.get("metadata_json") or {})
        metadata.update(
            {
                "_rag_available": True,
                "_langgraph_available": _has_langgraph(),
            }
        )
        state_data["metadata_json"] = metadata
        state = ProductWorkflowState(**state_data)

        runner = WorkflowRunner(self.session)
        final_state = runner.run_workflow(state)
        if final_state.analysis_run_id:
            self.repo.attach_analysis_run(workflow_id, final_state.analysis_run_id)
        self.session.commit()
        return final_state

    def create_and_run_workflow(
        self,
        *,
        startup_id: str | None = None,
        discovery_candidate_id: str | None = None,
        analysis_run_id: str | None = None,
        use_rag: bool = True,
        graph_version: str = "1.0",
    ) -> ProductWorkflowState:
        run = self.enqueue_workflow(
            startup_id=startup_id,
            discovery_candidate_id=discovery_candidate_id,
            analysis_run_id=analysis_run_id,
            use_rag=use_rag,
            graph_version=graph_version,
            initial_status=WorkflowStatus.RUNNING,
        )
        return self.run_existing_workflow(run.id)

    def get_workflow_state(self, workflow_id: str) -> ProductWorkflowState | None:
        run = self.repo.get_workflow_run(workflow_id)
        if run is None:
            return None
        state_data = dict(run.state_json or {})
        state_data["workflow_id"] = run.id
        state_data["startup_id"] = run.startup_id
        state_data["discovery_candidate_id"] = run.discovery_candidate_id
        state_data["analysis_run_id"] = run.analysis_run_id
        state_data["status"] = run.status
        state_data["current_node"] = run.current_node
        return ProductWorkflowState(**state_data)

    def list_workflows(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        startup_id: str | None = None,
    ) -> list[dict[str, Any]]:
        runs = self.repo.list_workflow_runs(
            offset=offset,
            limit=limit,
            status=status,
            startup_id=startup_id,
        )
        return [
            {
                "id": r.id,
                "startup_id": r.startup_id,
                "discovery_candidate_id": r.discovery_candidate_id,
                "analysis_run_id": r.analysis_run_id,
                "status": r.status,
                "current_node": r.current_node,
                "graph_version": r.graph_version,
                "error_message": r.error_message,
                "degraded_reason": r.degraded_reason,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in runs
        ]

    def get_review_payload(self, workflow_id: str) -> dict[str, Any] | None:
        run = self.repo.get_workflow_run(workflow_id)
        if run is None:
            return None
        state: dict[str, Any] = run.state_json or {}
        return state.get("review_payload")

    def submit_review(
        self,
        workflow_id: str,
        *,
        decision: str,
        reviewer: str,
        notes: str,
        resume: bool = False,
    ) -> dict[str, Any]:
        run = self.repo.get_workflow_run(workflow_id)
        if run is None:
            raise LookupError(f"Workflow run not found: {workflow_id}")

        state_data: dict[str, Any] = dict(run.state_json or {})
        now = datetime.now(UTC).isoformat()
        state_data.update(
            {
                "review_decision": decision,
                "reviewer": reviewer,
                "reviewed_by": reviewer,
                "review_notes": notes,
                "reviewed_at": now,
                "review_required": False,
            }
        )
        run.state_json = state_data
        self.session.flush()

        if not resume:
            self.session.commit()
            return {
                "workflow_id": workflow_id,
                "decision": decision,
                "reviewer": reviewer,
                "notes": notes,
                "created_at": now,
            }

        state_data["workflow_id"] = run.id
        state_data["startup_id"] = run.startup_id
        state_data["current_node"] = run.current_node
        workflow_state = ProductWorkflowState(**state_data)

        runner = WorkflowRunner(self.session)
        final_state = runner.resume_workflow(
            workflow_state,
            decision=decision,
            notes=notes,
            reviewed_by=reviewer,
        )
        if final_state.analysis_run_id:
            self.repo.attach_analysis_run(workflow_id, final_state.analysis_run_id)
        self.session.commit()

        return {
            "workflow_id": workflow_id,
            "decision": decision,
            "reviewer": reviewer,
            "notes": notes,
            "created_at": now,
        }

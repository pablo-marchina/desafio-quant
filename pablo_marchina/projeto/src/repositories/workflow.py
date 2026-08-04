from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import WorkflowNodeRun, WorkflowRun
from src.orchestration.state import WorkflowStatus


class WorkflowRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_workflow_run(
        self,
        *,
        startup_id: str | None = None,
        discovery_candidate_id: str | None = None,
        analysis_run_id: str | None = None,
        state_json: dict[str, Any] | None = None,
        graph_version: str = "1.0",
    ) -> WorkflowRun:
        run = WorkflowRun(
            startup_id=startup_id,
            discovery_candidate_id=discovery_candidate_id,
            analysis_run_id=analysis_run_id,
            status=WorkflowStatus.QUEUED,
            current_node="",
            graph_version=graph_version,
            state_json=state_json or {},
        )
        self.session.add(run)
        self.session.flush()
        return run

    def get_workflow_run(self, workflow_id: str) -> WorkflowRun | None:
        stmt = select(WorkflowRun).where(WorkflowRun.id == workflow_id)
        return self.session.scalar(stmt)

    def attach_analysis_run(self, workflow_id: str, analysis_run_id: str) -> WorkflowRun | None:
        run = self.get_workflow_run(workflow_id)
        if run is None:
            return None
        run.analysis_run_id = analysis_run_id
        state = dict(run.state_json or {})
        state["analysis_run_id"] = analysis_run_id
        run.state_json = state
        self.session.flush()
        return run

    def list_workflow_runs(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        startup_id: str | None = None,
    ) -> list[WorkflowRun]:
        stmt = select(WorkflowRun).order_by(WorkflowRun.created_at.desc())
        if status:
            stmt = stmt.where(WorkflowRun.status == status)
        if startup_id:
            stmt = stmt.where(WorkflowRun.startup_id == startup_id)
        return list(self.session.scalars(stmt.offset(offset).limit(limit)))

    def claim_next_queued_workflow(self) -> WorkflowRun | None:
        stmt = (
            select(WorkflowRun)
            .where(WorkflowRun.status == WorkflowStatus.QUEUED)
            .order_by(WorkflowRun.created_at.asc())
            .limit(1)
        )
        bind = self.session.get_bind()
        if bind.dialect.name.startswith("postgresql"):
            stmt = stmt.with_for_update(skip_locked=True)
        run = self.session.scalar(stmt)
        if run is None:
            return None
        run.status = WorkflowStatus.RUNNING
        run.started_at = run.started_at or datetime.now(UTC)
        self.session.flush()
        return run

    def get_workflow_for_analysis_run(self, analysis_run_id: str) -> WorkflowRun | None:
        stmt = select(WorkflowRun).where(WorkflowRun.analysis_run_id == analysis_run_id)
        return self.session.scalar(stmt)

    def update_workflow_status(
        self,
        workflow_id: str,
        *,
        status: str,
        current_node: str | None = None,
        error_message: str | None = None,
        degraded_reason: str | None = None,
        state_json: dict[str, Any] | None = None,
    ) -> WorkflowRun | None:
        run = self.get_workflow_run(workflow_id)
        if run is None:
            return None
        run.status = status
        if current_node is not None:
            run.current_node = current_node
        if error_message is not None:
            run.error_message = error_message
        if degraded_reason is not None:
            run.degraded_reason = degraded_reason
        if state_json is not None:
            run.state_json = state_json
        if status == WorkflowStatus.RUNNING and run.started_at is None:
            run.started_at = datetime.now(UTC)
        if status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.DEGRADED):
            run.completed_at = datetime.now(UTC)
        self.session.flush()
        return run

    def complete_workflow(self, workflow_id: str, *, state_json: dict[str, Any]) -> WorkflowRun | None:
        return self.update_workflow_status(workflow_id, status=WorkflowStatus.COMPLETED, state_json=state_json)

    def fail_workflow(
        self,
        workflow_id: str,
        *,
        error_message: str,
        state_json: dict[str, Any] | None = None,
    ) -> WorkflowRun | None:
        return self.update_workflow_status(
            workflow_id,
            status=WorkflowStatus.FAILED,
            error_message=error_message,
            state_json=state_json,
        )

    def degrade_workflow(
        self,
        workflow_id: str,
        *,
        degraded_reason: str,
        state_json: dict[str, Any] | None = None,
    ) -> WorkflowRun | None:
        return self.update_workflow_status(
            workflow_id,
            status=WorkflowStatus.DEGRADED,
            degraded_reason=degraded_reason,
            state_json=state_json,
        )

    def create_node_run(
        self,
        *,
        workflow_run_id: str,
        node_name: str,
        input_snapshot: dict[str, Any] | None = None,
    ) -> WorkflowNodeRun:
        node_run = WorkflowNodeRun(
            workflow_run_id=workflow_run_id,
            node_name=node_name,
            status="pending",
            input_snapshot_json=input_snapshot or {},
        )
        self.session.add(node_run)
        self.session.flush()
        return node_run

    def get_node_run(self, node_run_id: str) -> WorkflowNodeRun | None:
        stmt = select(WorkflowNodeRun).where(WorkflowNodeRun.id == node_run_id)
        return self.session.scalar(stmt)

    def list_node_runs(
        self,
        workflow_run_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[WorkflowNodeRun]:
        stmt = (
            select(WorkflowNodeRun)
            .where(WorkflowNodeRun.workflow_run_id == workflow_run_id)
            .order_by(WorkflowNodeRun.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def update_node_run_status(
        self,
        node_run_id: str,
        *,
        status: str,
        output_snapshot: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> WorkflowNodeRun | None:
        node_run = self.get_node_run(node_run_id)
        if node_run is None:
            return None
        node_run.status = status
        if output_snapshot is not None:
            node_run.output_snapshot_json = output_snapshot
        if error_message is not None:
            node_run.error_message = error_message
        if status in ("running", "completed", "failed", "degraded") and node_run.started_at is None:
            node_run.started_at = datetime.now(UTC)
        terminal_statuses = ("completed", "failed", "degraded", "skipped")
        if status in terminal_statuses:
            node_run.completed_at = datetime.now(UTC)
            # A failed workflow is rolled back before its failure state is recorded.
            # Node outputs are audit evidence and must survive that rollback, so a
            # terminal node transition defines its own durable transaction boundary.
            self.session.commit()
        else:
            self.session.flush()
        return node_run

    def increment_node_retry(self, node_run_id: str) -> WorkflowNodeRun | None:
        node_run = self.get_node_run(node_run_id)
        if node_run is None:
            return None
        node_run.retry_count += 1
        node_run.status = "pending"
        node_run.error_message = None
        self.session.flush()
        return node_run

    def update_node_run_metadata(
        self,
        node_run_id: str,
        *,
        metadata: dict[str, Any],
    ) -> WorkflowNodeRun | None:
        node_run = self.get_node_run(node_run_id)
        if node_run is None:
            return None
        node_run.metadata_json = metadata
        self.session.flush()
        return node_run

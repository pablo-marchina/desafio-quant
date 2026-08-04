from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.database.models import WorkflowRun
from src.database.session import configure_product_database, reset_product_database_runtime
from src.orchestration.runner import WorkflowRunner
from src.orchestration.state import ProductWorkflowState, WorkflowStatus
from src.repositories.workflow import WorkflowRepository


@pytest.fixture
def session(tmp_path: Path):
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'rollback.db').as_posix()}")
    session = runtime.session_factory()
    yield session
    session.close()
    reset_product_database_runtime()


def test_failed_flush_rolls_back_before_persisting_original_workflow_error(session) -> None:
    repo = WorkflowRepository(session)
    workflow = repo.create_workflow_run(state_json={"transaction_recovery": True})
    session.commit()

    state = ProductWorkflowState(workflow_id=workflow.id)
    graph = MagicMock()

    def fail_inside_graph(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        # Force a real SQLAlchemy flush failure and PendingRollback state.
        session.add(
            WorkflowRun(
                id=workflow.id,
                status=WorkflowStatus.RUNNING,
                current_node="duplicate",
                state_json={},
            )
        )
        session.flush()

    graph.invoke.side_effect = fail_inside_graph
    result = WorkflowRunner(session)._run_with_langgraph(state, graph)
    session.commit()
    session.expire_all()

    persisted = repo.get_workflow_run(workflow.id)
    assert persisted is not None
    assert result.status == WorkflowStatus.FAILED
    assert persisted.status == WorkflowStatus.FAILED
    assert persisted.error_message is not None
    assert "IntegrityError" in persisted.error_message
    assert "PendingRollbackError" not in persisted.error_message

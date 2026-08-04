from __future__ import annotations

from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.orchestration.state import WorkflowStatus
from src.repositories.workflow import WorkflowRepository


@pytest.fixture
def repo(tmp_path: Path) -> WorkflowRepository:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'workflow.db').as_posix()}")
    session = runtime.session_factory()
    yield WorkflowRepository(session)
    session.close()
    reset_product_database_runtime()


def test_create_workflow_run(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1", graph_version="1.0")
    assert run.id is not None
    assert run.startup_id == "s-1"
    assert run.status == WorkflowStatus.QUEUED
    assert run.graph_version == "1.0"
    assert run.current_node == ""


def test_create_workflow_run_with_state(repo: WorkflowRepository) -> None:
    state = {"startup_id": "s-2", "current_node": "load"}
    run = repo.create_workflow_run(
        startup_id="s-2",
        analysis_run_id="ar-1",
        state_json=state,
    )
    assert run.analysis_run_id == "ar-1"
    assert run.state_json == state


def test_get_workflow_run(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1")
    repo.session.commit()

    got = repo.get_workflow_run(run.id)
    assert got is not None
    assert got.id == run.id
    assert got.status == WorkflowStatus.QUEUED

    missing = repo.get_workflow_run("nonexistent")
    assert missing is None


def test_list_workflow_runs(repo: WorkflowRepository) -> None:
    repo.create_workflow_run(startup_id="s-1")
    repo.create_workflow_run(startup_id="s-2")
    repo.session.commit()

    all_runs = repo.list_workflow_runs()
    assert len(all_runs) >= 2

    filtered = repo.list_workflow_runs(status=WorkflowStatus.QUEUED)
    assert len(filtered) >= 2


def test_workflow_status_transitions(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1")
    repo.session.commit()

    repo.update_workflow_status(run.id, status=WorkflowStatus.RUNNING, current_node="load")
    repo.session.commit()
    run = repo.get_workflow_run(run.id)
    assert run is not None
    assert run.status == WorkflowStatus.RUNNING
    assert run.current_node == "load"
    assert run.started_at is not None

    repo.complete_workflow(run.id, state_json={"completed": True})
    repo.session.commit()
    run = repo.get_workflow_run(run.id)
    assert run is not None
    assert run.status == WorkflowStatus.COMPLETED
    assert run.completed_at is not None


def test_fail_workflow(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1")
    repo.session.commit()
    repo.fail_workflow(run.id, error_message="Critical node failed")
    repo.session.commit()
    run = repo.get_workflow_run(run.id)
    assert run is not None
    assert run.status == WorkflowStatus.FAILED
    assert run.error_message == "Critical node failed"


def test_degrade_workflow(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1")
    repo.session.commit()
    repo.degrade_workflow(run.id, degraded_reason="RAG unavailable")
    repo.session.commit()
    run = repo.get_workflow_run(run.id)
    assert run is not None
    assert run.status == WorkflowStatus.DEGRADED
    assert run.degraded_reason == "RAG unavailable"


def test_get_workflow_for_analysis_run(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1", analysis_run_id="ar-1")
    repo.session.commit()
    found = repo.get_workflow_for_analysis_run("ar-1")
    assert found is not None
    assert found.id == run.id

    missing = repo.get_workflow_for_analysis_run("nonexistent")
    assert missing is None


def test_create_node_run(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1")
    repo.session.commit()
    node_run = repo.create_node_run(
        workflow_run_id=run.id,
        node_name="load_startup_or_candidate",
        input_snapshot={"startup_id": "s-1"},
    )
    assert node_run.id is not None
    assert node_run.node_name == "load_startup_or_candidate"
    assert node_run.status == "pending"
    assert node_run.input_snapshot_json == {"startup_id": "s-1"}


def test_update_node_run_status(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1")
    repo.session.commit()
    node_run = repo.create_node_run(workflow_run_id=run.id, node_name="test")
    repo.session.commit()

    repo.update_node_run_status(node_run.id, status="completed", output_snapshot={"result": "ok"})
    repo.session.commit()
    updated = repo.get_node_run(node_run.id)
    assert updated is not None
    assert updated.status == "completed"
    assert updated.output_snapshot_json == {"result": "ok"}
    assert updated.completed_at is not None


def test_increment_retry(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1")
    repo.session.commit()
    node_run = repo.create_node_run(workflow_run_id=run.id, node_name="test")
    repo.session.commit()

    repo.increment_node_retry(node_run.id)
    repo.session.commit()
    updated = repo.get_node_run(node_run.id)
    assert updated is not None
    assert updated.retry_count == 1
    assert updated.status == "pending"


def test_list_node_runs(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1")
    repo.session.commit()
    repo.create_node_run(workflow_run_id=run.id, node_name="node1")
    repo.create_node_run(workflow_run_id=run.id, node_name="node2")
    repo.session.commit()

    node_runs = repo.list_node_runs(run.id)
    assert len(node_runs) == 2


def test_no_demo_runs_dependency(repo: WorkflowRepository) -> None:
    run = repo.create_workflow_run(startup_id="s-1")
    repo.session.commit()
    assert run.state_json.get("demo_data") is None

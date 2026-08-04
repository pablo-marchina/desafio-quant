from __future__ import annotations

from pathlib import Path

from src.database.session import (
    configure_product_database,
    get_db_session,
    reset_product_database_runtime,
)
from src.repositories.workflow import WorkflowRepository


def test_terminal_node_snapshot_survives_later_session_rollback(
    tmp_path: Path,
    monkeypatch,  # noqa: ANN001
) -> None:
    monkeypatch.setenv("APP_MODE", "test")
    database_url = f"sqlite:///{(tmp_path / 'node-durability.db').as_posix()}"
    configure_product_database(database_url)

    session = next(get_db_session())
    try:
        repo = WorkflowRepository(session)
        workflow = repo.create_workflow_run(state_json={"status": "initialized"})
        session.commit()
        workflow_id = workflow.id

        node = repo.create_node_run(
            workflow_run_id=workflow_id,
            node_name="map_nvidia_technologies",
            input_snapshot={"startup_id": "startup-test"},
        )
        repo.update_node_run_status(node.id, status="running")
        repo.update_node_run_status(
            node.id,
            status="completed",
            output_snapshot={
                "node_outputs": {
                    "mapping_output": {
                        "mapping_status": "needs_more_evidence",
                        "nvidia_mapping_metrics": {"total_mapping_count": 4},
                    }
                }
            },
        )

        # Simulate the workflow runner rolling back after a downstream
        # fail-closed exception. The terminal audit record must remain.
        session.rollback()
    finally:
        session.close()

    verification_session = next(get_db_session())
    try:
        persisted = WorkflowRepository(verification_session).list_node_runs(workflow_id)
        assert len(persisted) == 1
        assert persisted[0].status == "completed"
        mapping_output = persisted[0].output_snapshot_json["node_outputs"]["mapping_output"]
        assert mapping_output["mapping_status"] == "needs_more_evidence"
        assert mapping_output["nvidia_mapping_metrics"]["total_mapping_count"] == 4
    finally:
        verification_session.close()
        reset_product_database_runtime()

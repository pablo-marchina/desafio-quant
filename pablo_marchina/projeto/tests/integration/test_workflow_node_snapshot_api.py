from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.models import WorkflowNodeRun, WorkflowRun
from src.database.session import (
    configure_product_database,
    get_db_session,
    reset_product_database_runtime,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("ENABLE_PRODUCT_PERSISTENCE", "true")
    database_url = f"sqlite:///{(tmp_path / 'workflow-snapshots.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", database_url)
    configure_product_database(database_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


def test_node_snapshot_endpoint_exposes_failed_node_state(client: TestClient) -> None:
    session = next(get_db_session())
    try:
        workflow = WorkflowRun(
            status="failed",
            current_node="map_nvidia_technologies",
            graph_version="1.0",
            state_json={},
            error_message="NVIDIA mapping status: needs_more_evidence",
        )
        session.add(workflow)
        session.flush()
        node = WorkflowNodeRun(
            workflow_run_id=workflow.id,
            node_name="map_nvidia_technologies",
            status="failed",
            input_snapshot_json={"startup_id": "startup-test"},
            output_snapshot_json={
                "node_outputs": {
                    "mapping_output": {
                        "mapping_status": "needs_more_evidence",
                        "nvidia_mapping_metrics": {
                            "total_mapping_count": 3,
                            "production_allowed_mapping_count": 1,
                        },
                    }
                }
            },
            metadata_json={"attempt": 1},
            error_message="NVIDIA mapping status: needs_more_evidence",
        )
        session.add(node)
        session.commit()
        workflow_id = workflow.id
    finally:
        session.close()

    response = client.get(f"/workflows/product-runs/{workflow_id}/node-snapshots")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    persisted = payload[0]
    assert persisted["node_name"] == "map_nvidia_technologies"
    assert persisted["status"] == "failed"
    assert persisted["input_snapshot"] == {"startup_id": "startup-test"}
    mapping_output = persisted["output_snapshot"]["node_outputs"]["mapping_output"]
    assert mapping_output["mapping_status"] == "needs_more_evidence"
    assert mapping_output["nvidia_mapping_metrics"]["production_allowed_mapping_count"] == 1
    assert persisted["metadata"] == {"attempt": 1}

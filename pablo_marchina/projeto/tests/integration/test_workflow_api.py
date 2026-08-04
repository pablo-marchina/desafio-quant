from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.models import WorkflowRun
from src.database.session import (
    configure_product_database,
    get_db_session,
    reset_product_database_runtime,
)
from src.orchestration.state import WorkflowStatus


@pytest.fixture(autouse=True)
def _mock_product_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services.product.readiness_service import ProductReadinessReport, ProductReadinessService

    def ready_report(self: ProductReadinessService) -> ProductReadinessReport:
        return ProductReadinessReport(ready=True)

    monkeypatch.setattr(ProductReadinessService, "get_product_readiness", ready_report)
    monkeypatch.setattr("src.orchestration.runner.build_workflow_graph", lambda **_: None)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("ENABLE_PRODUCT_PERSISTENCE", "true")
    monkeypatch.setenv("QDRANT_URL", "")
    monkeypatch.delenv("RAG_VECTOR_BACKEND", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
    db_url = f"sqlite:///{(tmp_path / 'workflow_api.db').as_posix()}"
    monkeypatch.setenv("PRODUCT_DB_URL", db_url)
    configure_product_database(db_url)
    with TestClient(app) as test_client:
        yield test_client
    reset_product_database_runtime()


@pytest.fixture
def startup_id(client: TestClient) -> str:
    resp = client.post(
        "/startups",
        json={
            "name": "Workflow Startup",
            "website": "https://workflow.example.com",
            "sector": "AI",
            "description": "Workflow test startup",
            "product_summary": "AI product testing",
            "tags": ["ai-native", "testing"],
            "evidence": [
                {
                    "claim": "Uses AI in production",
                    "source_url": "https://workflow.example.com/tech",
                    "source_type": "official_site",
                    "quote_or_evidence": "Uses AI inference in production.",
                    "confidence": "high",
                }
            ],
        },
    )
    assert resp.status_code == 201, f"Create startup failed: {resp.text}"
    return resp.json()["id"]


def test_create_product_workflow_run(client: TestClient, startup_id: str) -> None:
    resp = client.post(
        "/workflows/product-runs",
        json={
            "startup_id": startup_id,
        },
    )
    assert resp.status_code == 201, f"Create workflow failed: {resp.text}"
    data = resp.json()
    assert data["id"] is not None
    assert data["startup_id"] == startup_id
    assert data["status"] in (
        "queued",
        "running",
        "awaiting_review",
        "completed",
        "degraded",
        "failed",
    )


def test_create_product_workflow_run_without_startup(client: TestClient) -> None:
    resp = client.post(
        "/workflows/product-runs",
        json={
            "startup_id": "nonexistent",
        },
    )
    assert resp.status_code == 201, f"Create workflow failed: {resp.text}"
    assert resp.json()["startup_id"] == "nonexistent"


def test_get_product_workflow_run(client: TestClient, startup_id: str) -> None:
    create_resp = client.post("/workflows/product-runs", json={"startup_id": startup_id})
    assert create_resp.status_code == 201
    run_id = create_resp.json()["id"]

    resp = client.get(f"/workflows/product-runs/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run_id
    assert data["startup_id"] == startup_id


def test_get_product_workflow_run_not_found(client: TestClient) -> None:
    resp = client.get("/workflows/product-runs/nonexistent")
    assert resp.status_code == 404


def test_list_product_workflow_runs(client: TestClient, startup_id: str) -> None:
    client.post("/workflows/product-runs", json={"startup_id": startup_id})
    client.post("/workflows/product-runs", json={"startup_id": startup_id})

    resp = client.get("/workflows/product-runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


def test_list_product_workflow_runs_filter_by_status(client: TestClient, startup_id: str) -> None:
    client.post("/workflows/product-runs", json={"startup_id": startup_id})

    resp = client.get("/workflows/product-runs?status=queued")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 0


def test_get_workflow_nodes(client: TestClient, startup_id: str) -> None:
    create_resp = client.post("/workflows/product-runs", json={"startup_id": startup_id})
    assert create_resp.status_code == 201
    run_id = create_resp.json()["id"]

    resp = client.get(f"/workflows/product-runs/{run_id}/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_get_workflow_nodes_not_found(client: TestClient) -> None:
    resp = client.get("/workflows/product-runs/nonexistent/nodes")
    assert resp.status_code == 404


def test_analysis_run_workflow_link(client: TestClient, startup_id: str) -> None:
    resp = client.post("/workflows/product-runs", json={"startup_id": startup_id, "analysis_run_id": "ar-1"})
    assert resp.status_code == 201

    resp = client.get("/analysis-runs/ar-1/workflow")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_run_id"] == "ar-1"


def test_analysis_run_workflow_link_not_found(client: TestClient) -> None:
    resp = client.get("/analysis-runs/nonexistent/workflow")
    assert resp.status_code == 404


def test_langgraph_status_endpoint(client: TestClient) -> None:
    resp = client.get("/workflows/langgraph-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "langgraph_available" in data
    assert isinstance(data["langgraph_available"], bool)


def test_workflow_run_created_at_populated(client: TestClient, startup_id: str) -> None:
    resp = client.post("/workflows/product-runs", json={"startup_id": startup_id})
    assert resp.status_code == 201
    data = resp.json()
    assert data["created_at"] is not None


# ---------------------------------------------------------------------------
# Workflow review-payload and review-submission tests
# ---------------------------------------------------------------------------


_REVIEW_PAYLOAD_DEMO: dict[str, object] = {
    "run_id": "demo-run-id",
    "startup_id": "demo-startup-id",
    "reason": "quality_gate_requested_human_review",
    "severity": "medium",
    "failed_quality_checks": ["brief_generated"],
    "blockers": [],
    "expected_human_actions": ["approve", "reject", "request_more_evidence"],
    "resumable": True,
    "interrupt_enabled": True,
}


def _create_workflow_with_review_payload(client: TestClient) -> str:
    """Create a workflow run whose state_json contains a review_payload."""
    session = next(get_db_session())
    try:
        run = WorkflowRun(
            startup_id="review-startup",
            status=WorkflowStatus.COMPLETED,
            current_node="finish",
            state_json={"review_payload": _REVIEW_PAYLOAD_DEMO},
        )
        session.add(run)
        session.commit()
        return run.id
    finally:
        session.close()


def test_get_review_payload_returns_payload(client: TestClient) -> None:
    workflow_id = _create_workflow_with_review_payload(client)
    resp = client.get(f"/workflows/{workflow_id}/review-payload")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "demo-run-id"
    assert data["severity"] == "medium"
    assert "approve" in data["expected_human_actions"]
    assert data["interrupt_enabled"] is True
    assert data["resumable"] is True


def test_get_review_payload_not_found(client: TestClient) -> None:
    resp = client.get("/workflows/nonexistent/review-payload")
    assert resp.status_code == 404


def test_get_review_payload_no_review_needed(client: TestClient) -> None:
    session = next(get_db_session())
    try:
        run = WorkflowRun(
            startup_id="no-review",
            status=WorkflowStatus.COMPLETED,
            current_node="finish",
            state_json={},
        )
        session.add(run)
        session.commit()
        workflow_id = run.id
    finally:
        session.close()

    resp = client.get(f"/workflows/{workflow_id}/review-payload")
    assert resp.status_code == 404


def test_submit_review_approve(client: TestClient) -> None:
    workflow_id = _create_workflow_with_review_payload(client)
    resp = client.post(
        f"/workflows/{workflow_id}/review",
        json={"decision": "approve", "reviewer": "test-user", "notes": "Looks good"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["workflow_id"] == workflow_id
    assert data["decision"] == "approve"
    assert data["reviewer"] == "test-user"
    assert data["notes"] == "Looks good"
    assert data["created_at"] is not None


def test_submit_review_reject(client: TestClient) -> None:
    workflow_id = _create_workflow_with_review_payload(client)
    resp = client.post(
        f"/workflows/{workflow_id}/review",
        json={"decision": "reject", "reviewer": "manager", "notes": "Missing critical evidence"},
    )
    assert resp.status_code == 201
    assert resp.json()["decision"] == "reject"


def test_submit_review_request_more_evidence(client: TestClient) -> None:
    workflow_id = _create_workflow_with_review_payload(client)
    resp = client.post(
        f"/workflows/{workflow_id}/review",
        json={
            "decision": "request_more_evidence",
            "reviewer": "analyst",
            "notes": "Need more sources",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["decision"] == "request_more_evidence"


def test_submit_review_invalid_decision(client: TestClient) -> None:
    workflow_id = _create_workflow_with_review_payload(client)
    resp = client.post(
        f"/workflows/{workflow_id}/review",
        json={"decision": "invalid", "reviewer": "test", "notes": ""},
    )
    assert resp.status_code == 422


def test_submit_review_workflow_not_found(client: TestClient) -> None:
    resp = client.post(
        "/workflows/nonexistent/review",
        json={"decision": "approve", "reviewer": "test", "notes": ""},
    )
    assert resp.status_code == 404


def test_submit_review_persists_decision(client: TestClient) -> None:
    workflow_id = _create_workflow_with_review_payload(client)
    client.post(
        f"/workflows/{workflow_id}/review",
        json={"decision": "approve", "reviewer": "persist-test", "notes": "Persist check"},
    )
    resp = client.get(f"/workflows/product-runs/{workflow_id}")
    assert resp.status_code == 200
    state = resp.json().get("state", {})
    assert state.get("review_decision") == "approve"
    assert state.get("reviewed_by") == "persist-test"
    assert state.get("review_notes") == "Persist check"
    assert state.get("reviewed_at") is not None


# ---------------------------------------------------------------------------
# POST /workflows/{workflow_id}/resume
# ---------------------------------------------------------------------------


def _create_awaiting_review_workflow(session, startup_id: str, analysis_run_id: str | None = None) -> str:
    import uuid

    thread_id = str(uuid.uuid4())
    wf = WorkflowRun(
        startup_id=startup_id,
        analysis_run_id=analysis_run_id,
        status="awaiting_review",
        current_node="needs_review",
        graph_version="1.0",
        state_json={
            "completed_nodes": [
                "preflight_configuration_check",
                "plan_search",
                "collect_sources",
                "extract_profile",
                "validate_evidence",
                "score_startup_probabilistic",
                "diagnose_gaps",
                "retrieve_nvidia_context",
                "rank_recommendations",
                "generate_brief",
                "run_quality_gates",
            ],
            "failed_nodes": [],
            "degraded_nodes": [],
            "blockers": [],
            "review_required": True,
            "review_payload": {
                "run_id": workflow_id if (workflow_id := str(uuid.uuid4())) else "",
                "reason": "Review required",
                "severity": "medium",
                "expected_human_actions": ["approve", "reject", "request_more_evidence"],
                "resumable": True,
            },
            "metadata_json": {
                "_langgraph_thread_id": thread_id,
            },
        },
    )
    session.add(wf)
    session.flush()
    return wf.id


def _create_startup_record(session) -> str:
    import uuid

    from src.database.models import Startup

    sid = str(uuid.uuid4())
    startup = Startup(
        id=sid,
        name=f"Resume Test Startup {sid[:8]}",
        normalized_name=f"resume-test-startup-{sid[:8]}",
        website=f"https://resume-{sid[:8]}.example.com",
        sector="AI",
        description="Resume test startup",
        product_summary="AI testing",
        tags_json=[],
    )
    session.add(startup)
    session.flush()
    return sid


def test_resume_workflow_not_found_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/workflows/nonexistent/resume",
        json={"decision": "approve", "reviewer": "test", "notes": ""},
    )
    assert resp.status_code == 404


def test_resume_workflow_invalid_decision_returns_422(client: TestClient) -> None:
    session = next(get_db_session())
    try:
        sid = _create_startup_record(session)
        wf_id = _create_awaiting_review_workflow(session, sid)
        session.commit()
    finally:
        session.close()

    resp = client.post(
        f"/workflows/{wf_id}/resume",
        json={"decision": "invalid", "reviewer": "test", "notes": ""},
    )
    assert resp.status_code == 422


def test_resume_workflow_approve_returns_200(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.orchestration.service.WorkflowOrchestrationService.submit_review",
        lambda self, workflow_id, *, decision, reviewer, notes, resume=False: {
            "workflow_id": workflow_id,
            "decision": decision,
            "reviewer": reviewer,
            "notes": notes,
        },
    )
    session = next(get_db_session())
    try:
        sid = _create_startup_record(session)
        wf_id = _create_awaiting_review_workflow(session, sid)
        session.commit()
    finally:
        session.close()

    resp = client.post(
        f"/workflows/{wf_id}/resume",
        json={"decision": "approve", "reviewer": "test-user", "notes": "Approved"},
    )
    assert resp.status_code == 200, f"Resume failed: {resp.text}"
    data = resp.json()
    assert data["id"] == wf_id
    assert data["startup_id"] == sid
    assert data["status"] == "awaiting_review"


def test_resume_workflow_request_more_evidence_returns_200(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.orchestration.service.WorkflowOrchestrationService.submit_review",
        lambda self, workflow_id, *, decision, reviewer, notes, resume=False: {
            "workflow_id": workflow_id,
            "decision": decision,
            "reviewer": reviewer,
            "notes": notes,
        },
    )
    session = next(get_db_session())
    try:
        sid = _create_startup_record(session)
        wf_id = _create_awaiting_review_workflow(session, sid)
        session.commit()
    finally:
        session.close()

    resp = client.post(
        f"/workflows/{wf_id}/resume",
        json={
            "decision": "request_more_evidence",
            "reviewer": "analyst",
            "notes": "Need more sources",
        },
    )
    assert resp.status_code == 200, f"Resume failed: {resp.text}"
    data = resp.json()
    assert data["id"] == wf_id


def test_resume_workflow_persists_review_decision(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.orchestration.service.WorkflowOrchestrationService.submit_review",
        lambda self, workflow_id, *, decision, reviewer, notes, resume=False: {
            "workflow_id": workflow_id,
            "decision": decision,
            "reviewer": reviewer,
            "notes": notes,
        },
    )
    session = next(get_db_session())
    try:
        from src.database.models import AnalysisRun

        sid = _create_startup_record(session)
        ar = AnalysisRun(
            startup_id=sid,
            status="awaiting_review",
            input_snapshot_json={},
            output_snapshot_json={},
            pipeline_version="test",
            config_snapshot_json={},
        )
        session.add(ar)
        session.flush()
        ar_id = ar.id

        wf_id = _create_awaiting_review_workflow(session, sid, analysis_run_id=ar_id)
        session.commit()
    finally:
        session.close()

    resp = client.post(
        f"/workflows/{wf_id}/resume",
        json={"decision": "reject", "reviewer": "auditor", "notes": "Not enough evidence"},
    )
    assert resp.status_code == 200, f"Resume failed: {resp.text}"

    session = next(get_db_session())
    try:
        from src.repositories.review import ReviewDecisionRepository

        repo = ReviewDecisionRepository(session)
        records = repo.list_for_run(ar_id)
        assert len(records) >= 1
        latest = records[0]
        assert latest.decision == "reject"
        assert latest.reviewer == "auditor"
        assert latest.notes == "Not enough evidence"
        assert latest.analysis_run_id == ar_id
        assert latest.startup_id == sid
    finally:
        session.close()

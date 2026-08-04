"""Tests for the product workflow API endpoints (POST /analysis-runs, GET /analysis-runs/{id})."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.models import ActionBriefRecord, AnalysisRun, WorkflowRun
from src.database.session import (
    configure_product_database,
    get_db_session,
    reset_product_database_runtime,
)
from src.orchestration.state import ProductWorkflowState
from src.services.product.readiness_service import ProductReadinessReport

_READY_REPORT = ProductReadinessReport(ready=True)


@pytest.fixture(autouse=True)
def _mock_readiness() -> Iterator[None]:
    with patch(
        "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
        return_value=_READY_REPORT,
    ):
        yield


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_MODE", "test")
    monkeypatch.setenv("ENABLE_PRODUCT_PERSISTENCE", "true")
    monkeypatch.setenv("QDRANT_URL", "")
    db_url = f"sqlite:///{(tmp_path / 'test_product_workflow_api.db').as_posix()}"
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
            "name": "Product Workflow API Startup",
            "website": "https://product-workflow-api.example.com",
            "sector": "AI",
            "description": "Product workflow API test startup",
            "product_summary": "AI-powered analytics",
            "tags": ["ai-native", "testing"],
            "evidence": [
                {
                    "claim": "Uses machine learning models in production",
                    "source_url": "https://product-workflow-api.example.com/tech",
                    "source_type": "official_site",
                    "quote_or_evidence": "Uses ML models for real-time inference.",
                    "confidence": "high",
                },
            ],
        },
    )
    assert resp.status_code == 201, f"Create startup failed: {resp.text}"
    return resp.json()["id"]


POST_RESPONSE_FIELDS = {
    "run_id",
    "startup_id",
    "status",
    "review_required",
    "executed_nodes",
    "blockers",
    "quality",
    "action_brief",
    "evidence_validation",
    "rag_metrics",
    "recommendation_metrics",
    "brief_metrics",
    "review_decision",
    "review_notes",
}
GET_RESPONSE_FIELDS = {
    "run_id",
    "startup_id",
    "status",
    "executed_nodes",
    "blockers",
    "quality",
    "evidence_validation",
    "rag_metrics",
    "recommendation_metrics",
    "brief_metrics",
    "action_brief",
    "dossier_summary",
    "review_required",
    "review_payload",
}


def _create_analysis_run_record(session, startup_id: str) -> str:
    run = AnalysisRun(
        startup_id=startup_id,
        status="completed",
        input_snapshot_json={},
        output_snapshot_json={
            "validated_evidence": {"total": 2, "supported": 2},
            "rag_output": {"contexts_retrieved": 5},
            "recommendation": {"total_recommendations": 3},
            "action_brief": {"version": "2.0"},
        },
        pipeline_version="test",
        config_snapshot_json={},
    )
    session.add(run)
    session.flush()
    return run.id


def _quantitative_action_brief(run_id: str, startup_id: str, *, status: str = "passed") -> dict:
    return {
        "run_id": run_id,
        "startup_id": startup_id,
        "generated_at": "2026-06-19T12:00:00+00:00",
        "brief_status": status,
        "executive_summary_quantitative": {
            "production_allowed_recommendations": 1,
            "average_priority_score": 0.85,
            "average_confidence": 0.72,
            "average_uncertainty": 0.15,
        },
        "recommendation_summary": "NVIDIA NIM(priority=0.85, confidence=0.72, uncertainty=0.15)",
        "top_recommendations": [
            {
                "recommendation_id": "rec-001",
                "nvidia_technology": "NVIDIA NIM",
                "gap_id": "gap-001",
                "gap_type": "external_api_dependency",
                "recommendation_priority_score": 0.85,
                "recommendation_confidence": 0.72,
                "uncertainty": 0.15,
                "mapping_score": 0.8,
                "mapping_confidence": 0.75,
                "business_impact": 0.7,
                "implementation_complexity": 0.3,
                "ai_native_score_value": 0.75,
                "nvidia_fit_score_value": 0.65,
                "gap_severity_score": 0.7,
                "gap_confidence_score": 0.65,
                "supporting_evidence_ids": ["ev-001"],
                "supporting_rag_context_ids": ["rag-001"],
                "supporting_claim_ids": ["claim-001"],
                "calibration_decision_ids": ["recommendation.priority_score_weights"],
                "next_best_action": "Engage startup to discuss NVIDIA NIM",
                "reason_grounded_in_scores": "priority_score=0.85; confidence=0.72",
                "production_allowed": True,
            }
        ],
        "evidence_summary": "evidence_items=2 | accepted=2 | status=passed",
        "rag_summary": "rag_contexts=1 | rag_supported_recommendations=1/1 | status=passed",
        "gap_summary": "total_gaps=1 | covered_by_recommendations=1 | status=passed",
        "scoring_summary": "ai_native_score=0.75 | nvidia_fit_score=0.65 | status=passed",
        "risk_summary": "none",
        "blockers": [],
        "next_best_actions": ["Engage startup to discuss NVIDIA NIM"],
        "audit_trail": {
            "executed_nodes": ["rank_recommendations", "generate_brief"],
            "calibration_decision_ids": ["recommendation.priority_score_weights"],
            "evidence_ids": ["ev-001"],
            "rag_context_ids": ["rag-001"],
            "blockers": [],
            "quality_gate_status": "passed",
        },
        "quality_gate_snapshot": {"status": "passed", "failed_checks": [], "warning_checks": []},
        "calibration_snapshot": {
            "calibration_decision_count": 1,
            "missing_calibration_count": 0,
        },
        "traceback": "must not be exported",
        "internal_token": "secret-value",
    }


def _brief_metrics() -> dict:
    return {
        "recommendation_count": 1,
        "production_allowed_recommendation_count": 1,
        "blocked_recommendation_count": 0,
        "average_recommendation_priority_score": 0.85,
        "average_recommendation_confidence": 0.72,
        "recommendation_uncertainty_mean": 0.15,
        "covered_gap_count": 1,
        "total_gap_count": 1,
        "accepted_evidence_count": 2,
        "supporting_rag_context_count": 1,
        "rag_supported_recommendation_rate": 1.0,
        "evidence_supported_recommendation_rate": 1.0,
        "unsupported_critical_claims_count": 0,
        "blocker_count": 0,
        "calibration_decision_count": 1,
        "missing_calibration_count": 0,
    }


def _create_quantitative_action_brief_record(
    session,
    analysis_run_id: str,
    startup_id: str,
    *,
    status: str = "passed",
    blockers: list[dict] | None = None,
) -> str:
    run = session.get(AnalysisRun, analysis_run_id)
    assert run is not None
    snapshot = dict(run.output_snapshot_json or {})
    snapshot["brief_metrics"] = _brief_metrics()
    run.output_snapshot_json = snapshot
    brief_json = _quantitative_action_brief(analysis_run_id, startup_id, status=status)
    if blockers is not None:
        brief_json["blockers"] = blockers
        brief_json["audit_trail"]["blockers"] = [b["description"] for b in blockers]
    brief = ActionBriefRecord(
        analysis_run_id=analysis_run_id,
        version=1,
        schema_version="2.0",
        brief_json=brief_json,
        brief_markdown="# Quantitative Action Brief",
        is_latest=True,
    )
    session.add(brief)
    session.flush()
    return brief.id


def _create_workflow_run_record(session, analysis_run_id: str, startup_id: str) -> str:
    wf = WorkflowRun(
        startup_id=startup_id,
        analysis_run_id=analysis_run_id,
        status="completed",
        current_node="finish",
        graph_version="1.0",
        state_json={
            "completed_nodes": [
                "preflight",
                "load_startup",
                "collect_evidence",
                "validate_evidence",
            ],
            "failed_nodes": [],
            "degraded_nodes": [],
            "blockers": [],
            "review_required": False,
        },
    )
    session.add(wf)
    session.flush()
    return wf.id


# ---------------------------------------------------------------------------
# POST /analysis-runs
# ---------------------------------------------------------------------------


class TestCreateAnalysisRun:
    def test_creates_and_returns_analysis_run(self, client: TestClient, startup_id: str) -> None:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_workflow_run_record(session, ar_id, startup_id)
            session.commit()
        finally:
            session.close()

        mock_state = ProductWorkflowState(
            workflow_id="wf-test-1",
            startup_id=startup_id,
            analysis_run_id=ar_id,
            status="completed",
            completed_nodes=["preflight", "load_startup", "collect_evidence", "validate_evidence"],
            blockers=[],
        )
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=mock_state,
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        assert resp.status_code == 200, f"POST failed: {resp.text}"
        data = resp.json()
        assert data["run_id"] == ar_id
        assert data["startup_id"] == startup_id
        assert data["status"] == "completed"

    def test_returns_run_id_startup_id_and_status(self, client: TestClient, startup_id: str) -> None:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_workflow_run_record(session, ar_id, startup_id)
            session.commit()
        finally:
            session.close()

        mock_state = ProductWorkflowState(
            workflow_id="wf-test-2",
            startup_id=startup_id,
            analysis_run_id=ar_id,
            status="completed",
            completed_nodes=["preflight"],
            blockers=[],
        )
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=mock_state,
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == ar_id
        assert data["startup_id"] == startup_id
        assert data["status"] == "completed"

    def test_blocked_by_preflight_does_not_return_500(self, client: TestClient, startup_id: str) -> None:
        report = ProductReadinessReport(ready=False, user_messages=["Database not configured"])
        with patch(
            "src.services.product.readiness_service.ProductReadinessService.get_product_readiness",
            return_value=report,
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "blocked"

    def test_response_model_has_expected_fields(self, client: TestClient, startup_id: str) -> None:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_workflow_run_record(session, ar_id, startup_id)
            session.commit()
        finally:
            session.close()

        mock_state = ProductWorkflowState(
            workflow_id="wf-test-3",
            startup_id=startup_id,
            analysis_run_id=ar_id,
            status="completed",
            blockers=[],
        )
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=mock_state,
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        assert resp.status_code == 200
        data = resp.json()
        actual = set(data.keys())
        unexpected = actual - POST_RESPONSE_FIELDS
        assert not unexpected, f"Unexpected fields: {unexpected}"

    def test_unexpected_error_sanitized(self, client: TestClient, startup_id: str) -> None:
        original = "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow"
        with patch(
            original,
            side_effect=RuntimeError("internal crash detail"),
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})
        assert resp.status_code == 500
        data = resp.json()
        assert "detail" in data
        assert "internal crash detail" not in resp.text

    def test_startup_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.post("/analysis-runs", json={"startup_id": "nonexistent-startup-id"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /analysis-runs/{run_id}
# ---------------------------------------------------------------------------


class TestGetAnalysisRun:
    def test_returns_analysis_run(self, client: TestClient, startup_id: str) -> None:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_workflow_run_record(session, ar_id, startup_id)
            session.commit()
        finally:
            session.close()

        resp = client.get(f"/analysis-runs/{ar_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == ar_id
        assert data["startup_id"] == startup_id

    def test_returns_404_for_nonexistent_run(self, client: TestClient) -> None:
        resp = client.get("/analysis-runs/nonexistent-run-id")
        assert resp.status_code == 404

    def test_response_model_has_expected_fields(self, client: TestClient, startup_id: str) -> None:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_workflow_run_record(session, ar_id, startup_id)
            session.commit()
        finally:
            session.close()

        resp = client.get(f"/analysis-runs/{ar_id}")
        assert resp.status_code == 200
        data = resp.json()
        actual = set(data.keys())
        unexpected = actual - GET_RESPONSE_FIELDS
        assert not unexpected, f"Unexpected fields: {unexpected}"

    def test_does_not_expose_internal_fields(self, client: TestClient, startup_id: str) -> None:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_workflow_run_record(session, ar_id, startup_id)
            session.commit()
        finally:
            session.close()

        resp = client.get(f"/analysis-runs/{ar_id}")
        assert resp.status_code == 200
        data = resp.json()
        internal_keys = {
            "output_snapshot",
            "input_snapshot",
            "config_snapshot",
            "error_message",
            "_session",
        }
        exposed = set(data.keys()) & internal_keys
        assert not exposed, f"Internal fields exposed: {exposed}"


# ---------------------------------------------------------------------------
# GET /analysis-runs/{run_id}/brief and /brief/export/json
# ---------------------------------------------------------------------------


class TestPersistedActionBrief:
    def _setup_brief(
        self,
        startup_id: str,
        *,
        status: str = "passed",
        blockers: list[dict] | None = None,
    ) -> str:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_workflow_run_record(session, ar_id, startup_id)
            _create_quantitative_action_brief_record(
                session,
                ar_id,
                startup_id,
                status=status,
                blockers=blockers,
            )
            session.commit()
        finally:
            session.close()
        return ar_id

    def test_get_brief_returns_persisted_action_brief(
        self,
        client: TestClient,
        startup_id: str,
    ) -> None:
        ar_id = self._setup_brief(startup_id)
        resp = client.get(f"/analysis-runs/{ar_id}/brief")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["run_id"] == ar_id
        assert data["startup_id"] == startup_id
        assert data["brief_status"] == "passed"
        assert data["executive_summary_quantitative"]["average_priority_score"] == 0.85

    def test_get_brief_does_not_recalculate_or_call_external_services(
        self,
        client: TestClient,
        startup_id: str,
    ) -> None:
        ar_id = self._setup_brief(startup_id)
        with (
            patch(
                "src.rag.rag_service_factory.build_qdrant_rag_service",
                side_effect=AssertionError("qdrant"),
            ),
            patch(
                "src.recommendation.recommendation_engine.rank_recommendations_from_mappings",
                side_effect=AssertionError("recommendation"),
            ),
            patch(
                "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
                side_effect=AssertionError("langgraph"),
            ),
        ):
            resp = client.get(f"/analysis-runs/{ar_id}/brief")

        assert resp.status_code == 200, resp.text

    def test_missing_action_brief_returns_404(self, client: TestClient, startup_id: str) -> None:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            session.commit()
        finally:
            session.close()

        resp = client.get(f"/analysis-runs/{ar_id}/brief")
        assert resp.status_code == 404
        assert "Action brief not found" in resp.text

    def test_blocked_brief_returns_blockers_and_audit_trail(
        self,
        client: TestClient,
        startup_id: str,
    ) -> None:
        blockers = [
            {
                "blocker_id": "rec-blocked",
                "description": "generate_brief: ranking_status is 'failed'",
                "source": "generate_brief",
                "severity": "high",
            }
        ]
        ar_id = self._setup_brief(
            startup_id,
            status="blocked_ranking_not_passed",
            blockers=blockers,
        )

        resp = client.get(f"/analysis-runs/{ar_id}/brief")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["brief_status"] == "blocked_ranking_not_passed"
        assert data["blockers"][0]["description"] == blockers[0]["description"]
        assert blockers[0]["description"] in data["audit_trail"]["blockers"]

    def test_response_preserves_top_recommendation_quantitative_fields(
        self,
        client: TestClient,
        startup_id: str,
    ) -> None:
        ar_id = self._setup_brief(startup_id)
        resp = client.get(f"/analysis-runs/{ar_id}/brief")
        assert resp.status_code == 200, resp.text
        rec = resp.json()["top_recommendations"][0]
        assert rec["recommendation_priority_score"] == 0.85
        assert rec["recommendation_confidence"] == 0.72
        assert rec["uncertainty"] == 0.15
        assert rec["mapping_score"] == 0.8
        assert rec["mapping_confidence"] == 0.75
        assert rec["ai_native_score_value"] == 0.75
        assert rec["nvidia_fit_score_value"] == 0.65
        assert rec["gap_severity_score"] == 0.7
        assert rec["gap_confidence_score"] == 0.65
        assert rec["supporting_evidence_ids"] == ["ev-001"]
        assert rec["supporting_rag_context_ids"] == ["rag-001"]
        assert rec["supporting_claim_ids"] == ["claim-001"]
        assert rec["calibration_decision_ids"] == ["recommendation.priority_score_weights"]
        assert rec["production_allowed"] is True

    def test_export_json_includes_metadata_and_preserves_metrics(
        self,
        client: TestClient,
        startup_id: str,
    ) -> None:
        ar_id = self._setup_brief(startup_id)
        resp = client.get(f"/analysis-runs/{ar_id}/brief/export/json")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        metadata = data["export_metadata"]
        assert metadata["run_id"] == ar_id
        assert metadata["export_format"] == "json"
        assert metadata["source"] == "persisted_analysis_run_action_brief"
        assert metadata["schema_version"] == "2.0"
        assert metadata["export_id"]
        assert data["action_brief"]["brief_metrics"]["recommendation_count"] == 1
        assert data["action_brief"]["brief_metrics"]["average_recommendation_confidence"] == 0.72

    def test_export_json_does_not_expose_tracebacks_secrets_or_internal_fields(
        self,
        client: TestClient,
        startup_id: str,
    ) -> None:
        ar_id = self._setup_brief(startup_id)
        resp = client.get(f"/analysis-runs/{ar_id}/brief/export/json")
        assert resp.status_code == 200, resp.text
        text = resp.text
        assert "Traceback" not in text
        assert "secret-value" not in text
        assert "internal_token" not in text
        assert "brief_markdown" not in text

    def test_get_analysis_run_and_get_brief_are_consistent(
        self,
        client: TestClient,
        startup_id: str,
    ) -> None:
        ar_id = self._setup_brief(startup_id)
        run_resp = client.get(f"/analysis-runs/{ar_id}")
        brief_resp = client.get(f"/analysis-runs/{ar_id}/brief")
        assert run_resp.status_code == 200
        assert brief_resp.status_code == 200
        assert run_resp.json()["run_id"] == brief_resp.json()["run_id"]
        assert run_resp.json()["startup_id"] == brief_resp.json()["startup_id"]


# ---------------------------------------------------------------------------
# POST /analysis-runs/{analysis_run_id}/resume
# ---------------------------------------------------------------------------


def _create_awaiting_review_workflow(session, ar_id: str, startup_id: str) -> str:
    """Create a workflow run in awaiting_review state with a stored thread_id."""
    import uuid

    thread_id = str(uuid.uuid4())
    wf = WorkflowRun(
        startup_id=startup_id,
        analysis_run_id=ar_id,
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
                "run_id": ar_id,
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


class TestResumeAnalysisRun:
    """Integration tests for POST /analysis-runs/{analysis_run_id}/resume."""

    def _patch_submit_review(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from datetime import UTC, datetime

        from src.orchestration.service import WorkflowOrchestrationService

        def mock_submit_review(
            self_obj: WorkflowOrchestrationService,
            workflow_id: str,
            *,
            decision: str,
            reviewer: str,
            notes: str,
            resume: bool = False,
        ) -> dict:
            return {
                "workflow_id": workflow_id,
                "decision": decision,
                "reviewer": reviewer,
                "notes": notes,
                "created_at": datetime.now(UTC).isoformat(),
            }

        monkeypatch.setattr(
            "src.orchestration.service.WorkflowOrchestrationService.submit_review",
            mock_submit_review,
        )

    def _assert_review_decision_persisted(self, analysis_run_id: str, startup_id: str, expected_decision: str) -> None:
        """Verify a ReviewDecision was persisted with the expected fields."""
        session = next(get_db_session())
        try:
            from src.repositories.review import ReviewDecisionRepository

            repo = ReviewDecisionRepository(session)
            records = repo.list_for_run(analysis_run_id)
            assert len(records) >= 1
            latest = records[0]
            assert latest.analysis_run_id == analysis_run_id
            assert latest.startup_id == startup_id
            assert latest.decision == expected_decision
            assert latest.status_before_resume == "awaiting_review"
            assert latest.review_payload_snapshot is not None
            assert latest.thread_id is not None
        finally:
            session.close()

    def test_resume_rejected_workflow_returns_200(
        self, client: TestClient, startup_id: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_submit_review(monkeypatch)
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_awaiting_review_workflow(session, ar_id, startup_id)
            session.commit()
        finally:
            session.close()

        resp = client.post(
            f"/analysis-runs/{ar_id}/resume",
            json={"decision": "reject", "reviewer": "test-user", "notes": "Not a fit"},
        )
        assert resp.status_code == 200, f"Resume failed: {resp.text}"
        data = resp.json()
        assert data["startup_id"] == startup_id

        self._assert_review_decision_persisted(ar_id, startup_id, "reject")

    def test_resume_approve_returns_200(
        self, client: TestClient, startup_id: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_submit_review(monkeypatch)
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_awaiting_review_workflow(session, ar_id, startup_id)
            session.commit()
        finally:
            session.close()

        resp = client.post(
            f"/analysis-runs/{ar_id}/resume",
            json={"decision": "approve", "reviewer": "test-user", "notes": "Looks good"},
        )
        assert resp.status_code == 200, f"Resume failed: {resp.text}"
        data = resp.json()
        assert data["startup_id"] == startup_id

        self._assert_review_decision_persisted(ar_id, startup_id, "approve")

    def test_resume_nonexistent_run_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/analysis-runs/nonexistent/resume",
            json={"decision": "approve", "reviewer": "test-user", "notes": ""},
        )
        assert resp.status_code == 404

    def test_resume_invalid_decision_returns_422(self, client: TestClient, startup_id: str) -> None:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_awaiting_review_workflow(session, ar_id, startup_id)
            session.commit()
        finally:
            session.close()

        resp = client.post(
            f"/analysis-runs/{ar_id}/resume",
            json={"decision": "invalid", "reviewer": "test-user", "notes": ""},
        )
        assert resp.status_code == 422

        session = next(get_db_session())
        try:
            from src.repositories.review import ReviewDecisionRepository

            repo = ReviewDecisionRepository(session)
            records = repo.list_for_run(ar_id)
            assert len(records) == 0, "No ReviewDecision should be persisted for invalid decision"
        finally:
            session.close()

    def test_resume_without_workflow_returns_404(self, client: TestClient, startup_id: str) -> None:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            session.commit()
        finally:
            session.close()

        resp = client.post(
            f"/analysis-runs/{ar_id}/resume",
            json={"decision": "approve", "reviewer": "test-user", "notes": ""},
        )
        assert resp.status_code == 404

        session = next(get_db_session())
        try:
            from src.repositories.review import ReviewDecisionRepository

            repo = ReviewDecisionRepository(session)
            records = repo.list_for_run(ar_id)
            assert len(records) == 0, "No orphan ReviewDecision should be persisted for missing workflow"
        finally:
            session.close()

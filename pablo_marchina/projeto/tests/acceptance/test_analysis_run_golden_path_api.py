"""Acceptance test: AnalysisRun golden path via API.

Validates the complete contract:
  POST /analysis-runs → workflow result → persisted → GET /analysis-runs/{id}

Uses mocked orchestration service but real SQLite database.
"""

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

REQUIRED_EXECUTED_NODES = frozenset(
    {
        "preflight_configuration_check",
        "validate_evidence",
        "retrieve_nvidia_context",
        "rank_recommendations",
        "generate_brief",
        "run_quality_gates",
    }
)

ACTION_BRIEF_REQUIRED_KEYS = frozenset(
    {
        "summary",
        "top_recommendations",
        "evidence_summary",
        "rag_summary",
        "risks",
        "next_best_actions",
        "confidence",
        "generated_from",
        "audit_flags",
    }
)


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
    monkeypatch.setenv("RAG_REQUIRED_FOR_PRODUCT", "false")
    monkeypatch.setenv("PRODUCT_DATA_DIR", str(tmp_path / "product_data"))
    db_url = f"sqlite:///{(tmp_path / 'analysis_run_golden.db').as_posix()}"
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
            "name": "Golden Path Analysis Run",
            "website": "https://golden-analysis.example.com",
            "sector": "AI Infrastructure",
            "description": "Test startup for analysis run golden path",
            "product_summary": "AI-powered analytics platform",
            "tags": ["golden-path", "acceptance"],
            "evidence": [
                {
                    "claim": "Uses GPU inference in production",
                    "source_url": "https://golden-analysis.example.com/tech",
                    "source_type": "official_site",
                    "quote_or_evidence": "Runs GPU inference workloads in production.",
                    "confidence": "high",
                },
                {
                    "claim": "Has 100+ enterprise customers",
                    "source_url": "https://golden-analysis.example.com/customers",
                    "source_type": "official_site",
                    "quote_or_evidence": "Serving 100+ enterprise customers globally.",
                    "confidence": "medium",
                },
            ],
        },
    )
    assert resp.status_code == 201, f"Create startup failed: {resp.text}"
    return resp.json()["id"]


def _create_analysis_run_record(session, startup_id: str) -> str:
    run = AnalysisRun(
        startup_id=startup_id,
        status="completed",
        input_snapshot_json={"startup_name": "Golden Path Analysis Run"},
        output_snapshot_json={
            "validated_evidence": {
                "status": "passed",
                "total": 2,
                "supported": 2,
                "unsupported": 0,
            },
            "rag_output": {
                "retrieved_context_count": 3,
                "contexts": ["NVIDIA CUDA", "NVIDIA TensorRT", "NVIDIA Triton"],
                "metrics": {"precision": 0.85, "recall": 0.78},
            },
            "recommendation": {
                "recommendation_count": 2,
                "recommendations": [
                    {"technology": "NVIDIA CUDA", "priority": "high"},
                    {"technology": "NVIDIA TensorRT", "priority": "medium"},
                ],
            },
            "action_brief": {
                "version": "2.0",
                "word_count": 450,
            },
            "brief_metrics": {
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
            },
        },
        pipeline_version="test",
        config_snapshot_json={},
    )
    session.add(run)
    session.flush()
    return run.id


def _create_workflow_run_record(session, analysis_run_id: str, startup_id: str) -> str:
    wf = WorkflowRun(
        startup_id=startup_id,
        analysis_run_id=analysis_run_id,
        status="completed",
        current_node="finish",
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
            "review_required": False,
        },
    )
    session.add(wf)
    session.flush()
    return wf.id


def _create_action_brief_record(session, analysis_run_id: str) -> str:
    run = session.get(AnalysisRun, analysis_run_id)
    assert run is not None
    brief = ActionBriefRecord(
        analysis_run_id=analysis_run_id,
        version=1,
        schema_version="2.0",
        brief_json={
            "summary": "Golden Path AI shows strong AI-native capabilities with GPU inference in production.",
            "run_id": analysis_run_id,
            "startup_id": run.startup_id,
            "generated_at": "2026-06-19T12:00:00+00:00",
            "brief_status": "passed",
            "executive_summary_quantitative": {
                "production_allowed_recommendations": 1,
                "average_priority_score": 0.85,
                "average_confidence": 0.72,
                "average_uncertainty": 0.15,
            },
            "recommendation_summary": "NVIDIA CUDA(priority=0.85, confidence=0.72, uncertainty=0.15)",
            "top_recommendations": [
                {
                    "technology": "NVIDIA CUDA",
                    "action": "Adopt for GPU acceleration",
                    "recommendation_id": "rec-golden-001",
                    "nvidia_technology": "NVIDIA CUDA",
                    "gap_id": "gap-golden-001",
                    "gap_type": "inference_performance_gap",
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
                    "supporting_evidence_ids": ["ev-golden-001"],
                    "supporting_rag_context_ids": ["rag-golden-001"],
                    "supporting_claim_ids": ["claim-golden-001"],
                    "calibration_decision_ids": ["recommendation.priority_score_weights"],
                    "next_best_action": "Evaluate CUDA acceleration fit",
                    "reason_grounded_in_scores": "priority_score=0.85; confidence=0.72",
                    "production_allowed": True,
                }
            ],
            "evidence_summary": "2 pieces of evidence collected, 2 supported.",
            "rag_summary": "3 NVIDIA contexts retrieved for recommendation.",
            "gap_summary": "total_gaps=1 | covered_by_recommendations=1 | status=passed",
            "scoring_summary": "ai_native_score=0.75 | nvidia_fit_score=0.65 | status=passed",
            "risk_summary": "none",
            "risks": ["Dependency on single cloud provider"],
            "blockers": [],
            "next_best_actions": [
                "Run NVIDIA Inception technical assessment",
                "Evaluate TensorRT integration",
            ],
            "audit_trail": {
                "executed_nodes": ["rank_recommendations", "generate_brief"],
                "calibration_decision_ids": ["recommendation.priority_score_weights"],
                "evidence_ids": ["ev-golden-001"],
                "rag_context_ids": ["rag-golden-001"],
                "blockers": [],
                "quality_gate_status": "passed",
            },
            "quality_gate_snapshot": {
                "status": "passed",
                "failed_checks": [],
                "warning_checks": [],
            },
            "calibration_snapshot": {
                "calibration_decision_count": 1,
                "missing_calibration_count": 0,
            },
            "confidence": "high",
            "generated_from": "analysis_run",
            "audit_flags": [],
        },
        brief_markdown="# Action Brief\n\nGolden Path AI...",
        is_latest=True,
    )
    session.add(brief)
    session.flush()
    return brief.id


# ---------------------------------------------------------------------------
# Golden Path Tests
# ---------------------------------------------------------------------------


@pytest.mark.acceptance
class TestAnalysisRunGoldenPath:
    """Complete golden path: POST → validate → GET → validate invariants."""

    def _setup_db_records(self, client: TestClient, startup_id: str) -> tuple[str, str]:
        session = next(get_db_session())
        try:
            ar_id = _create_analysis_run_record(session, startup_id)
            _create_workflow_run_record(session, ar_id, startup_id)
            _create_action_brief_record(session, ar_id)
            session.commit()
        finally:
            session.close()
        return ar_id

    def _mock_state(self, analysis_run_id: str, startup_id: str) -> ProductWorkflowState:
        return ProductWorkflowState(
            workflow_id="wf-golden-1",
            startup_id=startup_id,
            analysis_run_id=analysis_run_id,
            status="completed",
            completed_nodes=list(REQUIRED_EXECUTED_NODES),
            blockers=[],
        )

    # --- POST /analysis-runs ---

    def test_post_returns_all_contract_fields(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)

        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=self._mock_state(ar_id, startup_id),
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        assert resp.status_code == 200, f"POST failed: {resp.text}"
        data = resp.json()

        assert data["run_id"] == ar_id
        assert data["startup_id"] == startup_id
        assert data["status"] == "completed"

    def test_post_returns_evidence_validation(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=self._mock_state(ar_id, startup_id),
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        data = resp.json()
        ev = data["evidence_validation"]
        assert isinstance(ev, dict)
        assert ev.get("status") in {"passed", "needs_review", "failed"}

    def test_post_returns_rag_metrics(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=self._mock_state(ar_id, startup_id),
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        data = resp.json()
        rm = data["rag_metrics"]
        assert isinstance(rm, dict)
        assert rm.get("retrieved_context_count", 0) >= 1

    def test_post_returns_recommendation_metrics(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=self._mock_state(ar_id, startup_id),
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        data = resp.json()
        rec = data["recommendation_metrics"]
        assert isinstance(rec, dict)
        assert rec.get("recommendation_count", 0) >= 1

    def test_post_executed_nodes_contains_required(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=self._mock_state(ar_id, startup_id),
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        data = resp.json()
        executed = set(data.get("executed_nodes", []))
        missing = REQUIRED_EXECUTED_NODES - executed
        assert not missing, f"Missing required executed_nodes: {missing}"

    def test_post_action_brief_has_required_keys(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=self._mock_state(ar_id, startup_id),
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        data = resp.json()
        brief = data.get("action_brief")
        assert brief is not None, "action_brief should not be None"
        assert "brief_json" in brief
        brief_data = brief["brief_json"]
        missing = ACTION_BRIEF_REQUIRED_KEYS - set(brief_data.keys())
        assert not missing, f"action_brief.brief_json missing keys: {missing}"
        assert len(brief_data.get("top_recommendations", [])) >= 1

    def test_post_no_traceback_in_response(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=self._mock_state(ar_id, startup_id),
        ):
            resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        assert "Traceback" not in resp.text
        assert 'File "' not in resp.text

    # --- GET /analysis-runs/{run_id} ---

    def test_get_returns_same_run_id_and_startup_id(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=self._mock_state(ar_id, startup_id),
        ):
            post_resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        post_data = post_resp.json()
        get_resp = client.get(f"/analysis-runs/{ar_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()

        assert get_data["run_id"] == post_data["run_id"]
        assert get_data["startup_id"] == post_data["startup_id"]

    def test_get_returns_same_status(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        with patch(
            "src.orchestration.service.WorkflowOrchestrationService.create_and_run_workflow",
            return_value=self._mock_state(ar_id, startup_id),
        ):
            post_resp = client.post("/analysis-runs", json={"startup_id": startup_id})

        post_data = post_resp.json()
        get_resp = client.get(f"/analysis-runs/{ar_id}")
        get_data = get_resp.json()

        assert get_data["status"] == post_data["status"]

    def test_get_returns_detail_metrics(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        resp = client.get(f"/analysis-runs/{ar_id}")
        assert resp.status_code == 200
        data = resp.json()

        assert "evidence_validation" in data
        assert "rag_metrics" in data
        assert "recommendation_metrics" in data
        assert "brief_metrics" in data

        ev = data["evidence_validation"]
        assert isinstance(ev, dict)
        assert ev.get("status") in {"passed", "needs_review", "failed"}

        rm = data["rag_metrics"]
        assert rm.get("retrieved_context_count", 0) >= 1

        rec = data["recommendation_metrics"]
        assert rec.get("recommendation_count", 0) >= 1

    def test_get_action_brief_has_required_keys(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        resp = client.get(f"/analysis-runs/{ar_id}")
        assert resp.status_code == 200
        data = resp.json()
        brief = data.get("action_brief")
        assert brief is not None
        assert "brief_json" in brief
        brief_data = brief["brief_json"]
        missing = ACTION_BRIEF_REQUIRED_KEYS - set(brief_data.keys())
        assert not missing, f"GET action_brief.brief_json missing keys: {missing}"
        assert len(brief_data.get("top_recommendations", [])) >= 1

    def test_get_brief_endpoint_returns_quantitative_action_brief(
        self,
        client: TestClient,
        startup_id: str,
    ) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        resp = client.get(f"/analysis-runs/{ar_id}/brief")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["run_id"] == ar_id
        assert data["startup_id"] == startup_id
        assert data["brief_status"] == "passed"
        assert data["executive_summary_quantitative"]["average_priority_score"] == 0.85
        assert data["top_recommendations"][0]["recommendation_priority_score"] == 0.85
        assert data["top_recommendations"][0]["supporting_rag_context_ids"] == ["rag-golden-001"]
        assert data["brief_metrics"]["recommendation_count"] == 1

    def test_get_brief_export_json_returns_metadata_and_same_brief(
        self,
        client: TestClient,
        startup_id: str,
    ) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        resp = client.get(f"/analysis-runs/{ar_id}/brief/export/json")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["export_metadata"]["run_id"] == ar_id
        assert data["export_metadata"]["export_format"] == "json"
        assert data["export_metadata"]["source"] == "persisted_analysis_run_action_brief"
        assert data["action_brief"]["run_id"] == ar_id
        assert data["action_brief"]["startup_id"] == startup_id
        assert data["action_brief"]["brief_metrics"]["recommendation_count"] == 1

    def test_get_no_sensitive_fields(self, client: TestClient, startup_id: str) -> None:
        ar_id = self._setup_db_records(client, startup_id)
        resp = client.get(f"/analysis-runs/{ar_id}")
        assert resp.status_code == 200
        data = resp.json()
        sensitive = {"output_snapshot", "input_snapshot", "config_snapshot", "error_message"}
        exposed = set(data.keys()) & sensitive
        assert not exposed, f"Sensitive/internal fields exposed in GET: {exposed}"

    # --- Negative tests ---

    def test_get_nonexistent_run_returns_404(self, client: TestClient) -> None:
        resp = client.get("/analysis-runs/nonexistent-run-id-12345")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert "Traceback" not in resp.text

    def test_post_nonexistent_startup_returns_404(self, client: TestClient) -> None:
        resp = client.post("/analysis-runs", json={"startup_id": "nonexistent-startup"})
        assert resp.status_code == 404
        assert "Traceback" not in resp.text

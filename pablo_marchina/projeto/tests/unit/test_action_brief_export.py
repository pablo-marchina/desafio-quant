from __future__ import annotations

from src.api.product_schemas import ActionBriefJsonExportRead, PersistedActionBriefRead
from src.database.models import ActionBriefRecord, AnalysisRun
from src.services.product.export_service import (
    persisted_action_brief_json_export_payload,
    persisted_action_brief_payload,
)


def _run() -> AnalysisRun:
    return AnalysisRun(
        id="run-export-001",
        startup_id="startup-export-001",
        status="completed",
        input_snapshot_json={},
        output_snapshot_json={
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
            }
        },
        pipeline_version="test",
        config_snapshot_json={},
    )


def _brief() -> ActionBriefRecord:
    return ActionBriefRecord(
        id="brief-export-001",
        analysis_run_id="run-export-001",
        version=1,
        schema_version="2.0",
        brief_json={
            "run_id": "run-export-001",
            "startup_id": "startup-export-001",
            "generated_at": "2026-06-19T12:00:00+00:00",
            "brief_status": "passed",
            "executive_summary_quantitative": {
                "average_priority_score": 0.85,
                "average_confidence": 0.72,
            },
            "recommendation_summary": "NVIDIA NIM(priority=0.85)",
            "top_recommendations": [
                {
                    "recommendation_id": "rec-export-001",
                    "nvidia_technology": "NVIDIA NIM",
                    "gap_id": "gap-export-001",
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
                    "supporting_evidence_ids": ["ev-export-001"],
                    "supporting_rag_context_ids": ["rag-export-001"],
                    "supporting_claim_ids": ["claim-export-001"],
                    "calibration_decision_ids": ["recommendation.priority_score_weights"],
                    "next_best_action": "Engage startup to discuss NVIDIA NIM",
                    "reason_grounded_in_scores": "priority_score=0.85; confidence=0.72",
                    "production_allowed": True,
                }
            ],
            "evidence_summary": "evidence_items=2 | accepted=2",
            "rag_summary": "rag_contexts=1 | rag_supported_recommendations=1/1",
            "gap_summary": "total_gaps=1 | covered_by_recommendations=1",
            "scoring_summary": "ai_native_score=0.75 | nvidia_fit_score=0.65",
            "risk_summary": "none",
            "blockers": [],
            "next_best_actions": ["Engage startup to discuss NVIDIA NIM"],
            "audit_trail": {
                "executed_nodes": ["rank_recommendations", "generate_brief"],
                "calibration_decision_ids": ["recommendation.priority_score_weights"],
                "evidence_ids": ["ev-export-001"],
                "rag_context_ids": ["rag-export-001"],
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
            "traceback": "must not leak",
            "internal_token": "secret-value",
        },
        brief_markdown="# Hidden markdown",
        is_latest=True,
    )


def test_persisted_action_brief_payload_validates_and_preserves_metrics() -> None:
    payload = persisted_action_brief_payload(_run(), _brief())
    model = PersistedActionBriefRead(**payload)
    rec = model.top_recommendations[0]

    assert model.run_id == "run-export-001"
    assert model.startup_id == "startup-export-001"
    assert model.brief_metrics.recommendation_count == 1
    assert model.brief_metrics.average_recommendation_confidence == 0.72
    assert rec.recommendation_priority_score == 0.85
    assert rec.supporting_evidence_ids == ["ev-export-001"]
    assert rec.supporting_rag_context_ids == ["rag-export-001"]
    assert rec.calibration_decision_ids == ["recommendation.priority_score_weights"]


def test_export_json_includes_metadata_and_sanitized_action_brief() -> None:
    payload = persisted_action_brief_json_export_payload(_run(), _brief())
    model = ActionBriefJsonExportRead(**payload)
    dumped = model.model_dump(mode="json")

    assert dumped["export_metadata"]["export_id"]
    assert dumped["export_metadata"]["run_id"] == "run-export-001"
    assert dumped["export_metadata"]["export_format"] == "json"
    assert dumped["export_metadata"]["source"] == "persisted_analysis_run_action_brief"
    assert dumped["export_metadata"]["schema_version"] == "2.0"
    assert "traceback" not in dumped["action_brief"]
    assert "internal_token" not in dumped["action_brief"]
    assert "brief_markdown" not in dumped["action_brief"]

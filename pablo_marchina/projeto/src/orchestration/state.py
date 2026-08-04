from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class WorkflowStatus:
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    DEGRADED = "degraded"
    FAILED = "failed"


class ProductWorkflowState(BaseModel):
    workflow_id: str
    startup_id: str | None = None
    discovery_candidate_id: str | None = None
    analysis_run_id: str | None = None
    status: str = ""
    blockers: list[str] = []
    current_node: str = ""
    completed_nodes: list[str] = []
    failed_nodes: list[str] = []
    degraded_nodes: list[str] = []
    node_outputs: dict[str, Any] = {}
    evidence_ids: list[str] = []
    claim_ids: list[str] = []
    score_ids: list[str] = []
    gap_ids: list[str] = []
    mapping_ids: list[str] = []
    activation_recommendation_ids: list[str] = []
    dossier_id: str | None = None
    quality_run_id: str | None = None
    readiness_check_ids: list[str] = []
    search_plan: list[dict[str, Any]] = []
    raw_evidence: list[dict[str, Any]] = []
    evidence_items: list[dict[str, Any]] = []
    startup_profile: dict[str, Any] = {}
    classification_result: dict[str, Any] = {}
    defensibility_result: dict[str, Any] = {}
    inception_fit_result: dict[str, Any] = {}
    production_readiness_result: dict[str, Any] = {}
    scores: dict[str, Any] = {}
    nvidia_mappings: list[dict[str, Any]] = []
    nvidia_contexts: list[Any] = []
    recommendations: list[str] = []
    brief: dict[str, Any] = {}
    quality_gates_result: dict[str, Any] = {}
    review_payload: dict[str, Any] = {}
    review_required: bool = False
    review_decision: str = ""
    feedback_counts: dict[str, dict[str, int]] = {}
    adjusted_weights: dict[str, float] = {}
    feedback_adjustments: dict[str, Any] = {}
    iteration_count: int = 0
    max_iterations: int = 3
    technique_results: list[dict[str, Any]] = []
    evidence_weighted_scores: dict[str, Any] = {}
    ranked_recommendations: list[dict[str, Any]] = []
    decision_ledger_path: str = ""
    error_message: str | None = None
    metadata_json: dict[str, Any] = {}

from __future__ import annotations

from typing import Any

QUALITY_RUN_STATUS_RUNNING = "running"
QUALITY_RUN_STATUS_COMPLETED = "completed"
QUALITY_RUN_STATUS_FAILED = "failed"
QUALITY_RUN_STATUS_DEGRADED = "degraded"

METRIC_SEVERITY_INFO = "info"
METRIC_SEVERITY_WARN = "warn"
METRIC_SEVERITY_ERROR = "error"

METRIC_EVIDENCE_COVERAGE = "evidence_coverage"
METRIC_UNSUPPORTED_CLAIM_RATE = "unsupported_claim_rate"
METRIC_UNSUPPORTED_CRITICAL_CLAIM_COUNT = "unsupported_critical_claim_count"
METRIC_WEAK_CLAIM_RATE = "weak_claim_rate"
METRIC_DOSSIER_SECTION_COMPLETENESS = "dossier_section_completeness"
METRIC_MISSING_REQUIRED_SECTIONS = "missing_required_sections"
METRIC_ACTIVATION_PLAYBOOK_PRESENT = "activation_playbook_present"
METRIC_ACTIVATION_PLAYBOOK_EVIDENCE_SUPPORT = "activation_playbook_evidence_support"
METRIC_RECOMMENDATION_ACTIONABILITY_SCORE = "recommendation_actionability_score"
METRIC_DEGRADED_STATE_COUNT = "degraded_state_count"
METRIC_EXPORT_READINESS_SCORE = "export_readiness_score"
METRIC_REVIEW_READINESS_SCORE = "review_readiness_score"
METRIC_STRUCTURED_OUTPUT_VALID_RATE = "structured_output_valid_rate"
METRIC_STRUCTURED_OUTPUT_REPAIR_RATE = "structured_output_repair_rate"
METRIC_STRUCTURED_OUTPUT_FAILURE_RATE = "structured_output_failure_rate"
METRIC_AVG_RETRY_COUNT = "avg_retry_count"
METRIC_SCHEMA_VALIDATION_ERROR_COUNT = "schema_validation_error_count"
METRIC_MISSING_REQUIRED_FIELD_COUNT = "missing_required_field_count"

# RAG quality metrics (Epic 42)
METRIC_RAG_RETRIEVAL_SUCCESS = "rag_retrieval_success"
METRIC_RAG_DEGRADED_MODE = "rag_degraded_mode"
METRIC_RAG_FALLBACK_COUNT = "rag_fallback_count"
METRIC_RAG_SOURCE_COVERAGE = "rag_source_coverage"
METRIC_RAG_AVG_DENSE_SCORE = "rag_avg_dense_score"
METRIC_RAG_AVG_SPARSE_SCORE = "rag_avg_sparse_score"
METRIC_RAG_AVG_FUSED_SCORE = "rag_avg_fused_score"

DEFAULT_EVALUATOR_VERSION = "1.0"

DOSSIER_REQUIRED_SECTIONS: set[str] = {
    "metadata",
    "startup",
    "executive_verdict",
    "evidence_summary",
    "claims",
    "scores",
    "gaps",
    "nvidia_mappings",
    "activation_recommendations",
    "risks",
    "uncertainties",
    "review",
    "next_action",
}

THRESHOLDS: dict[str, dict[str, Any]] = {
    METRIC_RAG_RETRIEVAL_SUCCESS: {
        "threshold": 1.0,
        "severity": METRIC_SEVERITY_ERROR,
        "operator": "eq",
    },
    METRIC_RAG_DEGRADED_MODE: {
        "threshold": 0.0,
        "severity": METRIC_SEVERITY_WARN,
        "operator": "eq",
    },
    METRIC_RAG_SOURCE_COVERAGE: {
        "threshold": 0.50,
        "severity": METRIC_SEVERITY_WARN,
        "operator": "gte",
    },
    METRIC_RAG_AVG_FUSED_SCORE: {
        "threshold": 0.30,
        "severity": METRIC_SEVERITY_INFO,
        "operator": "gte",
    },
    METRIC_EVIDENCE_COVERAGE: {
        "threshold": 0.60,
        "severity": METRIC_SEVERITY_WARN,
        "operator": "gte",
    },
    METRIC_UNSUPPORTED_CLAIM_RATE: {
        "threshold": 0.20,
        "severity": METRIC_SEVERITY_ERROR,
        "operator": "lte",
    },
    METRIC_UNSUPPORTED_CRITICAL_CLAIM_COUNT: {
        "threshold": 0.0,
        "severity": METRIC_SEVERITY_ERROR,
        "operator": "eq",
    },
    METRIC_DOSSIER_SECTION_COMPLETENESS: {
        "threshold": 0.85,
        "severity": METRIC_SEVERITY_ERROR,
        "operator": "gte",
    },
    METRIC_ACTIVATION_PLAYBOOK_PRESENT: {
        "threshold": 1.0,
        "severity": METRIC_SEVERITY_WARN,
        "operator": "eq",
    },
    METRIC_RECOMMENDATION_ACTIONABILITY_SCORE: {
        "threshold": 0.70,
        "severity": METRIC_SEVERITY_WARN,
        "operator": "gte",
    },
    METRIC_EXPORT_READINESS_SCORE: {
        "threshold": 0.70,
        "severity": METRIC_SEVERITY_INFO,
        "operator": "gte",
    },
    METRIC_REVIEW_READINESS_SCORE: {
        "threshold": 0.60,
        "severity": METRIC_SEVERITY_INFO,
        "operator": "gte",
    },
    METRIC_STRUCTURED_OUTPUT_VALID_RATE: {
        "threshold": 0.95,
        "severity": METRIC_SEVERITY_WARN,
        "operator": "gte",
    },
    METRIC_STRUCTURED_OUTPUT_REPAIR_RATE: {
        "threshold": 0.10,
        "severity": METRIC_SEVERITY_INFO,
        "operator": "lte",
    },
    METRIC_STRUCTURED_OUTPUT_FAILURE_RATE: {
        "threshold": 0.05,
        "severity": METRIC_SEVERITY_ERROR,
        "operator": "lte",
    },
    METRIC_AVG_RETRY_COUNT: {
        "threshold": 1.0,
        "severity": METRIC_SEVERITY_INFO,
        "operator": "lte",
    },
    "workflow_completion_rate": {
        "threshold": 1.0,
        "severity": METRIC_SEVERITY_ERROR,
        "operator": "eq",
    },
    "node_failure_count": {
        "threshold": 0.0,
        "severity": METRIC_SEVERITY_ERROR,
        "operator": "eq",
    },
    "degraded_node_count": {
        "threshold": 2.0,
        "severity": METRIC_SEVERITY_WARN,
        "operator": "lte",
    },
    "workflow_duration_ms": {
        "threshold": 30000.0,
        "severity": METRIC_SEVERITY_INFO,
        "operator": "lte",
    },
    "retry_count": {
        "threshold": 1.0,
        "severity": METRIC_SEVERITY_INFO,
        "operator": "lte",
    },
    "critical_node_success": {
        "threshold": 1.0,
        "severity": METRIC_SEVERITY_ERROR,
        "operator": "eq",
    },
}

# ---------------------------------------------------------------------------
# Opportunity Score metric constants (Epic 43)
# ---------------------------------------------------------------------------
METRIC_OPPORTUNITY_SCORE = "opportunity_score"
METRIC_OPPORTUNITY_COMPONENT_COVERAGE = "opportunity_component_coverage"
METRIC_OPPORTUNITY_PENALTY_TOTAL = "opportunity_penalty_total"
METRIC_OPPORTUNITY_EVIDENCE_REF_COUNT = "opportunity_evidence_ref_count"
METRIC_OPPORTUNITY_RECOMMENDED_ACTION_DEFINED = "opportunity_recommended_action_defined"

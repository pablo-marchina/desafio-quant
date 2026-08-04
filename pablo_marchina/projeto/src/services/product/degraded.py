"""Explicit degraded-state definitions for product operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DegradedStateDefinition:
    code: str
    severity: str
    user_message: str
    recommended_action: str


DEGRADED_STATES: dict[str, DegradedStateDefinition] = {
    "QDRANT_UNAVAILABLE": DegradedStateDefinition(
        code="QDRANT_UNAVAILABLE",
        severity="warning",
        user_message="Vector search is unavailable for this analysis.",
        recommended_action="Verify QDRANT_URL, credentials, and the Qdrant service.",
    ),
    "RAG_UNAVAILABLE": DegradedStateDefinition(
        code="RAG_UNAVAILABLE",
        severity="warning",
        user_message="NVIDIA retrieval context was unavailable or incomplete.",
        recommended_action="Verify the corpus, embedding provider, and vector backend.",
    ),
    "SOURCE_COMPLIANCE_UNAVAILABLE": DegradedStateDefinition(
        code="SOURCE_COMPLIANCE_UNAVAILABLE",
        severity="warning",
        user_message="Source compliance could not be verified for one or more sources.",
        recommended_action="Run source compliance checks in an environment with required network access.",
    ),
    "SOURCE_QUALITY_INSUFFICIENT": DegradedStateDefinition(
        code="SOURCE_QUALITY_INSUFFICIENT",
        severity="warning",
        user_message="Available sources do not provide enough quality for a strong claim.",
        recommended_action="Collect stronger official or independent evidence before using the claim.",
    ),
    "GRAPH_INDEX_UNAVAILABLE": DegradedStateDefinition(
        code="GRAPH_INDEX_UNAVAILABLE",
        severity="info",
        user_message="Evidence graph retrieval is unavailable for this run.",
        recommended_action="Use baseline RAG and run the GraphRAG direct benchmark before promotion.",
    ),
    "GRAPH_BENCHMARK_NOT_PROMOTED": DegradedStateDefinition(
        code="GRAPH_BENCHMARK_NOT_PROMOTED",
        severity="info",
        user_message="GraphRAG remains a benchmark candidate and is not promoted to default runtime.",
        recommended_action="Promote only after direct benchmark evidence and final gates pass.",
    ),
    "SECURITY_SCAN_PENDING": DegradedStateDefinition(
        code="SECURITY_SCAN_PENDING",
        severity="warning",
        user_message="A required security scan has not produced a real final report.",
        recommended_action="Run the release security scanner and attach the JSON report.",
    ),
    "PROMPT_INJECTION_SUITE_PENDING": DegradedStateDefinition(
        code="PROMPT_INJECTION_SUITE_PENDING",
        severity="warning",
        user_message="The LLM/RAG prompt injection suite has not passed yet.",
        recommended_action="Run make test-security-llm and review the generated security reports.",
    ),
    "COLD_START_NOT_PROVEN": DegradedStateDefinition(
        code="COLD_START_NOT_PROVEN",
        severity="warning",
        user_message="Cold-start setup has not been proven in a clean environment.",
        recommended_action="Run the cold-start proof and store final_case_evidence/cold_start_report.json.",
    ),
    "FRONTEND_BUILD_NOT_PROVEN": DegradedStateDefinition(
        code="FRONTEND_BUILD_NOT_PROVEN",
        severity="warning",
        user_message="Frontend build reproducibility has not been proven.",
        recommended_action="Run npm ci and npm run build in a clean frontend environment.",
    ),
    "DIRECT_BENCHMARK_MISSING": DegradedStateDefinition(
        code="DIRECT_BENCHMARK_MISSING",
        severity="warning",
        user_message="A candidate lacks direct output benchmark evidence.",
        recommended_action="Run the direct benchmark protocol before promotion.",
    ),
    "PROXY_ONLY_CANDIDATE": DegradedStateDefinition(
        code="PROXY_ONLY_CANDIDATE",
        severity="info",
        user_message="Candidate only has proxy or local-readiness evidence.",
        recommended_action="Keep outside runtime until direct benchmark evidence exists.",
    ),
    "CORPUS_STALE": DegradedStateDefinition(
        code="CORPUS_STALE",
        severity="warning",
        user_message="The NVIDIA corpus may be stale.",
        recommended_action="Run the corpus freshness audit and maintenance workflow.",
    ),
    "MISSING_EVIDENCE": DegradedStateDefinition(
        code="MISSING_EVIDENCE",
        severity="warning",
        user_message="The analysis has material missing evidence.",
        recommended_action="Collect and validate additional public startup evidence.",
    ),
    "SCORE_INCOMPLETE": DegradedStateDefinition(
        code="SCORE_INCOMPLETE",
        severity="error",
        user_message="One or more required product scores are incomplete.",
        recommended_action="Inspect the pipeline output and score inputs before review.",
    ),
    "EVAL_FAILED": DegradedStateDefinition(
        code="EVAL_FAILED",
        severity="warning",
        user_message="A configured quality evaluation did not pass.",
        recommended_action="Inspect the evaluation report before using the result.",
    ),
    "PRODUCT_DB_UNAVAILABLE": DegradedStateDefinition(
        code="PRODUCT_DB_UNAVAILABLE",
        severity="error",
        user_message="The transactional product database is unavailable.",
        recommended_action="Verify PRODUCT_DB_URL and database access.",
    ),
    "UNSUPPORTED_CRITICAL_CLAIM": DegradedStateDefinition(
        code="UNSUPPORTED_CRITICAL_CLAIM",
        severity="error",
        user_message="One or more critical claims lack evidence support.",
        recommended_action="Review unsupported critical claims and collect additional evidence.",
    ),
    "LOW_EVIDENCE_COVERAGE": DegradedStateDefinition(
        code="LOW_EVIDENCE_COVERAGE",
        severity="warning",
        user_message="The analysis has low evidence coverage.",
        recommended_action="Improve evidence collection to increase claim support ratio.",
    ),
    "WEAK_NVIDIA_FIT_EVIDENCE": DegradedStateDefinition(
        code="WEAK_NVIDIA_FIT_EVIDENCE",
        severity="warning",
        user_message="NVIDIA fit claims have weak or missing evidence.",
        recommended_action=("Collect additional evidence linking the startup to NVIDIA technologies."),
    ),
    "BRIEF_HAS_UNSUPPORTED_CLAIM": DegradedStateDefinition(
        code="BRIEF_HAS_UNSUPPORTED_CLAIM",
        severity="warning",
        user_message="The Action Brief contains unsupported claims.",
        recommended_action="Review brief claims and add supporting evidence before finalizing.",
    ),
    "SCORE_HAS_LOW_EVIDENCE_SUPPORT": DegradedStateDefinition(
        code="SCORE_HAS_LOW_EVIDENCE_SUPPORT",
        severity="warning",
        user_message="A high score is based on low-confidence evidence.",
        recommended_action="Validate the evidence underlying the score before making decisions.",
    ),
    "NO_ACTIVATION_PLAYBOOK_MATCH": DegradedStateDefinition(
        code="NO_ACTIVATION_PLAYBOOK_MATCH",
        severity="warning",
        user_message="No activation playbook matched the diagnosed gaps.",
        recommended_action=("Review gap diagnosis and collect additional evidence to enable a playbook match."),
    ),
    "PLAYBOOK_LOW_EVIDENCE_SUPPORT": DegradedStateDefinition(
        code="PLAYBOOK_LOW_EVIDENCE_SUPPORT",
        severity="warning",
        user_message="Activation playbook match has low evidence support.",
        recommended_action=("Collect additional evidence to increase confidence in the recommended playbook."),
    ),
    "PLAYBOOK_UNSUPPORTED_CLAIMS": DegradedStateDefinition(
        code="PLAYBOOK_UNSUPPORTED_CLAIMS",
        severity="error",
        user_message="Activation playbook matched but critical claims are unsupported.",
        recommended_action=(
            "Review unsupported critical claims and strengthen evidence before proceeding with the playbook."
        ),
    ),
    "DOSSIER_LOW_EVIDENCE_COVERAGE": DegradedStateDefinition(
        code="DOSSIER_LOW_EVIDENCE_COVERAGE",
        severity="warning",
        user_message="The dossier has low evidence coverage.",
        recommended_action="Improve evidence collection and regenerate the dossier.",
    ),
    "DOSSIER_UNSUPPORTED_CRITICAL_CLAIMS": DegradedStateDefinition(
        code="DOSSIER_UNSUPPORTED_CRITICAL_CLAIMS",
        severity="error",
        user_message="The dossier contains unsupported critical claims.",
        recommended_action="Review unsupported claims and collect additional evidence.",
    ),
    "DOSSIER_NO_ACTIVATION_PLAYBOOK": DegradedStateDefinition(
        code="DOSSIER_NO_ACTIVATION_PLAYBOOK",
        severity="warning",
        user_message="The dossier has no matching activation playbook.",
        recommended_action="Review gap diagnosis to enable a playbook match.",
    ),
    "DOSSIER_MISSING_REVIEW": DegradedStateDefinition(
        code="DOSSIER_MISSING_REVIEW",
        severity="info",
        user_message="The dossier has no human review recorded.",
        recommended_action="Record a review decision for this analysis run.",
    ),
    "DOSSIER_INCOMPLETE_SCORES": DegradedStateDefinition(
        code="DOSSIER_INCOMPLETE_SCORES",
        severity="warning",
        user_message="The dossier has one or more missing scores.",
        recommended_action="Inspect pipeline output and rerun analysis if needed.",
    ),
    "QUALITY_LOW_EVIDENCE_COVERAGE": DegradedStateDefinition(
        code="QUALITY_LOW_EVIDENCE_COVERAGE",
        severity="warning",
        user_message="Quality evaluation detected low evidence coverage.",
        recommended_action="Improve evidence collection to increase the support ratio.",
    ),
    "QUALITY_HIGH_UNSUPPORTED_CLAIM_RATE": DegradedStateDefinition(
        code="QUALITY_HIGH_UNSUPPORTED_CLAIM_RATE",
        severity="warning",
        user_message="Quality evaluation shows a high rate of unsupported claims.",
        recommended_action="Review and collect additional evidence for unsupported claims.",
    ),
    "QUALITY_UNSUPPORTED_CRITICAL": DegradedStateDefinition(
        code="QUALITY_UNSUPPORTED_CRITICAL",
        severity="error",
        user_message="Quality evaluation found unsupported critical claims.",
        recommended_action="Collect evidence for all critical claims before proceeding.",
    ),
    "QUALITY_INCOMPLETE_DOSSIER": DegradedStateDefinition(
        code="QUALITY_INCOMPLETE_DOSSIER",
        severity="warning",
        user_message="Quality evaluation found the dossier has missing required sections.",
        recommended_action="Regenerate the dossier after filling missing sections.",
    ),
    "QUALITY_NO_PLAYBOOK": DegradedStateDefinition(
        code="QUALITY_NO_PLAYBOOK",
        severity="warning",
        user_message="Quality evaluation found no activation playbook match.",
        recommended_action="Review gap diagnosis and regenerate playbook recommendations.",
    ),
    "QUALITY_LOW_ACTIONABILITY": DegradedStateDefinition(
        code="QUALITY_LOW_ACTIONABILITY",
        severity="warning",
        user_message="Quality evaluation found recommendations with low actionability.",
        recommended_action=(
            "Review recommendations and ensure motion, next step, experiment, and metrics are defined."
        ),
    ),
    "QUALITY_LOW_EXPORT_READINESS": DegradedStateDefinition(
        code="QUALITY_LOW_EXPORT_READINESS",
        severity="warning",
        user_message="Quality evaluation shows low export readiness score.",
        recommended_action=("Improve dossier quality, evidence coverage, and reduce unsupported claims."),
    ),
    "QUALITY_LOW_REVIEW_READINESS": DegradedStateDefinition(
        code="QUALITY_LOW_REVIEW_READINESS",
        severity="warning",
        user_message="Quality evaluation shows low review readiness score.",
        recommended_action="Complete a human review and improve evidence coverage.",
    ),
    "PLAYBOOK_MISSING_SUCCESS_METRICS": DegradedStateDefinition(
        code="PLAYBOOK_MISSING_SUCCESS_METRICS",
        severity="warning",
        user_message="Activation playbook is missing defined success metrics.",
        recommended_action=("Ensure success metrics are defined before starting the playbook experiment."),
    ),
    "STRUCTURED_OUTPUT_INVALID": DegradedStateDefinition(
        code="STRUCTURED_OUTPUT_INVALID",
        severity="error",
        user_message="A structured output failed schema validation and could not be repaired.",
        recommended_action="Inspect the raw output and schema definition for drift.",
    ),
    "STRUCTURED_OUTPUT_REPAIRED": DegradedStateDefinition(
        code="STRUCTURED_OUTPUT_REPAIRED",
        severity="warning",
        user_message="A structured output was repaired after validation failure.",
        recommended_action="Review the repair to confirm the output is correct.",
    ),
    "STRUCTURED_OUTPUT_RETRY_EXHAUSTED": DegradedStateDefinition(
        code="STRUCTURED_OUTPUT_RETRY_EXHAUSTED",
        severity="error",
        user_message="A structured output exhausted retry attempts without valid repair.",
        recommended_action="Inspect the output source and schema; consider manual review.",
    ),
    "STRUCTURED_OUTPUT_SCHEMA_DRIFT": DegradedStateDefinition(
        code="STRUCTURED_OUTPUT_SCHEMA_DRIFT",
        severity="warning",
        user_message="A structured output field type changed compared to expected schema.",
        recommended_action="Verify the schema contract and update if intentional.",
    ),
    "STRUCTURED_OUTPUT_MISSING_REQUIRED_FIELD": DegradedStateDefinition(
        code="STRUCTURED_OUTPUT_MISSING_REQUIRED_FIELD",
        severity="error",
        user_message="A required field is missing from a structured output.",
        recommended_action="Check the output generator for the missing field.",
    ),
    "WORKFLOW_NODE_FAILED": DegradedStateDefinition(
        code="WORKFLOW_NODE_FAILED",
        severity="error",
        user_message="A workflow node failed during orchestration.",
        recommended_action="Inspect the workflow run and node error messages.",
    ),
    "WORKFLOW_DEGRADED": DegradedStateDefinition(
        code="WORKFLOW_DEGRADED",
        severity="warning",
        user_message="The workflow completed with degraded nodes.",
        recommended_action="Review node status and check optional service availability.",
    ),
    "WORKFLOW_RAG_SKIPPED": DegradedStateDefinition(
        code="WORKFLOW_RAG_SKIPPED",
        severity="warning",
        user_message="RAG retrieval was skipped during workflow execution.",
        recommended_action="Verify RAG configuration and corpus availability.",
    ),
    "WORKFLOW_QUALITY_FAILED": DegradedStateDefinition(
        code="WORKFLOW_QUALITY_FAILED",
        severity="error",
        user_message="Product quality evaluation failed during workflow.",
        recommended_action="Inspect quality run logs and pipeline output integrity.",
    ),
    "WORKFLOW_DOSSIER_MISSING": DegradedStateDefinition(
        code="WORKFLOW_DOSSIER_MISSING",
        severity="warning",
        user_message="Activation dossier was not generated during workflow.",
        recommended_action="Check dossier service availability and analysis run state.",
    ),
    "WORKFLOW_DISCOVERY_PROMOTION_FAILED": DegradedStateDefinition(
        code="WORKFLOW_DISCOVERY_PROMOTION_FAILED",
        severity="warning",
        user_message="Discovery candidate promotion failed during workflow.",
        recommended_action="Verify candidate exists and promotion service is functional.",
    ),
    "OPPORTUNITY_SCORE_UNAVAILABLE": DegradedStateDefinition(
        code="OPPORTUNITY_SCORE_UNAVAILABLE",
        severity="warning",
        user_message="Opportunity score has not been computed for this analysis run.",
        recommended_action="Run opportunity scoring for the analysis run.",
    ),
    "OPPORTUNITY_LOW_CONFIDENCE": DegradedStateDefinition(
        code="OPPORTUNITY_LOW_CONFIDENCE",
        severity="info",
        user_message="Opportunity score has low confidence due to missing or weak evidence.",
        recommended_action=("Collect additional evidence and rerun analysis before making decisions."),
    ),
    "OPPORTUNITY_HIGH_PENALTY": DegradedStateDefinition(
        code="OPPORTUNITY_HIGH_PENALTY",
        severity="warning",
        user_message="Opportunity score has a high penalty total, indicating significant gaps.",
        recommended_action="Review penalties and address top gaps before proceeding.",
    ),
}

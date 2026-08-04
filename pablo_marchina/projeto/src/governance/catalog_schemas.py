from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CandidateStatus(str, Enum):
    ADDED_MAXIMAL_RESEARCH = "ADDED_MAXIMAL_RESEARCH"
    BENCHMARKED = "BENCHMARKED"
    RESEARCHED = "RESEARCHED"
    FUTURE_RESEARCH = "FUTURE_RESEARCH"


class RetentionDecision(str, Enum):
    KEEP_IN_FINAL_SINGLE_CSV = "keep_in_final_single_csv"
    KEEP_IN_MAXIMAL_FINAL_SINGLE_CSV = "keep_in_maximal_final_single_csv"


class FinalFilterAction(str, Enum):
    KEEP = "KEEP"
    KEEP_MAXIMAL_CANDIDATE = "KEEP_MAXIMAL_CANDIDATE"


class ExpectedRuntimeUse(str, Enum):
    ACTIVE_PRODUCT_RUNTIME = "active_product_runtime"
    CANDIDATE_OR_SUPPORTING_GOVERNANCE = "candidate_or_supporting_governance"
    NOT_ACTIVE_RUNTIME = "not_active_runtime"
    AGENTIC_RESEARCH_RUNTIME = (
        "agentic research runtime for retrieval, document navigation, verification, and calculation tools"
    )
    TBD = "TBD_BY_RUNTIME_REVIEW"


class CostPolicy(str, Enum):
    FREE_ONLY_OR_SELF_HOSTED = "FREE_ONLY_OR_SELF_HOSTED; paid tiers/overages disabled"


class MaximalCandidateEntry(BaseModel):
    candidate_id: str
    name: str
    category: str
    status: CandidateStatus = CandidateStatus.ADDED_MAXIMAL_RESEARCH
    marco: str = "TBD_BY_ROADMAP_MAPPING"
    hypothesis: str = ""
    baseline: str = "TBD_BY_BASELINE"
    metrics: list[str] = Field(default_factory=lambda: ["TBD_BY_BENCHMARK"])
    benchmark_type: str = "TBD_BY_BENCHMARK"
    benchmark: str = "TBD_BY_BENCHMARK"
    required_configuration: str = "TBD_BY_CONFIGURATION_REVIEW"
    expected_runtime_use: ExpectedRuntimeUse = ExpectedRuntimeUse.CANDIDATE_OR_SUPPORTING_GOVERNANCE
    cost_to_measure: str = "TBD_BY_BENCHMARK"
    latency_to_measure: str = "TBD_BY_BENCHMARK"
    risks_to_measure: str = "TBD_BY_SECURITY_TESTING"
    gate: str = "check_candidate_catalog_complete"
    evidence_generated: str = "final_case_evidence/benchmark_results.jsonl"
    promotion_criteria: str = ""
    rejection_criteria: str = ""
    removal_criteria: str = ""
    substitute_candidate: str = ""
    substitute_reason: str = ""
    final_filter_action: FinalFilterAction = FinalFilterAction.KEEP_MAXIMAL_CANDIDATE
    final_filter_reason: str = ""
    cost_policy: CostPolicy = CostPolicy.FREE_ONLY_OR_SELF_HOSTED
    allowed_runtime_mode: str = ""
    canonical_technique_name: str = ""
    duplicate_group_id: str = ""
    duplicate_role: str = ""
    technique_family: str = ""
    architecture_tags: str = ""
    risk_coverage_tags: str = ""
    output_improvement_axes: str = ""
    free_self_hosted_verification: str = ""
    license_or_standard: str = ""
    paid_dependency_risk: str = ""
    external_dependency: str = ""
    runtime_eval_governance_role: str = ""
    mutual_exclusivity_group: str = ""
    mutual_exclusivity_reason: str = ""
    final_deduplication_policy: str = ""
    final_duplicate_status: str = ""
    merged_duplicate_candidate_ids: str = ""
    merged_duplicate_names: str = ""
    complementarity_policy: str = ""
    complementarity_family_peers: str = ""
    retention_decision: RetentionDecision = RetentionDecision.KEEP_IN_MAXIMAL_FINAL_SINGLE_CSV
    retention_reason: str = ""
    source_or_reference: str = ""
    maximal_addition_batch: str = ""
    maximal_addition_reason: str = ""


class CandidateModuleMapping(BaseModel):
    candidate_id: str
    module_path: str
    class_name: str
    is_infrastructure: bool = False
    is_external: bool = False

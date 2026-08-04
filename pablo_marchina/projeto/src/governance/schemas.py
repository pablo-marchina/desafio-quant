from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class CandidateStatus(str, Enum):
    DOCUMENTED_CANDIDATE = "DOCUMENTED_CANDIDATE"
    BENCHMARK_CONFIGURED = "BENCHMARK_CONFIGURED"
    BENCHMARKED = "BENCHMARKED"
    PROMOTED_TO_RUNTIME = "PROMOTED_TO_RUNTIME"
    REJECTED_BY_EVIDENCE = "REJECTED_BY_EVIDENCE"
    REMOVED_UNUSED = "REMOVED_UNUSED"
    FUTURE_RESEARCH = "FUTURE_RESEARCH"


class BenchmarkType(str, Enum):
    LOCAL_READINESS = "LOCAL_READINESS"
    PROXY = "PROXY"
    OUTPUT_VALUE = "OUTPUT_VALUE"
    PRODUCTION_QUALITY = "PRODUCTION_QUALITY"
    SECURITY = "SECURITY"
    COST_LATENCY = "COST_LATENCY"
    COMPLIANCE = "COMPLIANCE"
    REPRODUCIBILITY = "REPRODUCIBILITY"


class PurposeCategory(str, Enum):
    PRODUCT_RUNTIME = "Product Runtime"
    PRODUCT_CONFIGURATION = "Product Configuration"
    PRODUCT_TESTS = "Product Tests"
    BENCHMARK_LAB = "Benchmark Lab"
    DELIVERY_DOCUMENTATION = "Delivery Documentation"
    GOVERNANCE_EVIDENCE = "Governance Evidence"
    SECURITY_RELEASE_INFRASTRUCTURE = "Security/Release Infrastructure"
    ARCHIVED_HISTORICAL_MATERIAL = "Archived Historical Material"


class KeepOrRemove(str, Enum):
    KEEP = "keep"
    REMOVE = "remove"
    ARCHIVE = "archive"
    REVIEW = "review"


class EvidenceKind(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    UNVERIFIED = "unverified"


class RiskStatus(str, Enum):
    OPEN = "open"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class BenchmarkCandidateEntry(BaseModel):
    candidate_id: str
    name: str
    category: str
    status: CandidateStatus = CandidateStatus.DOCUMENTED_CANDIDATE
    marco: str = "TBD_BY_ROADMAP"
    hypothesis: str = "TBD_BY_BENCHMARK"
    baseline: str = "TBD_BY_BASELINE"
    metrics: list[str] = Field(default_factory=list)
    benchmark_type: BenchmarkType = BenchmarkType.LOCAL_READINESS
    benchmark: str = "TBD_BY_BENCHMARK"
    required_configuration: str = "TBD_BY_CONFIGURATION_REVIEW"
    expected_runtime_use: str = "TBD_BY_RUNTIME_REVIEW"
    cost_to_measure: str = "TBD_BY_BENCHMARK"
    latency_to_measure: str = "TBD_BY_BENCHMARK"
    risks_to_measure: str = "TBD_BY_SECURITY_TESTING"
    gate: str = "check_candidate_catalog_complete"
    evidence_generated: str = "final_case_evidence/candidate_catalog.csv"
    promotion_criteria: str = "TBD_BY_BENCHMARK"
    rejection_criteria: str = "TBD_BY_BENCHMARK"
    removal_criteria: str = "TBD_BY_REPOSITORY_CLEANLINESS"
    substitute_candidate: str | None = None
    substitute_reason: str | None = None
    free_self_hosted_verification: str = ""
    source_or_reference: str = ""
    external_dependency: str = ""
    cost_policy: str = ""

    @field_validator("candidate_id", "name", "category")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _promotion_requires_evidence(self) -> BenchmarkCandidateEntry:
        if self.status == CandidateStatus.PROMOTED_TO_RUNTIME:
            missing = [
                value
                for value in (
                    self.benchmark,
                    self.evidence_generated,
                    self.promotion_criteria,
                )
                if value.startswith("TBD_")
            ]
            if missing:
                raise ValueError("runtime promotion requires benchmark evidence and criteria")
        return self


class DecisionLedgerEntry(BaseModel):
    decision_id: str
    item_name: str
    category: str
    status: CandidateStatus
    decision: str
    evidence_reference: str
    hypothesis: str = "TBD_BY_BENCHMARK"
    baseline: str = "TBD_BY_BASELINE"
    metric_names: list[str] = Field(default_factory=list)
    benchmark_type: BenchmarkType = BenchmarkType.REPRODUCIBILITY
    benchmark_result_ref: str | None = None
    owner: str = "product"
    decided_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _runtime_decision_requires_benchmark(self) -> DecisionLedgerEntry:
        if self.status == CandidateStatus.PROMOTED_TO_RUNTIME and not self.benchmark_result_ref:
            raise ValueError("PROMOTED_TO_RUNTIME decisions require benchmark_result_ref")
        return self


class CalibrationRegistryEntry(BaseModel):
    calibration_id: str
    metric_name: str
    value: str | float | int
    unit: str
    decision_area: str
    dataset_version: str
    corpus_version: str
    pipeline_version: str
    experiment_run_id: str
    git_commit: str
    baseline_result: str
    candidate_result: str
    statistical_method: str
    uncertainty_method: str
    calibration_method: str
    calibration_date: str
    reviewer_or_approver: str
    validity_period: str
    recalibration_trigger: str
    production_allowed: bool = False


class RuntimeBOMEntry(BaseModel):
    component_id: str
    name: str
    category: str
    version_or_source: str
    status: CandidateStatus
    runtime_role: str
    configuration_ref: str
    benchmark_ref: str
    decision_ref: str
    owner: str = "product"

    @model_validator(mode="after")
    def _runtime_bom_requires_promotion(self) -> RuntimeBOMEntry:
        if self.runtime_role != "documentation_only" and self.status != CandidateStatus.PROMOTED_TO_RUNTIME:
            raise ValueError("runtime BOM entries with active runtime roles must be PROMOTED_TO_RUNTIME")
        return self


class RepositoryPurposeEntry(BaseModel):
    path: str
    category: PurposeCategory
    purpose: str
    owner: str
    runtime_or_documentation_role: str
    runtime_role: str = "none"
    documentation_role: str = "none"
    evidence_role: str = "none"
    keep_or_remove: KeepOrRemove
    justification: str = "Purpose is documented in the repository final delivery evidence."
    evidence_reference: str


class ComponentStatusEntry(BaseModel):
    component_id: str
    component_name: str
    status: CandidateStatus
    reason: str
    evidence_reference: str
    updated_at: datetime = Field(default_factory=utc_now)


class EvidenceRecord(BaseModel):
    evidence_id: str
    source_url: str
    collected_at: datetime = Field(default_factory=utc_now)
    evidence_kind: EvidenceKind
    claim: str
    support_text: str
    confidence: str
    lineage_ref: str


class RiskRecord(BaseModel):
    risk_id: str
    risk_area: str
    description: str
    detection_method: str
    mitigation: str
    owner: str
    status: RiskStatus = RiskStatus.OPEN
    residual_risk_status: str = "TBD_BY_SECURITY_POLICY"


class IncidentRecord(BaseModel):
    incident_id: str
    severity: str
    detection_method: str
    impact: str
    immediate_action: str
    rollback: str
    owner: str
    root_cause: str
    regression_test_added: bool
    prevention: str
    status: str


class RCARecord(BaseModel):
    failure_id: str
    failure_type: str
    affected_run: str
    root_cause: str
    impact: str
    fix: str
    regression_test_added: bool
    metric_affected: str
    owner: str
    status: str


class GateReport(BaseModel):
    gate_id: str
    status: str
    generated_at: datetime = Field(default_factory=utc_now)
    checked_items: int
    failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status.upper() == "PASS"

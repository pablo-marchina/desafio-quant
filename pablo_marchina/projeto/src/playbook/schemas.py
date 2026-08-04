from __future__ import annotations

from pydantic import BaseModel, Field


class ExperimentDefinition(BaseModel):
    title: str
    hypothesis: str
    description: str
    duration: str


class ConfidenceRules(BaseModel):
    requires_gap_match: bool = True
    evidence_coverage_boost: bool = True
    unsupported_claim_penalty: bool = True
    min_evidence_coverage: float = 0.3


class OutputTemplate(BaseModel):
    section_title: str
    fields: list[str]


class ActivationPlaybook(BaseModel):
    playbook_id: str
    name: str
    description: str
    target_gap_types: list[str]
    target_claim_types: list[str]
    nvidia_technologies: list[str]
    technical_experiment: ExperimentDefinition
    success_metrics: list[str]
    recommended_motion: str
    prerequisites: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    expected_value: str
    implementation_complexity: str
    confidence_rules: ConfidenceRules
    output_template: OutputTemplate
    version: str


class ActivationPlaybookMatch(BaseModel):
    playbook_id: str
    playbook_name: str
    matched_gap_types: list[str]
    matched_claim_ids: list[str] = Field(default_factory=list)
    gap_confidence: str
    evidence_coverage: float
    unsupported_claim_count: int = 0
    raw_score: float
    confidence: str
    reasoning: str


class ActivationRecommendationSchema(BaseModel):
    analysis_run_id: str
    playbook_id: str
    playbook_name: str
    matched_gap_types: list[str]
    matched_claim_ids: list[str]
    nvidia_technologies: list[str]
    technical_experiment: str
    success_metrics: list[str]
    recommended_motion: str
    priority: int
    confidence: str
    reasoning: str
    evidence_refs: list[dict]
    risks: list[str]
    next_step: str


class ActivationPlaybookListResponse(BaseModel):
    playbooks: list[ActivationPlaybook]
    total: int

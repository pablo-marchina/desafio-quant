"""Schemas for optional LLM judge answer quality reports.

The judge is experimental and must not be used as a CI gate. The default provider
is a deterministic null provider that performs no external calls.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class LLMJudgeResultStatus(StrEnum):
    """Execution status for one optional judge case."""

    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class LLMJudgeProviderConfig(BaseModel):
    """Configuration for an optional judge provider."""

    provider_name: str = "null"
    enabled: bool = False
    model_name: str | None = None
    temperature: float = 0.0
    timeout_seconds: int = 60
    max_cases: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class LLMJudgeInput(BaseModel):
    """Structured input for judging one final RAG/Action Brief answer."""

    case_id: str
    case_description: str
    pipeline_case_id: str
    answer_text: str
    startup_evidence: list[dict[str, Any]] = Field(default_factory=list)
    rag_contexts: list[dict[str, Any]] = Field(default_factory=list)
    diagnosed_gaps: list[dict[str, Any]] = Field(default_factory=list)
    nvidia_technology_candidates: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    uncertainties: list[dict[str, Any] | str] = Field(default_factory=list)
    deterministic_metrics: dict[str, Any] = Field(default_factory=dict)


class LLMJudgeScore(BaseModel):
    """Optional semantic judge scores for one answer."""

    faithfulness_score: float = Field(ge=0.0, le=1.0)
    answer_relevancy_score: float = Field(ge=0.0, le=1.0)
    groundedness_score: float = Field(ge=0.0, le=1.0)
    completeness_score: float = Field(ge=0.0, le=1.0)
    uncertainty_honesty_score: float = Field(ge=0.0, le=1.0)
    executive_usefulness_score: float = Field(ge=0.0, le=1.0)
    judge_confidence: float = Field(ge=0.0, le=1.0)
    judge_rationale: str
    judge_flags: list[str] = Field(default_factory=list)


class LLMJudgeResult(BaseModel):
    """Optional judge result for one answer quality case."""

    case_id: str
    provider_name: str
    model_name: str | None = None
    score: LLMJudgeScore
    prompt_version: str
    raw_response: str | None = None
    errors: list[str] = Field(default_factory=list)
    status: LLMJudgeResultStatus = LLMJudgeResultStatus.COMPLETED


class LLMJudgeRunReport(BaseModel):
    """Run-level optional LLM judge report."""

    report_version: str = "1.0"
    generated_at: str
    provider: LLMJudgeProviderConfig
    input_source: str
    total_cases: int
    completed_cases: int
    skipped_cases: int
    error_cases: int
    results: list[LLMJudgeResult] = Field(default_factory=list)
    summary: dict[str, float | int | str] = Field(default_factory=dict)
    is_ci_gate: bool = False

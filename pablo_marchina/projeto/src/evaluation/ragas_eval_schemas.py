"""Pydantic schemas for RAGAS Evaluation Harness — golden dataset, metrics, and reports.

This module defines the data contract between the RAGAS evaluator and:
  - Golden dataset on disk (data/eval/golden_ragas_rag.json)
  - Decision Calibration Registry (src/quality/decision_calibration_registry.py)
  - Unit tests (tests/evals/test_ragas_eval.py)

No external dependencies beyond Pydantic.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoldenContext(BaseModel):
    chunk_id: str = ""
    source_id: str = ""
    title: str = ""
    content: str = ""
    product: str = ""
    gap_types: list[str] = Field(default_factory=list)
    url: str | None = None
    relevance_score: float = 0.0


class RagasEvalGoldenSample(BaseModel):
    question: str
    gap_id: str
    gap_type: str
    expected_nvidia_topics: list[str] = Field(default_factory=list)
    expected_context_ids: list[str] = Field(default_factory=list)
    expected_evidence_markers: list[str] = Field(default_factory=list)
    ground_truth_answer: str | None = None
    retrieved_contexts: list[GoldenContext] = Field(default_factory=list)
    generated_answer: str | None = None
    recommendation_text: str | None = None
    metadata: dict = Field(default_factory=dict)


class RagasEvalDataset(BaseModel):
    samples: list[RagasEvalGoldenSample] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class CustomEvalMetrics(BaseModel):
    citation_precision: float = 0.0
    unsupported_claim_rate: float = 0.0
    retrieved_context_count: int = 0
    contexts_per_gap: dict[str, int] = Field(default_factory=dict)
    gaps_without_context_count: int = 0
    rag_blocker_count: int = 0


class RagasComputedMetrics(BaseModel):
    context_precision: float | None = None
    context_recall: float | None = None
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    metrics_source: str = "unavailable"


class RagasEvalReport(BaseModel):
    metric_name: str
    score: float
    sample_count: int
    confidence_interval: tuple[float, float] | None = None
    failed_examples: list[str] = Field(default_factory=list)
    calibration_recommendation: str = ""
    production_allowed_recommendation: bool = False


class RagasEvalResult(BaseModel):
    dataset_size: int = 0
    dataset_sufficient: bool = False
    calibration_status: str = "baseline_dataset_insufficient"
    production_allowed: bool = False
    custom_metrics: CustomEvalMetrics = Field(default_factory=CustomEvalMetrics)
    ragas_metrics: RagasComputedMetrics | None = None
    reports: list[RagasEvalReport] = Field(default_factory=list)
    calibration_decisions: dict[str, dict] = Field(default_factory=dict)


MINIMUM_GOLDEN_SAMPLES: int = 10
"""Minimum number of golden samples required for a sufficient dataset."""

MINIMUM_GAP_TYPES_COVERED: int = 3
"""Minimum distinct gap types required for a sufficient dataset."""

REQUIRED_SAMPLE_FIELDS: set[str] = {
    "question",
    "gap_id",
    "gap_type",
    "expected_nvidia_topics",
}
"""Fields that every golden sample must have (others are optional)."""

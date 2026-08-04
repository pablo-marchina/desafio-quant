"""Pydantic schemas for Qdrant retrieval evaluation — per-retriever metrics and comparison.

Defines the data contract between QdrantRetrievalEvaluator and:
  - Golden dataset (data/eval/golden_ragas_rag.json)
  - Decision Calibration Registry (src/quality/decision_calibration_registry.py)
  - Unit tests (tests/evals/test_qdrant_retrieval_eval.py)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrieverMetrics(BaseModel):
    """Custom + RAGAS metrics computed for a single retriever on the golden set."""

    retriever_name: str = ""
    sample_count: int = 0

    context_precision: float | None = None
    context_recall: float | None = None
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    ragas_metrics_source: str = "unavailable"

    recall_at_k: float = 0.0
    precision_at_k: float = 0.0
    mrr: float = 0.0
    hit_rate_at_k: float = 0.0
    retrieved_context_count: int = 0
    contexts_per_gap: dict[str, int] = Field(default_factory=dict)
    gaps_without_context_count: int = 0
    citation_precision: float = 1.0
    unsupported_claim_rate: float = 0.0

    latency_ms: float = 0.0
    qdrant_payload_completeness_rate: float = 1.0
    corpus_version_match_rate: float = 1.0


class PerGapMetrics(BaseModel):
    """Per-gap-type metrics for a single retriever."""

    gap_type: str
    contexts_retrieved: int = 0
    unique_sources: int = 0
    citation_precision: float = 1.0
    unsupported_claim_rate: float = 0.0


class RetrieverDetail(BaseModel):
    """Detailed evaluation result for one retriever."""

    summary: RetrieverMetrics = Field(default_factory=lambda: RetrieverMetrics(retriever_name=""))
    per_gap: list[PerGapMetrics] = Field(default_factory=list)
    failed_examples: list[str] = Field(default_factory=list)
    production_readiness_recommendation: str = ""


class RetrievalComparison(BaseModel):
    """Side-by-side comparison across retrievers."""

    multi_objective_scores: dict[str, float] = Field(default_factory=dict)
    winner: str = ""
    selection_justification: str = ""
    dataset_sufficient: bool = False
    production_allowed: bool = False


class QdrantRetrievalEvalResult(BaseModel):
    """Top-level result from QdrantRetrievalEvaluator.evaluate()."""

    dataset_size: int = 0
    dataset_sufficient: bool = False
    calibration_status: str = "baseline_dataset_insufficient"

    semantic: RetrieverDetail = Field(default_factory=lambda: RetrieverDetail())
    lexical: RetrieverDetail = Field(default_factory=lambda: RetrieverDetail())
    hybrid: RetrieverDetail = Field(default_factory=lambda: RetrieverDetail())
    comparison: RetrievalComparison = Field(default_factory=RetrievalComparison)

    calibration_decisions: dict[str, dict] = Field(default_factory=dict)
    qdrant_available: bool = False
    qdrant_unavailable_reason: str = ""


MINIMUM_GOLDEN_SAMPLES: int = 10
MINIMUM_GAP_TYPES_COVERED: int = 3

MULTI_OBJECTIVE_WEIGHTS: dict[str, float] = {
    "context_recall": 0.40,
    "context_precision": 0.30,
    "unsupported_claim_inverse": 0.10,
    "mrr": 0.10,
    "hit_rate": 0.10,
}

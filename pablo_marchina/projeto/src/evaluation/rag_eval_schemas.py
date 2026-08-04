"""Schemas for RAG Evaluation — retrieval metrics and quality gates.

Epic 13 adds: RetrievalMode, ModeEvalResult, RagEvalComparison.
Epic 14 adds: HYBRID_RERANKED, HYBRID_RERANKED_PACKED + 8 metrics.
The active corpus can grow beyond the original golden set, so each case can
separate required sources from additional allowed sources.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.rag.schemas import RetrievalQuery, RetrievedContext


class RetrievalMode(str, Enum):
    """Retrieval mode identifier for multi-mode evaluation."""

    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    HYBRID_RERANKED = "hybrid_reranked"
    HYBRID_RERANKED_PACKED = "hybrid_reranked_packed"


class RagEvalCase(BaseModel):
    """A golden query case for RAG evaluation.

    ``expected_*`` values are required for coverage. ``allowed_*`` values
    define the wider relevance boundary used for precision and top-1 checks.
    When no allowed values are supplied, expected values remain authoritative.
    """

    case_id: str
    description: str
    query: RetrievalQuery
    expected_source_ids: list[str] = Field(default_factory=list)
    expected_products: list[str] = Field(default_factory=list)
    allowed_source_ids: list[str] = Field(default_factory=list)
    allowed_products: list[str] = Field(default_factory=list)
    is_critical: bool = False
    top_k_for_test: int = 3


class RagRetrievalMetrics(BaseModel):
    """Metrics computed from a single retrieval result against golden expectations.

    Epic 12: 7 metrics (hit_at_k through context_precision).
    Epic 14: +8 metrics (duplicate_context_count through noise_reduction_score).
    """

    hit_at_k: bool = False
    expected_source_coverage: float = 0.0
    expected_product_coverage: float = 0.0
    irrelevant_context_count: int = 0
    missing_context_count: int = 0
    top_1_expected_match: bool = False
    context_precision: float = 0.0
    duplicate_context_count: int = 0
    packed_context_count: int = 0
    dropped_context_count: int = 0
    provenance_coverage: float = 0.0
    context_budget_used: float = 0.0
    gap_coverage: float = 0.0
    technology_coverage: float = 0.0
    noise_reduction_score: float = 0.0


class RagEvalResult(BaseModel):
    """Result of evaluating a single golden query."""

    case_id: str
    case_description: str
    passed: bool
    is_critical: bool = False
    metrics: RagRetrievalMetrics
    retrieved_contexts: list[RetrievedContext] = Field(default_factory=list)
    expected_source_ids: list[str] = Field(default_factory=list)
    expected_products: list[str] = Field(default_factory=list)
    allowed_source_ids: list[str] = Field(default_factory=list)
    allowed_products: list[str] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)


class RagQualityGateResult(BaseModel):
    """Result of a single quality gate."""

    gate_name: str
    passed: bool
    details: str
    failed_cases: list[str] = Field(default_factory=list)


class ModeEvalResult(BaseModel):
    """Evaluation results for a single retrieval mode."""

    mode: RetrievalMode
    results: list[RagEvalResult]
    gates: list[RagQualityGateResult]
    passed_cases: int = 0
    total_cases: int = 0


class RagEvalComparison(BaseModel):
    """Side-by-side comparison of all retrieval modes."""

    lexical: ModeEvalResult
    semantic: ModeEvalResult
    hybrid: ModeEvalResult
    hybrid_reranked: ModeEvalResult = Field(
        default_factory=lambda: ModeEvalResult(
            mode=RetrievalMode.HYBRID_RERANKED,
            results=[],
            gates=[],
        )
    )
    hybrid_reranked_packed: ModeEvalResult = Field(
        default_factory=lambda: ModeEvalResult(
            mode=RetrievalMode.HYBRID_RERANKED_PACKED,
            results=[],
            gates=[],
        )
    )
    critical_regressions: list[str] = Field(default_factory=list)
    """Case IDs where semantic or hybrid regressed vs lexical on a critical query."""

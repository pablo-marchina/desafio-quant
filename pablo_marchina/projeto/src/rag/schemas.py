"""Schemas for Product RAG module.

Epic 14 adds: RerankingConfig, PackedContext, DroppedContext, PackingResult,
SupportingNvidiaContext.

Epic 42 adds: RetrievalMode, RagEvidenceChunk, QueryPlan, RagEvidenceChunkList.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RagSource(BaseModel):
    source_id: str
    title: str
    url: str | None = None
    product: str
    gap_types: list[str] = Field(default_factory=list)
    version: str = "1.0"
    document_type: str = "nvidia_corpus"
    content_hash: str | None = None
    previous_content_hash: str | None = None
    collected_at: str | None = None
    last_checked_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    freshness_policy: str | None = None
    stale_after_days: int | None = None
    is_active: bool = True
    deprecated_at: str | None = None
    superseded_by: str | None = None
    deprecation_reason: str | None = None


class RagDocument(BaseModel):
    source_id: str
    title: str
    raw_text: str


class RagChunk(BaseModel):
    chunk_id: str
    source_id: str
    title: str
    content: str
    product: str
    gap_types: list[str] = Field(default_factory=list)
    url: str | None = None
    version: str = "1.0"
    document_type: str = "nvidia_corpus"
    content_hash: str | None = None
    previous_content_hash: str | None = None
    collected_at: str | None = None
    last_checked_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    freshness_policy: str | None = None
    stale_after_days: int | None = None
    is_active: bool = True
    deprecated_at: str | None = None
    superseded_by: str | None = None
    deprecation_reason: str | None = None
    nvidia_technology: str = ""
    corpus_version: str = "1.0"
    chunk_index: int = 0
    char_count: int = 0


class RetrievalQuery(BaseModel):
    technology: str | None = None
    gap_type: str | None = None
    keywords: list[str] = Field(default_factory=list)
    include_deprecated: bool = False
    include_expired: bool = False
    include_stale: bool = False


class RetrievedContext(BaseModel):
    chunk_id: str
    source_id: str
    title: str
    content: str
    product: str
    gap_types: list[str] = Field(default_factory=list)
    url: str | None = None
    relevance_score: float = 0.0
    version: str = "1.0"
    collected_at: str | None = None
    last_checked_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    freshness_policy: str | None = None
    stale_after_days: int | None = None
    is_active: bool = True
    deprecated_at: str | None = None
    superseded_by: str | None = None


class PlaybookRetrievalResult(BaseModel):
    query: RetrievalQuery
    contexts: list[RetrievedContext] = Field(default_factory=list)
    total_found: int = 0
    missing_context: bool = False
    reasoning: str = ""


# ------------------------------------------------------------------
# Epic 14 — Reranking + Context Packing schemas
# ------------------------------------------------------------------


class TechniquesConfig(BaseModel):
    """Runtime config for catalog techniques. Each attribute is a module
    name; default True (enabled). Set to False to skip a technique."""


class ClaimVerificationConfig(BaseModel):
    enabled: bool = True


class RAGFusionConfig(BaseModel):
    use_nvidia_llm: bool = True
    max_variants: int = 4
    fusion_top_k: int = 20


class SelfRAGConfig(BaseModel):
    enabled: bool = True
    relevance_threshold: float = 0.5
    max_retries: int = 3


class CorrectiveRAGConfig(BaseModel):
    enabled: bool = True
    quality_threshold: float = 0.6
    max_correction_rounds: int = 2


class RerankingConfig(BaseModel):
    boost_gap_match: float = 0.3
    boost_technology_match: float = 0.2
    penalty_no_provenance: float = -0.5
    penalty_duplicate: float = -0.3
    penalty_irrelevant: float = -0.2
    boost_known_source: float = 0.1


class PackedContext(BaseModel):
    chunk_id: str
    source_id: str
    title: str
    content: str
    product: str
    gap_types: list[str] = Field(default_factory=list)
    url: str | None = None
    relevance_score: float = 0.0
    rerank_score: float = 0.0
    matched_gap: str | None = None
    matched_technology: str | None = None
    version: str = "1.0"
    valid_from: str | None = None
    valid_until: str | None = None
    freshness_policy: str | None = None
    stale_after_days: int | None = None
    is_active: bool = True
    deprecated_at: str | None = None
    superseded_by: str | None = None


class DroppedContext(BaseModel):
    chunk_id: str
    reason: str
    rerank_score: float = 0.0


class PackingConfig(BaseModel):
    max_total: int = 5
    max_per_technology: int = 2
    max_per_gap: int = 3


class PackingResult(BaseModel):
    packed: list[PackedContext] = Field(default_factory=list)
    dropped: list[DroppedContext] = Field(default_factory=list)
    total_raw: int = 0
    total_packed: int = 0
    total_dropped: int = 0
    provenance_coverage: float = 0.0
    gap_coverage: float = 0.0
    technology_coverage: float = 0.0
    context_budget_used: float = 0.0
    noise_reduction_score: float = 0.0


class SupportingNvidiaContext(BaseModel):
    gap_type: str
    technology: str
    contexts: list[PackedContext] = Field(default_factory=list)
    total_available: int = 0
    total_dropped: int = 0


class RagPipelineOutput(BaseModel):
    packing_result: PackingResult | None = None
    retrieval_mode: str = "lexical"
    missing_context: bool = True
    rag_quality_summary: str = ""


# ------------------------------------------------------------------
# Epic 42 — Hybrid RAG + Reranking Hardening schemas
# ------------------------------------------------------------------


class RetrievalMode(str, Enum):
    DENSE_ONLY = "dense_only"
    SPARSE_ONLY = "sparse_only"
    HYBRID = "hybrid"
    HYBRID_WITH_RERANK = "hybrid_with_rerank"
    # Legacy mode aliases
    LEXICAL = "lexical"
    SEMANTIC = "semantic"


class RagEvidenceChunk(BaseModel):
    """A single evidence chunk returned by the Hybrid RAG retriever.

    Carries full provenance, per-mode scores, and retrieval metadata
    for consumption by Claim Ledger, Dossier, and Product Quality.
    """

    chunk_id: str
    source_title: str
    source_url: str | None = None
    section: str = ""
    text: str
    score_dense: float = 0.0
    score_sparse: float = 0.0
    score_fused: float = 0.0
    score_rerank: float = 0.0
    retrieval_mode: str = "hybrid_with_rerank"
    corpus_version: str = "1.0"
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class QueryPlan(BaseModel):
    """Deterministic query plan produced by RagQueryPlanner."""

    primary_query: str = ""
    keyword_query: str = ""
    technology_filters: list[str] = Field(default_factory=list)
    target_doc_categories: list[str] = Field(default_factory=list)
    must_have_terms: list[str] = Field(default_factory=list)
    optional_terms: list[str] = Field(default_factory=list)
    metadata_filters: dict[str, str] = Field(default_factory=dict)


class RagEvidenceChunkList(BaseModel):
    """Collection of evidence chunks with aggregate metadata."""

    chunks: list[RagEvidenceChunk] = Field(default_factory=list)
    retrieval_mode: str = "dense_only"
    total_raw: int = 0
    total_returned: int = 0
    fallback_reason: str = ""
    degraded: bool = False

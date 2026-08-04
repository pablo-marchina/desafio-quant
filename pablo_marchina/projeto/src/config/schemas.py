"""Pydantic schemas for YAML configuration files."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    confidence: float = 0.30
    business_impact: float = 0.25
    implementation_complexity_inverse: float = 0.20
    rag_support: float = 0.15
    evidence_support: float = 0.10


class OpportunityWeights(BaseModel):
    defensibility: float = 0.30
    inception_fit: float = 0.25
    production_readiness: float = 0.35
    classification: float = 0.10


class ProductionReadinessWeights(BaseModel):
    real_users: float = 0.30
    scale_inference: float = 0.30
    privacy_governance: float = 0.20
    data_infrastructure: float = 0.20


class DefensibilityWeights(BaseModel):
    ai_core: float = 0.25
    proprietary_data: float = 0.20
    workflow_integration: float = 0.15
    real_usage: float = 0.15
    replication_barrier: float = 0.15
    nvidia_fit: float = 0.10


class InceptionFitWeights(BaseModel):
    gap_taxonomy: float = 0.35
    vertical_alignment: float = 0.25
    technical_maturity: float = 0.20
    revenue_potential: float = 0.20


class ConfidenceThresholds(BaseModel):
    high_min: float = 0.7
    medium_min: float = 0.4


class ConfidenceFloatMap(BaseModel):
    high: float = 1.0
    medium: float = 0.6
    low: float = 0.3


class ConfidenceScoreFactors(BaseModel):
    high: float = 1.0
    medium: float = 0.7
    low: float = 0.4


class ConfidenceConfig(BaseModel):
    thresholds: ConfidenceThresholds = Field(default_factory=ConfidenceThresholds)
    float_map: ConfidenceFloatMap = Field(default_factory=ConfidenceFloatMap)
    score_factors: ConfidenceScoreFactors = Field(default_factory=ConfidenceScoreFactors)
    penalty_on_missing: float = 0.15
    max_signal_boost: float = 0.6
    no_evidence_factor: float = 0.3


class ClassificationConfig(BaseModel):
    base_scores: dict[str, float] = {
        "non_ai": 0, "ai_assisted": 25, "ai_enabled": 50,
        "ai_native": 80, "ai_native_service": 85,
    }


class KeywordBoosts(BaseModel):
    nvidia_specific: float = 0.25
    llm_generative: float = 0.20
    ml_dl_nlp_gpu: float = 0.15
    framework_mlops: float = 0.10
    data_science: float = 0.05


class ScoringConfig(BaseModel):
    priority_score: ScoringWeights = Field(default_factory=ScoringWeights)
    opportunity_score: OpportunityWeights = Field(default_factory=OpportunityWeights)
    production_readiness: ProductionReadinessWeights = Field(default_factory=ProductionReadinessWeights)
    defensibility: DefensibilityWeights = Field(default_factory=DefensibilityWeights)
    inception_fit: InceptionFitWeights = Field(default_factory=InceptionFitWeights)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    classification: ClassificationConfig = Field(default_factory=ClassificationConfig)
    keyword_boosts: KeywordBoosts = Field(default_factory=KeywordBoosts)


class SourceTypeScores(BaseModel):
    official_site: float = 1.0
    news: float = 0.8
    founder_profile: float = 0.7
    blog: float = 0.6
    job_post: float = 0.5
    directory: float = 0.4


class DiscoveryConfidenceWeights(BaseModel):
    has_name: float = 0.3
    has_website: float = 0.1
    is_manual_seed: float = 0.2
    source_reliable: float = 0.1


class RateLimitConfig(BaseModel):
    requests_per_second: int = 2
    concurrent_requests: int = 1


class SourceQualityConfig(BaseModel):
    source_types: SourceTypeScores = Field(default_factory=SourceTypeScores)
    discovery: dict = Field(default_factory=lambda: {"max_sources": 10, "max_search_depth": 2})
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    gap_business_impact: dict[str, float] = Field(default_factory=dict)


class BM25Config(BaseModel):
    k1: float = 1.5
    b: float = 0.75
    top_k: int = 20


class DenseConfig(BaseModel):
    model: str = "all-MiniLM-L6-v2"
    dimension: int = 384
    top_k: int = 20
    similarity: str = "cosine"


class HybridConfig(BaseModel):
    rrf_k: int = 60
    dense_weight: float = 0.5
    sparse_weight: float = 0.5
    top_k: int = 20


class ChunkingConfig(BaseModel):
    chunk_size: int = 512
    overlap: int = 64
    strategy: str = "recursive"
    semantic_chunking: bool = False
    parent_child: bool = False


class RagRetrievalConfig(BaseModel):
    bm25: BM25Config = Field(default_factory=BM25Config)
    dense: DenseConfig = Field(default_factory=DenseConfig)
    hybrid: HybridConfig = Field(default_factory=HybridConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)


class RerankerConfig(BaseModel):
    active: bool = True
    model: str = "BAAI/bge-reranker-v2-m3"
    provider: str = "cross_encoder"
    top_k_after_rerank: int = 10
    candidates_before_rerank: int = 50


class DeterministicBoosts(BaseModel):
    gap_match_boost: float = 0.15
    technology_match_boost: float = 0.15
    provenance_boost: float = 0.10
    recency_boost: float = 0.05
    dedup_enabled: bool = True


class RerankingConfig(BaseModel):
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    deterministic: DeterministicBoosts = Field(default_factory=DeterministicBoosts)


class QualityGates(BaseModel):
    unsupported_critical_claims_max: int = 0
    blockers_max: int = 0
    evidence_items_min: int = 1
    rag_contexts_min: int = 1
    recommendations_min: int = 1


class RetrievalThresholds(BaseModel):
    recall_at_5_min: float = 0.5
    recall_at_10_min: float = 0.6
    recall_at_20_min: float = 0.7
    mrr_min: float = 0.5
    ndcg_min: float = 0.5


class RagThresholds(BaseModel):
    faithfulness_min: float = 0.6
    groundedness_min: float = 0.5
    answer_relevancy_min: float = 0.5
    citation_precision_min: float = 0.5
    hallucination_max: float = 0.2


class WorkflowThresholds(BaseModel):
    max_evidence_retries: int = 3
    min_rag_contexts: int = 1
    min_evidence_items: int = 1
    min_recommendations: int = 1
    min_supported_claims: int = 1
    rag_required: bool = True


class EvalThresholdsConfig(BaseModel):
    quality_gates: QualityGates = Field(default_factory=QualityGates)
    retrieval: RetrievalThresholds = Field(default_factory=RetrievalThresholds)
    rag: RagThresholds = Field(default_factory=RagThresholds)
    workflow: WorkflowThresholds = Field(default_factory=WorkflowThresholds)


class LLMRoute(BaseModel):
    provider: str
    model: str
    rationale: str = ""
    max_tokens: int = 4096
    temperature: float = 0.1
    fallback_provider: str | None = None
    fallback_model: str | None = None


class LLMRoutingConfig(BaseModel):
    routing: dict[str, LLMRoute] = Field(default_factory=dict)


class SignalBoostItem(BaseModel):
    pattern: str
    label: str
    boost: float


class KeywordsConfig(BaseModel):
    gap_keyword_dict: dict[str, list[str]] = Field(default_factory=dict)
    knowledge_base_signal_boosts: list[SignalBoostItem] = Field(default_factory=list)
    nvidia_keyword_boosts: dict[str, float] = Field(default_factory=dict)

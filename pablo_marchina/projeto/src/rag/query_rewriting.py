"""Deterministic query rewriting and multi-query retrieval for RAG product spikes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext


class QueryRewriteConfig(BaseModel):
    """Opt-in config for deterministic query rewriting.

    This is a product spike config, not default runtime behavior.
    """

    enabled: bool = True
    max_variants: int = 4
    max_keywords_per_variant: int = 12
    score_variant_bonus: float = 0.03


_GAP_KEYWORDS: dict[str, tuple[str, ...]] = {
    "high_inference_cost": ("inference", "latency", "throughput", "gpu", "optimization"),
    "high_latency": ("latency", "real-time", "inference", "triton", "serving"),
    "external_api_dependency": ("deployment", "self-hosted", "nim", "endpoint", "inference"),
    "agent_governance_gap": ("guardrails", "safety", "policy", "agent", "governance"),
    "slow_data_pipeline": ("rapids", "gpu", "dataframe", "etl", "acceleration"),
    "voice_need": ("speech", "voice", "asr", "tts", "riva"),
}

_TECH_SYNONYMS: dict[str, tuple[str, ...]] = {
    "triton": ("triton", "inference server", "model serving", "gpu inference"),
    "triton inference server": ("triton", "inference server", "model serving", "gpu inference"),
    "nvidia nim": ("nim", "nvidia inference microservices", "inference endpoint"),
    "tensorrt-llm": ("tensorrt", "llm optimization", "inference", "latency"),
    "nemo guardrails": ("nemo guardrails", "agent safety", "policy", "guardrails"),
    "rapids": ("rapids", "gpu dataframe", "cudf", "data acceleration"),
}

_KEYWORD_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "scale": ("throughput", "latency", "deployment"),
    "delivery": ("deployment", "endpoint", "serving", "inference"),
    "enterprise": ("production", "reliability", "deployment"),
    "customers": ("endpoint", "production", "deployment"),
    "ai": ("model", "inference", "gpu"),
    "analytics": ("data", "rapids", "gpu"),
    "agent": ("guardrails", "policy", "safety"),
}


def build_query_variants(query: RetrievalQuery, config: QueryRewriteConfig | None = None) -> list[RetrievalQuery]:
    """Build deterministic query variants while preserving the original first."""
    cfg = config or QueryRewriteConfig()
    if not cfg.enabled:
        return [query]

    variants = [query]
    expanded_keywords = _expanded_keywords(query, cfg.max_keywords_per_variant)
    if expanded_keywords and expanded_keywords != query.keywords:
        variants.append(
            query.model_copy(
                update={
                    "keywords": expanded_keywords,
                }
            )
        )

    if query.gap_type and query.gap_type in _GAP_KEYWORDS:
        variants.append(query.model_copy(update={"keywords": list(_GAP_KEYWORDS[query.gap_type])}))

    if query.technology:
        tech_terms = _TECH_SYNONYMS.get(query.technology.lower())
        if tech_terms:
            variants.append(query.model_copy(update={"keywords": list(tech_terms)}))

    return _dedupe_queries(variants)[: max(cfg.max_variants, 1)]


def retrieve_multi_query(
    index: ChunkIndex,
    query: RetrievalQuery,
    *,
    top_k: int = 3,
    config: QueryRewriteConfig | None = None,
) -> list[RetrievedContext]:
    """Run lexical retrieval across query variants and keep the best context per chunk."""
    cfg = config or QueryRewriteConfig()
    best_by_chunk: dict[str, RetrievedContext] = {}
    for variant_index, variant in enumerate(build_query_variants(query, cfg)):
        for context in index.retrieve(variant, top_k=top_k):
            score = min(1.0, context.relevance_score + (cfg.score_variant_bonus if variant_index > 0 else 0.0))
            candidate = context.model_copy(update={"relevance_score": round(score, 4)})
            existing = best_by_chunk.get(candidate.chunk_id)
            if existing is None or candidate.relevance_score > existing.relevance_score:
                best_by_chunk[candidate.chunk_id] = candidate

    return sorted(best_by_chunk.values(), key=lambda ctx: ctx.relevance_score, reverse=True)[:top_k]


def _expanded_keywords(query: RetrievalQuery, max_keywords: int) -> list[str]:
    expanded: list[str] = []
    for keyword in query.keywords:
        expanded.append(keyword)
        expanded.extend(_KEYWORD_EXPANSIONS.get(keyword.lower(), ()))
    if query.technology:
        expanded.extend(_TECH_SYNONYMS.get(query.technology.lower(), ()))
    if query.gap_type:
        expanded.extend(_GAP_KEYWORDS.get(query.gap_type, ()))
    return _dedupe_strings(expanded)[:max_keywords]


def _dedupe_queries(queries: list[RetrievalQuery]) -> list[RetrievalQuery]:
    seen: set[tuple[str | None, str | None, tuple[str, ...]]] = set()
    deduped: list[RetrievalQuery] = []
    for query in queries:
        key = (query.gap_type, query.technology, tuple(keyword.lower() for keyword in query.keywords))
        if key not in seen:
            seen.add(key)
            deduped.append(query)
    return deduped


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.lower().strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(value)
    return result


class QueryRewriting:
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query")
        index = kwargs.get("chunk_index") or kwargs.get("index")
        if not isinstance(query, RetrievalQuery) or not isinstance(index, ChunkIndex):
            return contexts
        config = kwargs.get("config")
        if config is not None and not isinstance(config, QueryRewriteConfig):
            config = QueryRewriteConfig(**config) if isinstance(config, dict) else None
        return retrieve_multi_query(
            index=index,
            query=query,
            top_k=kwargs.get("top_k", 3),
            config=config,
        )

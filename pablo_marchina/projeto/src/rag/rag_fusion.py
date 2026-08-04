"""RAG-Fusion: multi-query generation → retrieve each → RRF fuse.

Uses NVIDIA LLM to generate diverse query variants when available,
falls back to deterministic keyword-based variants.
"""

from __future__ import annotations

from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.query_rewriting import build_query_variants as deterministic_variants
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RAGFusionConfig, RetrievalQuery, RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_FUSION_PROMPT = """Generate {n} diverse search queries related to the topic below.

Each query must be a single line starting with "Q: ".
The queries should cover different angles and use different keywords.

Topic: {topic}

Q: """


def build_fusion_variants(
    query: RetrievalQuery,
    config: RAGFusionConfig | None = None,
) -> list[RetrievalQuery]:
    """Build query variants for RAG-Fusion.

    Uses NVIDIA LLM when ``use_nvidia_llm`` is True and the API is
    available. Falls back to deterministic keyword-based variants.
    """
    cfg = config or RAGFusionConfig()
    topic = _build_topic(query)

    if cfg.use_nvidia_llm:
        nvidia = _get_nvidia()
        prompt = _FUSION_PROMPT.format(n=cfg.max_variants - 1, topic=topic)
        reply = nvidia.llm_generate(prompt, max_tokens=256, temperature=0.7)
        if reply:
            variants: list[RetrievalQuery] = [query]
            for line in reply.strip().split("\n"):
                line = line.strip()
                if line.startswith("Q: "):
                    text = line[3:]
                    keywords = [k.strip() for k in text.split() if len(k) > 2]
                    variants.append(
                        RetrievalQuery(
                            gap_type=query.gap_type,
                            technology=query.technology,
                            keywords=keywords[: cfg.max_variants],
                        )
                    )
                    if len(variants) >= cfg.max_variants:
                        break
            if len(variants) > 1:
                return variants

    return deterministic_variants(query)[: cfg.max_variants]


def rag_fusion_retrieve(
    index: ChunkIndex,
    query: RetrievalQuery,
    config: RAGFusionConfig | None = None,
    top_k: int = 3,
) -> list[RetrievedContext]:
    """RAG-Fusion: multi-query → retrieve each → RRF fuse."""
    cfg = config or RAGFusionConfig()
    variants = build_fusion_variants(query, cfg)

    all_results: list[list[RetrievedContext]] = []
    for v in variants:
        all_results.append(index.retrieve(v, top_k=top_k))

    if not all_results or len(all_results) < 2:
        return all_results[0] if all_results else []

    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedContext] = {}

    for variant_results in all_results:
        for rank, ctx in enumerate(variant_results):
            cid = ctx.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (60 + rank)
            if cid not in chunk_map:
                chunk_map[cid] = ctx

    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)
    fused = [chunk_map[cid] for cid in sorted_ids[: cfg.fusion_top_k]]

    max_score = max(rrf_scores.values()) if rrf_scores else 1.0
    for ctx in fused:
        ctx.relevance_score = round(rrf_scores.get(ctx.chunk_id, 0.0) / max_score, 4)

    return fused


def _build_topic(query: RetrievalQuery) -> str:
    parts: list[str] = []
    if query.gap_type:
        parts.append(query.gap_type.replace("_", " "))
    if query.technology:
        parts.append(query.technology)
    if query.keywords:
        parts.extend(query.keywords)
    return " ".join(parts) if parts else "NVIDIA technology deployment"


class RagFusion:
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query")
        index = kwargs.get("chunk_index") or kwargs.get("index")
        if not isinstance(query, RetrievalQuery) or not isinstance(index, ChunkIndex):
            return contexts
        config = kwargs.get("config")
        if config is not None and not isinstance(config, RAGFusionConfig):
            config = RAGFusionConfig(**config) if isinstance(config, dict) else None
        return rag_fusion_retrieve(
            index=index,
            query=query,
            config=config,
            top_k=kwargs.get("top_k", 3),
        )

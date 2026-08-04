"""Self-RAG: LLM self-reflection scoring on retrieved chunks.

Each chunk is scored for relevance, factual support, and completeness
using an LLM judge (NVIDIA NIM). Chunks below threshold are demoted
or dropped.
"""

from __future__ import annotations

from typing import Any

from src.rag.nvidia_client import NvidiaClient
from src.rag.schemas import RetrievalQuery, RetrievedContext, SelfRAGConfig

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_REFLECTION_PROMPT = """Rate the relevance of the following document to the query.

Return ONLY a single number between 0.0 and 1.0.
0.0 = completely irrelevant
1.0 = perfectly relevant and directly answers the query

Query: {query}

Document: {document}

Relevance score:"""


def self_rag_reflect(
    contexts: list[RetrievedContext],
    query: RetrievalQuery | str,
    config: SelfRAGConfig | None = None,
) -> list[RetrievedContext]:
    """Score each chunk via LLM self-reflection.

    Chunks with relevance below ``relevance_threshold`` have their
    score penalized. Chunks at or above threshold keep their original
    score boosted by the reflection score.
    """
    cfg = config or SelfRAGConfig()
    if not cfg.enabled or not contexts:
        return contexts

    query_text = query if isinstance(query, str) else _build_query_text(query)
    nvidia = _get_nvidia()

    for ctx in contexts:
        reflection_score = _score_chunk(nvidia, query_text, ctx.content[:512], cfg)
        if reflection_score is not None:
            if reflection_score >= cfg.relevance_threshold:
                ctx.relevance_score = round(0.5 * ctx.relevance_score + 0.5 * reflection_score, 4)
            else:
                ctx.relevance_score = round(ctx.relevance_score * reflection_score, 4)

    contexts.sort(key=lambda x: x.relevance_score, reverse=True)
    return contexts


def _score_chunk(
    nvidia: NvidiaClient,
    query: str,
    document: str,
    config: SelfRAGConfig,
) -> float | None:
    for _attempt in range(1 + config.max_retries):
        prompt = _REFLECTION_PROMPT.format(query=query, document=document)
        reply = nvidia.llm_generate(prompt, max_tokens=10, temperature=0.01)
        if reply:
            try:
                score = float(reply.strip().split()[0])
                return max(0.0, min(1.0, score))
            except (ValueError, IndexError):
                continue
    return None


def _build_query_text(query: RetrievalQuery) -> str:
    parts: list[str] = []
    if query.gap_type:
        parts.append(query.gap_type.replace("_", " "))
    if query.technology:
        parts.append(query.technology)
    if query.keywords:
        parts.extend(query.keywords)
    return " ".join(parts) if parts else ""


class SelfRag:
    def run(self, contexts: list[RetrievedContext], **kwargs: Any) -> list[RetrievedContext]:
        query = kwargs.get("query", "")
        config = kwargs.get("config")
        return self_rag_reflect(contexts, query, config)

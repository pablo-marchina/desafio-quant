"""Corrective RAG: evaluate retrieval quality → rewrite → re-retrieve.

When retrieval confidence is below threshold, the query is rewritten
using NVIDIA LLM to improve specificity, then retrieval is repeated.
"""

from __future__ import annotations

from src.rag.nvidia_client import NvidiaClient
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import CorrectiveRAGConfig, RetrievalQuery, RetrievedContext

_NVIDIA_CLIENT: NvidiaClient | None = None


def _get_nvidia() -> NvidiaClient:
    global _NVIDIA_CLIENT
    if _NVIDIA_CLIENT is None:
        _NVIDIA_CLIENT = NvidiaClient()
    return _NVIDIA_CLIENT


_QUALITY_PROMPT = """Evaluate the quality of the search results below.

Return ONLY a single number between 0.0 and 1.0.
0.0 = completely useless results
1.0 = excellent results that directly address the query

Query: {query}

Results:
{results}

Quality score:"""

_REWRITE_PROMPT = """The following search query returned poor results.
Rewrite it to be more specific and targeted.

Original query: {query}
What the user is looking for: {topic}

Improved query:"""


def corrective_retrieve(
    index: ChunkIndex,
    query: RetrievalQuery,
    config: CorrectiveRAGConfig | None = None,
    top_k: int = 3,
) -> list[RetrievedContext]:
    """Retrieve with corrective loop.

    1. Initial retrieval
    2. Evaluate quality via LLM
    3. If below threshold, rewrite query and re-retrieve
    4. Return best results
    """
    cfg = config or CorrectiveRAGConfig()
    if not cfg.enabled:
        return index.retrieve(query, top_k=top_k)

    nvidia = _get_nvidia()
    best_contexts = index.retrieve(query, top_k=top_k)
    best_quality = _evaluate_quality(nvidia, query, best_contexts)

    for _round in range(cfg.max_correction_rounds):
        if best_quality >= cfg.quality_threshold:
            break

        rewritten = _rewrite_query(nvidia, query)
        if not rewritten:
            break

        corrected_query = RetrievalQuery(
            gap_type=query.gap_type,
            technology=query.technology,
            keywords=rewritten.split()[:12],
        )
        new_contexts = index.retrieve(corrected_query, top_k=top_k)
        new_quality = _evaluate_quality(nvidia, corrected_query, new_contexts)

        if new_quality > best_quality:
            best_contexts = new_contexts
            best_quality = new_quality

    return best_contexts


def _evaluate_quality(
    nvidia: NvidiaClient,
    query: RetrievalQuery,
    contexts: list[RetrievedContext],
) -> float:
    if not contexts:
        return 0.0

    query_text = _build_query_text(query)
    results_text = "\n".join(f"- [{ctx.chunk_id}] {ctx.content[:100]}" for ctx in contexts[:3])
    prompt = _QUALITY_PROMPT.format(query=query_text, results=results_text)
    reply = nvidia.llm_generate(prompt, max_tokens=10, temperature=0.01)
    if reply:
        try:
            return max(0.0, min(1.0, float(reply.strip().split()[0])))
        except (ValueError, IndexError):
            pass
    return 0.5


def _rewrite_query(
    nvidia: NvidiaClient,
    query: RetrievalQuery,
) -> str | None:
    topic = _build_query_text(query)
    prompt = _REWRITE_PROMPT.format(query=topic, topic=topic)
    reply = nvidia.llm_generate(prompt, max_tokens=64, temperature=0.3)
    return reply.strip() if reply else None


def _build_query_text(query: RetrievalQuery) -> str:
    parts: list[str] = []
    if query.gap_type:
        parts.append(query.gap_type.replace("_", " "))
    if query.technology:
        parts.append(query.technology)
    if query.keywords:
        parts.extend(query.keywords)
    return " ".join(parts) if parts else ""

"""Deterministic reranking of retrieved contexts.

Reranks a list of RetrievedContext based on:
- original relevance score
- gap_type match
- technology/product match
- provenance presence
- duplicate penalty
- source metadata quality

No external calls, no LLM judge.
"""

from __future__ import annotations

from src.rag.schemas import RerankingConfig, RetrievalQuery, RetrievedContext


def rerank_contexts(
    contexts: list[RetrievedContext],
    query: RetrievalQuery,
    config: RerankingConfig | None = None,
) -> list[RetrievedContext]:
    """Rerank contexts using a deterministic composite score.

    Parameters
    ----------
    contexts:
        Retrieved contexts from lexical, semantic, or hybrid retrieval.
    query:
        The original retrieval query (gap_type, technology, keywords).
    config:
        Reranking weights. Uses defaults if None.

    Returns
    -------
    list[RetrievedContext]
        Contexts sorted by descending rerank score.
        Each context's ``relevance_score`` is updated to the final rerank score.
    """
    if not contexts:
        return []

    cfg = config or RerankingConfig()
    seen_chunk_ids: set[str] = set()
    scored: list[tuple[RetrievedContext, float]] = []

    for ctx in contexts:
        score = ctx.relevance_score * 0.3

        if query.gap_type and query.gap_type in ctx.gap_types:
            score += cfg.boost_gap_match
        elif ctx.gap_types:
            score += cfg.penalty_irrelevant

        if query.technology:
            q_tech = query.technology.lower()
            if q_tech in ctx.product.lower() or q_tech in ctx.content.lower():
                score += cfg.boost_technology_match

        has_source = bool(ctx.source_id)
        has_url = bool(ctx.url)
        if has_source and has_url:
            score += cfg.boost_known_source
        elif not has_source or not has_url:
            score += cfg.penalty_no_provenance

        if ctx.chunk_id in seen_chunk_ids:
            score += cfg.penalty_duplicate
        seen_chunk_ids.add(ctx.chunk_id)

        score = max(0.0, min(1.0, score))
        scored.append((ctx, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    result: list[RetrievedContext] = []
    for ctx, s in scored:
        ctx.relevance_score = round(s, 2)
        result.append(ctx)

    return result

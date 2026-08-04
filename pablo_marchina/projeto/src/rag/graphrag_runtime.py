"""Runtime GraphRAG expansion for the official NVIDIA RAG pipeline.

This module is intentionally lightweight and local: it builds an evidence graph
from already-governed NVIDIA corpus contexts and uses graph neighborhood scores
as a third retrieval signal alongside dense Qdrant retrieval and BM25.
"""

from __future__ import annotations

from collections import defaultdict
import os
import re
from typing import Iterable

from src.rag.evidence_graph import build_evidence_graph, graph_lineage_summary
from src.rag.schemas import RetrievedContext, RetrievalQuery

_ENTITY_RE = re.compile(r"(?:NVIDIA\s+)?[A-Z][A-Za-z0-9+-]*(?:\s+[A-Z][A-Za-z0-9+-]*){0,4}")


def graphrag_expand(
    *,
    seed_contexts: list[RetrievedContext],
    corpus_contexts: Iterable[RetrievedContext],
    query: RetrievalQuery,
    top_k: int = 6,
    min_context_score: float | None = None,
) -> tuple[list[RetrievedContext], dict[str, object]]:
    """Return graph-neighborhood contexts for a query.

    The graph is built from shared entities, NVIDIA product labels, source IDs,
    and gap type overlap. The output is an actively used retrieval signal in the
    official RAG service, not a benchmark-only artifact.
    """

    if not seed_contexts:
        return [], {"enabled": True, "seed_count": 0, "graph_context_count": 0, "lineage_path_count": 0}

    min_score = float(min_context_score if min_context_score is not None else os.getenv("GRAPHRAG_MIN_CONTEXT_SCORE", "0.0"))
    max_neighbors = int(os.getenv("GRAPHRAG_MAX_GRAPH_NEIGHBORS", str(top_k)))

    seeds_by_id = {c.chunk_id: c for c in seed_contexts}
    seed_entities = set()
    seed_products = set()
    seed_sources = set()
    seed_gaps = set()
    for ctx in seed_contexts:
        seed_entities.update(_entities(ctx))
        if ctx.product:
            seed_products.add(ctx.product.casefold())
        if ctx.source_id:
            seed_sources.add(ctx.source_id.casefold())
        seed_gaps.update(g.casefold() for g in ctx.gap_types)

    scored: list[tuple[RetrievedContext, float]] = []
    for ctx in corpus_contexts:
        if ctx.chunk_id in seeds_by_id:
            continue
        if ctx.relevance_score < min_score:
            continue
        score = _graph_score(ctx, seed_entities, seed_products, seed_sources, seed_gaps, query)
        if score > 0:
            clone = ctx.model_copy(deep=True)
            clone.relevance_score = round(min(1.0, 0.55 * clone.relevance_score + 0.45 * score), 4)
            scored.append((clone, clone.relevance_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    graph_contexts = [ctx for ctx, _ in scored[:max_neighbors]]

    technology = query.technology or (seed_contexts[0].product if seed_contexts else "NVIDIA")
    graph = build_evidence_graph(
        contexts=seed_contexts + graph_contexts,
        gap_type=query.gap_type or "unknown_gap",
        technology=technology,
        alternatives=[],
    )
    metrics = dict(graph.metrics)
    metrics.update(
        {
            "enabled": True,
            "seed_count": len(seed_contexts),
            "graph_context_count": len(graph_contexts),
            "graph_summary": graph_lineage_summary(graph),
        }
    )
    return graph_contexts, metrics


def _entities(ctx: RetrievedContext) -> set[str]:
    return {m.group(0).casefold() for m in _ENTITY_RE.finditer(f"{ctx.title} {ctx.product} {ctx.content}")}


def _graph_score(
    ctx: RetrievedContext,
    seed_entities: set[str],
    seed_products: set[str],
    seed_sources: set[str],
    seed_gaps: set[str],
    query: RetrievalQuery,
) -> float:
    score = 0.0
    entities = _entities(ctx)
    if seed_entities:
        score += min(0.45, 0.08 * len(entities & seed_entities))
    if ctx.product and ctx.product.casefold() in seed_products:
        score += 0.25
    if ctx.source_id and ctx.source_id.casefold() in seed_sources:
        score += 0.10
    if seed_gaps and set(g.casefold() for g in ctx.gap_types) & seed_gaps:
        score += 0.25
    if query.technology and query.technology.casefold() in f"{ctx.product} {ctx.content}".casefold():
        score += 0.25
    if query.gap_type and query.gap_type.casefold() in {g.casefold() for g in ctx.gap_types}:
        score += 0.20
    if ctx.source_id and ctx.url:
        score += 0.05
    return min(1.0, score)


class GraphRAGRuntime:
    """Technique runner wrapper used by the RAG technique pipeline."""

    def run(self, contexts: list[RetrievedContext], **kwargs: object) -> list[RetrievedContext]:
        query = kwargs.get("retrieval_query") or kwargs.get("query")
        corpus_contexts = kwargs.get("corpus_contexts")
        if not isinstance(query, RetrievalQuery) or corpus_contexts is None:
            return contexts
        expanded, _ = graphrag_expand(
            seed_contexts=contexts,
            corpus_contexts=corpus_contexts,  # type: ignore[arg-type]
            query=query,
            top_k=int(kwargs.get("top_k", 6)),
        )
        existing = {c.chunk_id for c in contexts}
        return contexts + [c for c in expanded if c.chunk_id not in existing]


# Loader-friendly alias.
GraphragRuntime = GraphRAGRuntime

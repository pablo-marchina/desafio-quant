"""RAG pipeline orchestration — retrieve, rerank, pack for the main pipeline.

Epic 14.1: Integrates hybrid retrieval, deterministic reranking, and context
packing into a single step that the main pipeline calls as Step 11.
RAG remains optional — missing corpus or empty index returns missing_context.
"""

from __future__ import annotations

from src.diagnosis.schemas import GapDiagnosisResult
from src.rag.context_packing import pack_contexts
from src.rag.embeddings import EmbeddingProvider
from src.rag.hybrid_retrieval import hybrid_retrieve
from src.rag.query_rewriting import QueryRewriteConfig, retrieve_multi_query
from src.rag.reranking import rerank_contexts
from src.rag.retrieval import ChunkIndex, build_default_index
from src.rag.schemas import (
    PackingConfig,
    PackingResult,
    RagPipelineOutput,
    RerankingConfig,
    RetrievalQuery,
    RetrievedContext,
)
from src.rag.vector_store import VectorStore


def run_rag_pipeline(
    gap_diagnosis: GapDiagnosisResult,
    chunk_index: ChunkIndex | None = None,
    embedding_model: EmbeddingProvider | None = None,
    vector_store: VectorStore | None = None,
    reranking_config: RerankingConfig | None = None,
    packing_config: PackingConfig | None = None,
    query_rewrite_config: QueryRewriteConfig | None = None,
) -> RagPipelineOutput:
    """Orchestrate hybrid retrieval → reranking → context packing for the pipeline.

    Parameters
    ----------
    gap_diagnosis:
        Diagnosed gaps with technology candidates.
    chunk_index:
        Lexical index. If None, tries ``build_default_index()``.
    embedding_model:
        Embedding provider for semantic search. If None, falls back to lexical.
    vector_store:
        Vector store for semantic search. If None or empty, falls back to lexical.
    reranking_config:
        Reranking weights. If None, reranking is skipped.
    packing_config:
        Packing limits. If None, packing is skipped (all contexts kept).

    Returns
    -------
    RagPipelineOutput
        Packed contexts and quality metadata.
    """
    idx = chunk_index if chunk_index is not None else build_default_index()

    if not idx.chunks:
        return RagPipelineOutput(
            packing_result=None,
            retrieval_mode="lexical",
            missing_context=True,
            rag_quality_summary="Index is empty — no corpus available.",
        )

    diagnosed = [g for g in gap_diagnosis.diagnosed_gaps if g.detected]
    if not diagnosed:
        return RagPipelineOutput(
            packing_result=None,
            retrieval_mode="lexical",
            missing_context=True,
            rag_quality_summary="No diagnosed gaps to retrieve context for.",
        )

    tech_by_gap: dict[str, list[str]] = {}
    for gap in diagnosed:
        gap_val = gap.gap.value
        tech_by_gap.setdefault(gap_val, [])
    for tc in gap_diagnosis.nvidia_technology_candidates:
        gap_val = tc.addresses_gap.value
        tech_name = tc.technology_name
        if gap_val in tech_by_gap:
            tech_by_gap[gap_val].append(tech_name)

    all_contexts: list[RetrievedContext] = []
    retrieval_mode = "lexical"

    for gap_val, techs in tech_by_gap.items():
        if not techs:
            query = RetrievalQuery(gap_type=gap_val)
            if query_rewrite_config is not None and query_rewrite_config.enabled:
                ctxs = retrieve_multi_query(idx, query, top_k=3, config=query_rewrite_config)
                if retrieval_mode == "lexical":
                    retrieval_mode = "lexical_multi_query"
            else:
                ctxs = idx.retrieve(query, top_k=3)
            all_contexts.extend(ctxs)
        else:
            for tech in sorted(techs):
                query = RetrievalQuery(gap_type=gap_val, technology=tech)
                if vector_store is not None and vector_store.size > 0 and embedding_model is not None:  # noqa: E501
                    ctxs = hybrid_retrieve(query, idx, embedding_model, vector_store, top_k=3)
                    if retrieval_mode == "lexical":
                        retrieval_mode = "hybrid"
                elif query_rewrite_config is not None and query_rewrite_config.enabled:
                    ctxs = retrieve_multi_query(idx, query, top_k=3, config=query_rewrite_config)
                    if retrieval_mode == "lexical":
                        retrieval_mode = "lexical_multi_query"
                else:
                    ctxs = idx.retrieve(query, top_k=3)
                all_contexts.extend(ctxs)

    if not all_contexts:
        return RagPipelineOutput(
            packing_result=None,
            retrieval_mode=retrieval_mode,
            missing_context=True,
            rag_quality_summary="No contexts retrieved for any gap or technology.",
        )

    # Deduplicate by chunk_id across all retrieved contexts
    seen: set[str] = set()
    deduped: list[RetrievedContext] = []
    for ctx in all_contexts:
        if ctx.chunk_id not in seen:
            seen.add(ctx.chunk_id)
            deduped.append(ctx)

    # Rerank (if configured)
    if reranking_config is not None:
        deduped = rerank_contexts(deduped, RetrievalQuery(), config=reranking_config)
        retrieval_mode = (
            "lexical_multi_query_reranked" if retrieval_mode == "lexical_multi_query" else "hybrid_reranked"
        )

    # Pack (if configured)
    packing_result: PackingResult | None = None
    if packing_config is not None:
        packing_result = pack_contexts(deduped, RetrievalQuery(), config=packing_config)
        if retrieval_mode == "lexical_multi_query_reranked":
            retrieval_mode = "lexical_multi_query_reranked_packed"
        elif retrieval_mode == "lexical_multi_query":
            retrieval_mode = "lexical_multi_query_packed"
        else:
            retrieval_mode = "hybrid_reranked_packed"
    else:
        # Build a minimal packing result with deduped contexts
        from src.rag.schemas import PackedContext

        packed_list = [
            PackedContext(
                chunk_id=ctx.chunk_id,
                source_id=ctx.source_id,
                title=ctx.title,
                content=ctx.content,
                product=ctx.product,
                gap_types=list(ctx.gap_types),
                url=ctx.url,
                relevance_score=ctx.relevance_score,
                rerank_score=ctx.relevance_score,
                matched_gap=None,
                matched_technology=None,
                version=ctx.version,
                valid_from=ctx.valid_from,
                valid_until=ctx.valid_until,
                freshness_policy=ctx.freshness_policy,
                stale_after_days=ctx.stale_after_days,
                is_active=ctx.is_active,
                deprecated_at=ctx.deprecated_at,
                superseded_by=ctx.superseded_by,
            )
            for ctx in deduped
        ]
        has_prov = sum(1 for p in packed_list if p.source_id and p.url)
        packing_result = PackingResult(
            packed=packed_list,
            dropped=[],
            total_raw=len(deduped),
            total_packed=len(packed_list),
            total_dropped=0,
            provenance_coverage=round(has_prov / len(packed_list), 4) if packed_list else 1.0,
            gap_coverage=0.0,
            technology_coverage=0.0,
            context_budget_used=1.0,
            noise_reduction_score=1.0,
        )

    lines: list[str] = [
        f"Retrieval mode: {retrieval_mode}",
        f"Raw contexts: {packing_result.total_raw}",
        f"Packed contexts: {packing_result.total_packed}",
        f"Dropped contexts: {packing_result.total_dropped}",
        f"Provenance coverage: {packing_result.provenance_coverage}",
        f"Noise reduction: {packing_result.noise_reduction_score}",
    ]

    return RagPipelineOutput(
        packing_result=packing_result,
        retrieval_mode=retrieval_mode,
        missing_context=False,
        rag_quality_summary="\n".join(lines),
    )

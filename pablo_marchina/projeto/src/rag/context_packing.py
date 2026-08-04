"""Context packing for RAG — dedup, filter, limit, and organize contexts.

Removes duplicates, applies per-gap and per-technology limits,
preserves provenance, and returns dropped contexts with reasons.
"""

from __future__ import annotations

from src.rag.schemas import (
    DroppedContext,
    PackedContext,
    PackingConfig,
    PackingResult,
    RetrievalQuery,
    RetrievedContext,
    SupportingNvidiaContext,
)


def pack_contexts(
    contexts: list[RetrievedContext],
    query: RetrievalQuery,
    config: PackingConfig | None = None,
) -> PackingResult:
    """Pack contexts: dedup, filter, limit by gap/tech, sort by relevance.

    Parameters
    ----------
    contexts:
        Already-reranked contexts (or raw, if reranking is skipped).
    query:
        The original retrieval query.
    config:
        Packing limits. Uses defaults if None.

    Returns
    -------
    PackingResult
        Packed contexts, dropped contexts, and quality metrics.
    """
    cfg = config or PackingConfig()
    total_raw = len(contexts)

    # ---- Step 1: dedup by chunk_id ----
    seen: set[str] = set()
    deduped: list[RetrievedContext] = []
    dropped: list[DroppedContext] = []
    for ctx in contexts:
        if ctx.chunk_id in seen:
            dropped.append(
                DroppedContext(
                    chunk_id=ctx.chunk_id,
                    reason="duplicate",
                    rerank_score=ctx.relevance_score,
                )
            )
        else:
            seen.add(ctx.chunk_id)
            deduped.append(ctx)

    # duplicate_count is tracked via total_raw - total_packed - total_dropped in PackingResult

    # ---- Step 2: classify by gap and technology ----
    grouped: dict[str, dict[str, list[PackedContext]]] = {}
    for ctx in deduped:
        matched_gap = query.gap_type if query.gap_type and query.gap_type in ctx.gap_types else None
        matched_tech = (
            query.technology
            if (
                query.technology
                and (query.technology.lower() in ctx.product.lower() or query.technology.lower() in ctx.content.lower())
            )
            else None
        )
        pc = PackedContext(
            chunk_id=ctx.chunk_id,
            source_id=ctx.source_id,
            title=ctx.title,
            content=ctx.content,
            product=ctx.product,
            gap_types=list(ctx.gap_types),
            url=ctx.url,
            relevance_score=ctx.relevance_score,
            rerank_score=ctx.relevance_score,
            matched_gap=matched_gap,
            matched_technology=matched_tech,
            version=ctx.version,
            valid_from=ctx.valid_from,
            valid_until=ctx.valid_until,
            freshness_policy=ctx.freshness_policy,
            stale_after_days=ctx.stale_after_days,
            is_active=ctx.is_active,
            deprecated_at=ctx.deprecated_at,
            superseded_by=ctx.superseded_by,
        )
        gap_key = matched_gap or "_unknown"
        tech_key = matched_tech or "_unknown"
        grouped.setdefault(gap_key, {}).setdefault(tech_key, []).append(pc)

    # ---- Step 3: sort within each gap/tech group and apply limits ----
    packed: list[PackedContext] = []
    for _gap_key, tech_dict in grouped.items():
        for _tech_key, tech_contexts in tech_dict.items():
            tech_contexts.sort(key=lambda x: x.rerank_score, reverse=True)
            if len(tech_contexts) > cfg.max_per_technology:
                for exc in tech_contexts[cfg.max_per_technology :]:
                    dropped.append(
                        DroppedContext(
                            chunk_id=exc.chunk_id,
                            reason=f"exceeded_per_technology (max {cfg.max_per_technology})",
                            rerank_score=exc.rerank_score,
                        )
                    )
                tech_contexts = tech_contexts[: cfg.max_per_technology]
            packed.extend(tech_contexts)

        # Apply per-gap limit
        all_in_gap: list[PackedContext] = []
        for tcs in tech_dict.values():
            all_in_gap.extend(tcs)
        if len(all_in_gap) > cfg.max_per_gap:
            all_in_gap.sort(key=lambda x: x.rerank_score, reverse=True)
            for exc in all_in_gap[cfg.max_per_gap :]:
                dropped.append(
                    DroppedContext(
                        chunk_id=exc.chunk_id,
                        reason=f"exceeded_per_gap (max {cfg.max_per_gap})",
                        rerank_score=exc.rerank_score,
                    )
                )
            # Remove exceeded from packed
            exceed_ids = {exc.chunk_id for exc in all_in_gap[cfg.max_per_gap :]}
            packed = [p for p in packed if p.chunk_id not in exceed_ids]

    # ---- Step 4: sort globally by gap → technology → score ----
    packed.sort(
        key=lambda p: (
            0 if p.matched_gap else 1,
            0 if p.matched_technology else 1,
            -p.rerank_score,
        )
    )

    # ---- Step 5: apply global max_total ----
    if len(packed) > cfg.max_total:
        for exc in packed[cfg.max_total :]:
            dropped.append(
                DroppedContext(
                    chunk_id=exc.chunk_id,
                    reason=f"exceeded_global_max (max {cfg.max_total})",
                    rerank_score=exc.rerank_score,
                )
            )
        packed = packed[: cfg.max_total]

    # ---- Step 6: compute metrics ----
    total_packed = len(packed)
    total_dropped = len(dropped)
    has_provenance = sum(1 for p in packed if p.source_id and p.url) if packed else 0
    provenance_coverage = round(has_provenance / total_packed, 4) if total_packed > 0 else 1.0
    context_budget_used = round(total_packed / cfg.max_total, 4) if cfg.max_total > 0 else 1.0
    noise_reduction_score = round(1.0 - (total_dropped / max(total_raw, 1)), 4)

    gap_coverage = 0.0
    technology_coverage = 0.0
    expected_gaps = [query.gap_type] if query.gap_type else []
    expected_techs = [query.technology] if query.technology else []
    if expected_gaps:
        covered_gaps = sum(1 for p in packed if p.matched_gap == query.gap_type)
        gap_coverage = round(covered_gaps / len(expected_gaps), 4)
    if expected_techs:
        covered_techs = sum(1 for p in packed if p.matched_technology == query.technology)
        technology_coverage = round(covered_techs / len(expected_techs), 4)

    return PackingResult(
        packed=packed,
        dropped=dropped,
        total_raw=total_raw,
        total_packed=total_packed,
        total_dropped=total_dropped,
        provenance_coverage=provenance_coverage,
        gap_coverage=gap_coverage,
        technology_coverage=technology_coverage,
        context_budget_used=context_budget_used,
        noise_reduction_score=noise_reduction_score,
    )


def build_supporting_contexts(packing_result: PackingResult) -> list[SupportingNvidiaContext]:
    """Group packed contexts into SupportingNvidiaContext by gap and technology.

    Returns a list suitable for embedding into the Action Brief.
    """
    by_gap_tech: dict[tuple[str, str], list[PackedContext]] = {}
    for pc in packing_result.packed:
        gap = pc.matched_gap or "_unknown"
        tech = pc.matched_technology or "_unknown"
        by_gap_tech.setdefault((gap, tech), []).append(pc)

    result: list[SupportingNvidiaContext] = []
    for (gap, tech), contexts in by_gap_tech.items():
        dropped_count = sum(1 for d in packing_result.dropped if d.chunk_id in {c.chunk_id for c in contexts})
        result.append(
            SupportingNvidiaContext(
                gap_type=gap,
                technology=tech,
                contexts=contexts,
                total_available=len(contexts) + dropped_count,
                total_dropped=dropped_count,
            )
        )

    result.sort(key=lambda s: (0 if s.gap_type != "_unknown" else 1, s.gap_type))
    return result

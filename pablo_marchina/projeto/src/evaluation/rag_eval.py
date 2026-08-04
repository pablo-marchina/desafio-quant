"""Corpus-aware offline RAG evaluation.

This module preserves the established retrieval/evaluation implementation in
``rag_eval_legacy`` while refining relevance semantics for a growing corpus:

* ``expected_*`` values remain mandatory coverage targets;
* ``allowed_*`` values define additional relevant results that must not be
  counted as noise;
* negative queries still require an empty result set.

The separation prevents newly governed NVIDIA sources from being mislabeled as
irrelevant without weakening mandatory coverage gates.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluation import rag_eval_legacy as _legacy
from src.evaluation.rag_eval_schemas import (
    ModeEvalResult,
    RagEvalCase,
    RagEvalComparison,
    RagEvalResult,
    RagQualityGateResult,
    RagRetrievalMetrics,
    RetrievalMode,
)
from src.rag.embeddings import EmbeddingProvider
from src.rag.retrieval import ChunkIndex, build_default_index
from src.rag.schemas import PackingConfig, PackingResult, RerankingConfig
from src.rag.vector_store import VectorStore

_GOLDEN_QUERIES_PATH = Path("examples/rag_eval/golden_queries.json")
_EXPECTED_CONTEXTS_PATH = Path("examples/rag_eval/expected_contexts.json")

# Stable helpers and formatters remain delegated to the established evaluator.
_load_expected_contexts = _legacy._load_expected_contexts
_check_provenance = _legacy._check_provenance
_retrieve_for_mode = _legacy._retrieve_for_mode
run_quality_gates = _legacy.run_quality_gates
format_eval_summary = _legacy.format_eval_summary
format_comparison_summary = _legacy.format_comparison_summary


def _load_golden_queries(path: Path = _GOLDEN_QUERIES_PATH) -> list[RagEvalCase]:
    """Load required and allowed relevance boundaries from the golden set."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[RagEvalCase] = []
    for item in raw["queries"]:
        cases.append(
            RagEvalCase(
                case_id=item["case_id"],
                description=item["description"],
                query=item["query"],
                expected_source_ids=item.get("expected_source_ids", []),
                expected_products=item.get("expected_products", []),
                allowed_source_ids=item.get("allowed_source_ids", []),
                allowed_products=item.get("allowed_products", []),
                is_critical=item.get("is_critical", False),
                top_k_for_test=item.get("top_k_for_test", 3),
            )
        )
    return cases


def _relevant_source_ids(case: RagEvalCase) -> set[str]:
    return set(case.allowed_source_ids or case.expected_source_ids)


def _relevant_products(case: RagEvalCase) -> set[str]:
    return set(case.allowed_products or case.expected_products)


def _compute_metrics(
    retrieved: list,
    case: RagEvalCase,
    packing_result: PackingResult | None = None,
) -> RagRetrievalMetrics:
    """Measure mandatory coverage and precision against the wider allowed set."""
    total = len(retrieved)
    retrieved_source_ids = {context.source_id for context in retrieved}
    retrieved_products = {context.product for context in retrieved}
    required_sources = set(case.expected_source_ids)
    required_products = set(case.expected_products)
    relevant_sources = _relevant_source_ids(case)

    hit_at_k = bool(retrieved and relevant_sources.intersection(retrieved_source_ids))
    top_1_expected = bool(retrieved and retrieved[0].source_id in relevant_sources)

    source_coverage = (
        len(required_sources.intersection(retrieved_source_ids)) / len(required_sources)
        if required_sources
        else 0.0
    )
    product_coverage = (
        len(required_products.intersection(retrieved_products)) / len(required_products)
        if required_products
        else 0.0
    )

    irrelevant = (
        sum(1 for context in retrieved if context.source_id not in relevant_sources)
        if relevant_sources
        else 0
    )
    missing = len(required_sources.difference(retrieved_source_ids))
    precision = (
        (total - irrelevant) / total
        if total > 0 and relevant_sources
        else 0.0
    )

    duplicate_count = 0
    packed_count = 0
    dropped_count = 0
    provenance_coverage = 0.0
    context_budget_used = 0.0
    gap_coverage = 0.0
    technology_coverage = 0.0
    noise_reduction_score = 0.0

    if packing_result:
        duplicate_count = (
            packing_result.total_raw
            - packing_result.total_packed
            - packing_result.total_dropped
        )
        packed_count = packing_result.total_packed
        dropped_count = packing_result.total_dropped
        provenance_coverage = packing_result.provenance_coverage
        context_budget_used = packing_result.context_budget_used
        gap_coverage = packing_result.gap_coverage
        technology_coverage = packing_result.technology_coverage
        noise_reduction_score = packing_result.noise_reduction_score

    return RagRetrievalMetrics(
        hit_at_k=hit_at_k,
        expected_source_coverage=round(source_coverage, 4),
        expected_product_coverage=round(product_coverage, 4),
        irrelevant_context_count=irrelevant,
        missing_context_count=missing,
        top_1_expected_match=top_1_expected,
        context_precision=round(precision, 4),
        duplicate_context_count=duplicate_count,
        packed_context_count=packed_count,
        dropped_context_count=dropped_count,
        provenance_coverage=round(provenance_coverage, 4),
        context_budget_used=round(context_budget_used, 4),
        gap_coverage=round(gap_coverage, 4),
        technology_coverage=round(technology_coverage, 4),
        noise_reduction_score=round(noise_reduction_score, 4),
    )


def _eval_one_case(
    case: RagEvalCase,
    retrieved: list,
    packing_result: PackingResult | None = None,
) -> RagEvalResult:
    metrics = _compute_metrics(retrieved, case, packing_result=packing_result)
    failure_reasons: list[str] = []
    relevant_sources = _relevant_source_ids(case)

    if case.is_critical and relevant_sources:
        if not metrics.hit_at_k:
            failure_reasons.append(
                f"critical case '{case.case_id}': hit_at_k=False "
                f"(top_{case.top_k_for_test})"
            )
        if not metrics.top_1_expected_match:
            failure_reasons.append(
                f"critical case '{case.case_id}': top_1_expected_match=False"
            )

    if case.expected_source_ids and metrics.missing_context_count > 0:
        found_required = len(
            set(case.expected_source_ids).intersection(
                {context.source_id for context in retrieved}
            )
        )
        failure_reasons.append(
            f"case '{case.case_id}': missing_context_count="
            f"{metrics.missing_context_count} "
            f"(found {found_required}/{len(case.expected_source_ids)} "
            "required sources)"
        )

    provenance_issues = _check_provenance(retrieved)
    failure_reasons.extend(
        f"provenance: {issue}" for issue in provenance_issues
    )

    if not relevant_sources and retrieved:
        failure_reasons.append(
            f"case '{case.case_id}': expected empty but got {len(retrieved)} results"
        )

    return RagEvalResult(
        case_id=case.case_id,
        case_description=case.description,
        passed=not failure_reasons,
        is_critical=case.is_critical,
        metrics=metrics,
        retrieved_contexts=retrieved,
        expected_source_ids=case.expected_source_ids,
        expected_products=case.expected_products,
        allowed_source_ids=case.allowed_source_ids,
        allowed_products=case.allowed_products,
        failure_reasons=failure_reasons,
    )


def run_rag_eval(
    index: ChunkIndex | None = None,
    golden_path: Path = _GOLDEN_QUERIES_PATH,
    expected_path: Path = _EXPECTED_CONTEXTS_PATH,
) -> list[RagEvalResult]:
    """Evaluate all lexical golden queries against the active corpus."""
    del expected_path  # Kept for backward-compatible call signatures.
    chunk_index = index if index is not None else build_default_index()
    return [
        _eval_one_case(
            case,
            chunk_index.retrieve(case.query, top_k=case.top_k_for_test),
        )
        for case in _load_golden_queries(golden_path)
    ]


def run_mode_eval(
    mode: RetrievalMode,
    golden_path: Path = _GOLDEN_QUERIES_PATH,
    *,
    chunk_index: ChunkIndex | None = None,
    vector_store: VectorStore | None = None,
    embedding_model: EmbeddingProvider | None = None,
    reranking_config: RerankingConfig | None = None,
    packing_config: PackingConfig | None = None,
) -> ModeEvalResult:
    """Evaluate one retrieval mode using corpus-aware relevance boundaries."""
    index = chunk_index if chunk_index is not None else build_default_index()
    needs_embedding = mode in (
        RetrievalMode.SEMANTIC,
        RetrievalMode.HYBRID,
        RetrievalMode.HYBRID_RERANKED,
        RetrievalMode.HYBRID_RERANKED_PACKED,
    )
    if needs_embedding and embedding_model is None:
        raise ValueError(
            "embedding_model is required for semantic/hybrid RAG evaluation"
        )

    results: list[RagEvalResult] = []
    for case in _load_golden_queries(golden_path):
        retrieved, packing_result = _retrieve_for_mode(
            mode,
            case,
            index,
            embedding_model if needs_embedding else None,
            vector_store,
            reranking_config=reranking_config,
            packing_config=packing_config,
        )
        results.append(
            _eval_one_case(case, retrieved, packing_result=packing_result)
        )

    gates = run_quality_gates(results)
    return ModeEvalResult(
        mode=mode,
        results=results,
        gates=gates,
        passed_cases=sum(1 for result in results if result.passed),
        total_cases=len(results),
    )


def run_comparison_eval(
    chunk_index: ChunkIndex | None = None,
    vector_store: VectorStore | None = None,
    embedding_model: EmbeddingProvider | None = None,
    golden_path: Path = _GOLDEN_QUERIES_PATH,
) -> RagEvalComparison:
    """Run all retrieval modes and detect regressions against lexical."""
    lexical = run_mode_eval(
        RetrievalMode.LEXICAL,
        golden_path,
        chunk_index=chunk_index,
    )
    semantic = run_mode_eval(
        RetrievalMode.SEMANTIC,
        golden_path,
        chunk_index=chunk_index,
        vector_store=vector_store,
        embedding_model=embedding_model,
    )
    hybrid = run_mode_eval(
        RetrievalMode.HYBRID,
        golden_path,
        chunk_index=chunk_index,
        vector_store=vector_store,
        embedding_model=embedding_model,
    )
    hybrid_reranked = run_mode_eval(
        RetrievalMode.HYBRID_RERANKED,
        golden_path,
        chunk_index=chunk_index,
        vector_store=vector_store,
        embedding_model=embedding_model,
    )
    hybrid_packed = run_mode_eval(
        RetrievalMode.HYBRID_RERANKED_PACKED,
        golden_path,
        chunk_index=chunk_index,
        vector_store=vector_store,
        embedding_model=embedding_model,
    )

    lexical_critical_passes = {
        result.case_id
        for result in lexical.results
        if result.is_critical and result.passed
    }
    regressions: list[str] = []
    for label, mode_result in (
        ("semantic", semantic),
        ("hybrid", hybrid),
        ("hybrid_reranked", hybrid_reranked),
        ("hybrid_reranked_packed", hybrid_packed),
    ):
        regressions.extend(
            f"{label}/{result.case_id}"
            for result in mode_result.results
            if result.is_critical
            and result.case_id in lexical_critical_passes
            and not result.passed
        )

    return RagEvalComparison(
        lexical=lexical,
        semantic=semantic,
        hybrid=hybrid,
        hybrid_reranked=hybrid_reranked,
        hybrid_reranked_packed=hybrid_packed,
        critical_regressions=regressions,
    )


__all__ = [
    "ModeEvalResult",
    "RagEvalCase",
    "RagEvalComparison",
    "RagEvalResult",
    "RagQualityGateResult",
    "RagRetrievalMetrics",
    "RetrievalMode",
    "_check_provenance",
    "_compute_metrics",
    "_eval_one_case",
    "_load_expected_contexts",
    "_load_golden_queries",
    "format_comparison_summary",
    "format_eval_summary",
    "run_comparison_eval",
    "run_mode_eval",
    "run_quality_gates",
    "run_rag_eval",
]

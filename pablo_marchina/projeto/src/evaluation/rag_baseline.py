from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.rag.embeddings import EmbeddingProvider
from src.rag.retrieval import ChunkIndex, build_default_index
from src.rag.schemas import RetrievalQuery, RetrievedContext
from src.rag.semantic_retrieval import semantic_retrieve
from src.rag.vector_store import VectorStore


class RagBaselineCase(BaseModel):
    case_id: str
    description: str
    query: RetrievalQuery
    expected_source_ids: list[str] = Field(default_factory=list)
    expected_products: list[str] = Field(default_factory=list)
    is_critical: bool = False
    top_k_for_test: int = 3
    minimum_relevant_contexts: int = 0
    critical_claims_expected: int = 0


class RagBaselineMetrics(BaseModel):
    recall_at_k: float = 0.0
    precision_at_k: float = 0.0
    mrr: float = 0.0
    citation_precision: float = 0.0
    unsupported_claim_rate: float = 0.0
    retrieved_context_count: int = 0
    relevant_context_count: int = 0


class RagBaselineResult(BaseModel):
    case_id: str
    description: str
    top_k: int
    is_critical: bool
    expected_source_ids: list[str] = Field(default_factory=list)
    retrieved_source_ids: list[str] = Field(default_factory=list)
    metrics: RagBaselineMetrics


@dataclass
class RagGridSearchResult:
    top_k: int
    avg_recall: float
    avg_precision: float
    mrr: float
    avg_citation_precision: float
    avg_unsupported_claim_rate: float
    avg_retrieved: float
    avg_relevant: float
    total_cases: int
    cases_with_expected_sources: int
    per_case_results: list[RagBaselineResult] = field(default_factory=list)


def _load_baseline_golden(path: Path) -> list[RagBaselineCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[RagBaselineCase] = []
    for item in raw["queries"]:
        q = RetrievalQuery(**item["query"])
        cases.append(
            RagBaselineCase(
                case_id=item["case_id"],
                description=item["description"],
                query=q,
                expected_source_ids=item.get("expected_source_ids", []),
                expected_products=item.get("expected_products", []),
                is_critical=item.get("is_critical", False),
                top_k_for_test=item.get("top_k_for_test", 3),
                minimum_relevant_contexts=item.get("minimum_relevant_contexts", 0),
                critical_claims_expected=item.get("critical_claims_expected", 0),
            )
        )
    return cases


def _compute_metrics_for_case(
    case: RagBaselineCase,
    retrieved: list[RetrievedContext],
    top_k: int,
) -> RagBaselineMetrics:
    top_k_ctx = retrieved[:top_k]
    retrieved_source_ids = [ctx.source_id for ctx in top_k_ctx]
    expected = set(case.expected_source_ids)

    retrieved_count = len(top_k_ctx)

    unique_found = {sid for sid in retrieved_source_ids if sid in expected}
    relevant_unique_count = len(unique_found)
    expected_count = len(expected)

    relevant_in_top_k = sum(1 for sid in retrieved_source_ids if sid in expected)

    if expected_count > 0:
        recall = relevant_unique_count / expected_count
    else:
        recall = 1.0 if retrieved_count == 0 else 0.0

    if top_k > 0:
        precision = relevant_in_top_k / top_k
    else:
        precision = 0.0

    rr = 0.0
    for rank, ctx in enumerate(top_k_ctx, start=1):
        if ctx.source_id in expected:
            rr = 1.0 / rank
            break

    citation_count = sum(1 for ctx in top_k_ctx if ctx.source_id and ctx.url)
    citation_prec = citation_count / retrieved_count if retrieved_count > 0 else 1.0

    unsupported_count = max(0, expected_count - relevant_unique_count)
    unsupported_rate = unsupported_count / expected_count if expected_count > 0 else 0.0

    return RagBaselineMetrics(
        recall_at_k=round(recall, 4),
        precision_at_k=round(precision, 4),
        mrr=round(rr, 4),
        citation_precision=round(citation_prec, 4),
        unsupported_claim_rate=round(unsupported_rate, 4),
        retrieved_context_count=retrieved_count,
        relevant_context_count=relevant_unique_count,
    )


def _retrieve_for_baseline(
    case: RagBaselineCase,
    top_k: int,
    *,
    index: ChunkIndex | None = None,
    vector_store: VectorStore | None = None,
    embedding_model: EmbeddingProvider | None = None,
) -> list[RetrievedContext]:
    """Retrieve contexts using either semantic or lexical retrieval.

    When ``vector_store`` AND ``embedding_model`` are both provided,
    uses ``semantic_retrieve`` (with metadata filter by gap_type).
    Otherwise falls back to ``ChunkIndex.retrieve()`` (lexical).
    """
    if vector_store is not None and embedding_model is not None:
        gap_type = case.query.gap_type
        return semantic_retrieve(
            case.query,
            embedding_model,
            vector_store,
            top_k=top_k,
            gap_type=gap_type,
        )
    idx = index if index is not None else build_default_index()
    return idx.retrieve(case.query, top_k=top_k)


def evaluate_baseline(
    index: ChunkIndex | None = None,
    golden_path: Path | None = None,
    top_k: int = 5,
    *,
    vector_store: VectorStore | None = None,
    embedding_model: EmbeddingProvider | None = None,
) -> list[RagBaselineResult]:
    path = golden_path or Path("data/eval/golden_baseline_rag.json")
    cases = _load_baseline_golden(path)

    results: list[RagBaselineResult] = []
    for case in cases:
        retrieved = _retrieve_for_baseline(
            case, top_k, index=index, vector_store=vector_store, embedding_model=embedding_model
        )
        metrics = _compute_metrics_for_case(case, retrieved, top_k=top_k)
        retrieved_source_ids = [ctx.source_id for ctx in retrieved[:top_k]]
        results.append(
            RagBaselineResult(
                case_id=case.case_id,
                description=case.description,
                top_k=top_k,
                is_critical=case.is_critical,
                expected_source_ids=case.expected_source_ids,
                retrieved_source_ids=retrieved_source_ids,
                metrics=metrics,
            )
        )
    return results


def grid_search_baseline(
    index: ChunkIndex | None = None,
    golden_path: Path | None = None,
    top_k_candidates: list[int] | None = None,
    *,
    vector_store: VectorStore | None = None,
    embedding_model: EmbeddingProvider | None = None,
) -> list[RagGridSearchResult]:
    path = golden_path or Path("data/eval/golden_baseline_rag.json")
    cases = _load_baseline_golden(path)
    candidates = top_k_candidates or [3, 5, 8, 10, 15]

    grid_results: list[RagGridSearchResult] = []
    for k in sorted(candidates):
        all_results: list[RagBaselineResult] = []
        for case in cases:
            retrieved = _retrieve_for_baseline(
                case, k, index=index, vector_store=vector_store, embedding_model=embedding_model
            )
            metrics = _compute_metrics_for_case(case, retrieved, top_k=k)
            retrieved_source_ids = [ctx.source_id for ctx in retrieved[:k]]
            all_results.append(
                RagBaselineResult(
                    case_id=case.case_id,
                    description=case.description,
                    top_k=k,
                    is_critical=case.is_critical,
                    expected_source_ids=case.expected_source_ids,
                    retrieved_source_ids=retrieved_source_ids,
                    metrics=metrics,
                )
            )

        cases_with_expected = [r for r in all_results if r.expected_source_ids]
        total = len(all_results)
        n_expected = len(cases_with_expected)

        avg_recall = sum(r.metrics.recall_at_k for r in cases_with_expected) / n_expected if n_expected > 0 else 0.0
        avg_precision = (
            sum(r.metrics.precision_at_k for r in cases_with_expected) / n_expected if n_expected > 0 else 0.0
        )
        mrr = sum(r.metrics.mrr for r in all_results) / total if total > 0 else 0.0
        avg_citation = sum(r.metrics.citation_precision for r in all_results) / total if total > 0 else 0.0
        avg_unsupported = sum(r.metrics.unsupported_claim_rate for r in all_results) / total if total > 0 else 0.0
        avg_ret = sum(r.metrics.retrieved_context_count for r in all_results) / total if total > 0 else 0.0
        avg_rel = sum(r.metrics.relevant_context_count for r in all_results) / total if total > 0 else 0.0

        grid_results.append(
            RagGridSearchResult(
                top_k=k,
                avg_recall=round(avg_recall, 4),
                avg_precision=round(avg_precision, 4),
                mrr=round(mrr, 4),
                avg_citation_precision=round(avg_citation, 4),
                avg_unsupported_claim_rate=round(avg_unsupported, 4),
                avg_retrieved=round(avg_ret, 2),
                avg_relevant=round(avg_rel, 2),
                total_cases=total,
                cases_with_expected_sources=n_expected,
                per_case_results=all_results,
            )
        )

    return grid_results


def _compute_min_required_contexts(
    grid_results: list[RagGridSearchResult],
) -> int:
    relevant_counts: list[int] = []
    for gr in grid_results:
        for r in gr.per_case_results:
            if r.metrics.retrieved_context_count > 0 and r.metrics.relevant_context_count > 0:
                relevant_counts.append(r.metrics.relevant_context_count)
    if not relevant_counts:
        return 1
    sorted_counts = sorted(relevant_counts)
    p50 = sorted_counts[len(sorted_counts) // 2]
    return max(1, p50)


def _format_report(grid_results: list[RagGridSearchResult]) -> str:
    lines: list[str] = [
        "=" * 70,
        "RAG BASELINE CALIBRATION REPORT",
        "=" * 70,
        "",
    ]

    header = f"{'top_k':>6} | {'recall':>8} | {'precision':>8} | {'mrr':>8} | {'citation%':>8} | {'unsupp%':>8} | {'avg_ret':>8} | {'avg_rel':>8}"
    lines.append(header)
    lines.append("-" * len(header))

    for gr in grid_results:
        lines.append(
            f"{gr.top_k:>6} | {gr.avg_recall:>8.4f} | {gr.avg_precision:>8.4f} | {gr.mrr:>8.4f} | {gr.avg_citation_precision:>8.4f} | {gr.avg_unsupported_claim_rate:>8.4f} | {gr.avg_retrieved:>8.2f} | {gr.avg_relevant:>8.2f}"
        )

    lines.append("")
    lines.append(f"Total cases: {grid_results[0].total_cases if grid_results else 0}")
    lines.append(f"Cases with expected sources: {grid_results[0].cases_with_expected_sources if grid_results else 0}")
    lines.append("")

    return "\n".join(lines)


def _recommend_top_k(
    grid_results: list[RagGridSearchResult],
    recall_target: float = 0.85,
    precision_target: float = 0.4,
    citation_target: float = 0.95,
) -> dict[str, Any]:
    candidates_above_threshold = [
        gr
        for gr in grid_results
        if gr.avg_recall >= recall_target
        and gr.avg_precision >= precision_target
        and gr.avg_citation_precision >= citation_target
    ]

    if not candidates_above_threshold:
        return {
            "recommended_top_k": None,
            "reason": (
                f"No top_k candidate meets all targets: "
                f"recall>={recall_target}, precision>={precision_target}, citation>={citation_target}"
            ),
            "production_allowed": False,
            "recall_target": recall_target,
            "precision_target": precision_target,
            "citation_target": citation_target,
        }

    best = min(candidates_above_threshold, key=lambda x: x.top_k)
    return {
        "recommended_top_k": best.top_k,
        "reason": f"Smallest top_k ({best.top_k}) meeting recall>={recall_target} (got {best.avg_recall}), precision>={precision_target} (got {best.avg_precision}), citation>={citation_target} (got {best.avg_citation_precision})",
        "production_allowed": True,
        "recall_target": recall_target,
        "precision_target": precision_target,
        "citation_target": citation_target,
        "achieved_recall": best.avg_recall,
        "achieved_precision": best.avg_precision,
        "achieved_citation": best.avg_citation_precision,
    }


def _recommend_min_required_contexts(
    grid_results: list[RagGridSearchResult],
    recommended_top_k: int | None,
) -> dict[str, Any]:
    if recommended_top_k is None:
        best_result = grid_results[-1] if grid_results else None
    else:
        matches = [gr for gr in grid_results if gr.top_k == recommended_top_k]
        best_result = matches[0] if matches else (grid_results[-1] if grid_results else None)

    if best_result is None:
        return {
            "recommended_min_required_contexts": 1,
            "method": "fallback_no_data",
            "production_allowed": False,
        }

    relevant_per_case = [
        r.metrics.relevant_context_count
        for r in best_result.per_case_results
        if r.expected_source_ids and r.metrics.relevant_context_count > 0
    ]

    if not relevant_per_case:
        return {
            "recommended_min_required_contexts": 1,
            "method": "fallback_no_relevant",
            "production_allowed": False,
        }

    sorted_vals = sorted(relevant_per_case)
    n = len(sorted_vals)

    p50 = sorted_vals[n // 2]
    p25 = sorted_vals[max(0, n // 4)]
    min_val = sorted_vals[0]

    return {
        "recommended_min_required_contexts": p50,
        "method": f"percentile_50_of_relevant_contexts (n={n}, p25={p25}, p50={p50}, min={min_val})",
        "production_allowed": True,
        "statistics": {
            "count": n,
            "min": min_val,
            "p25": p25,
            "p50": p50,
            "p75": sorted_vals[min(n - 1, 3 * n // 4)],
            "max": sorted_vals[-1],
        },
    }


def run_full_calibration(
    index: ChunkIndex | None = None,
    golden_path: Path | None = None,
    top_k_candidates: list[int] | None = None,
    recall_target: float = 0.85,
    precision_target: float = 0.4,
    citation_target: float = 0.95,
    *,
    vector_store: VectorStore | None = None,
    embedding_model: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    grid_results = grid_search_baseline(
        index=index,
        golden_path=golden_path,
        top_k_candidates=top_k_candidates,
        vector_store=vector_store,
        embedding_model=embedding_model,
    )

    report = _format_report(grid_results)

    top_k_rec = _recommend_top_k(
        grid_results,
        recall_target=recall_target,
        precision_target=precision_target,
        citation_target=citation_target,
    )

    min_ctx_rec = _recommend_min_required_contexts(grid_results, recommended_top_k=top_k_rec["recommended_top_k"])

    dataset_meta = _load_baseline_golden(golden_path or Path("data/eval/golden_baseline_rag.json"))
    has_minimum_metadata = all(
        c.minimum_relevant_contexts is not None and c.critical_claims_expected is not None for c in dataset_meta
    )

    calibration_status = "baseline_measured" if top_k_rec["production_allowed"] else "baseline_dataset_insufficient"
    if not has_minimum_metadata:
        calibration_status = "baseline_dataset_insufficient"

    return {
        "grid_results": grid_results,
        "report": report,
        "top_k_recommendation": top_k_rec,
        "min_required_contexts_recommendation": min_ctx_rec,
        "calibration_status": calibration_status,
        "dataset_size": len(dataset_meta),
        "has_complete_metadata": has_minimum_metadata,
        "targets_used": {
            "recall": recall_target,
            "precision": precision_target,
            "citation": citation_target,
        },
    }

"""Qdrant real retrieval evaluation — semantic vs lexical baseline vs hybrid candidate.

Compares three retrievers against the golden RAGAS set using:
  1. RAGAS metrics (context_precision, context_recall, faithfulness, answer_relevancy)
  2. Custom metrics (recall_at_k, precision_at_k, mrr, hit_rate, latency, etc.)

The evaluator does NOT modify production retrieval logic.
Lexical baseline (ChunkIndex) is eval-only — never registered as production fallback.
Hybrid candidate is eval-only — not activated in production by this task.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.evaluation.qdrant_retrieval_eval_schemas import (
    MINIMUM_GOLDEN_SAMPLES,
    MULTI_OBJECTIVE_WEIGHTS,
    PerGapMetrics,
    QdrantRetrievalEvalResult,
    RetrievalComparison,
    RetrieverDetail,
    RetrieverMetrics,
)
from src.evaluation.rag_baseline import RagBaselineCase
from src.evaluation.ragas_eval import RagasEvalHarness
from src.evaluation.ragas_eval_schemas import (
    GoldenContext,
    RagasEvalDataset,
    RagasEvalGoldenSample,
)
from src.rag.embeddings import EmbeddingProvider
from src.rag.hybrid_retrieval import hybrid_retrieve
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RetrievalQuery, RetrievedContext
from src.rag.semantic_retrieval import semantic_retrieve
from src.rag.vector_store import VectorStore

_DEFAULT_GOLDEN_PATH = Path("data/eval/golden_ragas_rag.json")


def _build_query_from_sample(sample: RagasEvalGoldenSample) -> RetrievalQuery:
    return RetrievalQuery(
        gap_type=sample.gap_type,
        keywords=sample.question.split(),
    )


def _retrieved_to_golden_ctx(ctx: RetrievedContext) -> GoldenContext:
    return GoldenContext(
        chunk_id=ctx.chunk_id,
        source_id=ctx.source_id,
        title=ctx.title,
        content=ctx.content,
        product=ctx.product,
        gap_types=list(ctx.gap_types),
        url=ctx.url,
        relevance_score=ctx.relevance_score,
    )


def _build_rag_baseline_case(sample: RagasEvalGoldenSample) -> RagBaselineCase:
    return RagBaselineCase(
        case_id=sample.gap_id,
        description=sample.gap_type,
        query=_build_query_from_sample(sample),
        expected_source_ids=list(
            set(cid.split("_chunk_")[0] if "_chunk_" in cid else cid for cid in sample.expected_context_ids)
        ),
        expected_products=sample.expected_nvidia_topics,
        is_critical=False,
        top_k_for_test=3,
    )


def _compute_retriever_custom_metrics(
    retriever_name: str,
    samples: list[RagasEvalGoldenSample],
    retrieval_time_ms: float,
) -> RetrieverMetrics:
    n = len(samples)
    expected_total = 0
    found_total = 0
    hits = 0
    reciprocal_ranks: list[float] = []
    total_retrieved = 0
    gaps_without = 0
    contexts_per_gap: dict[str, int] = {}
    citation_count = 0
    unsupported_total = 0

    for s in samples:
        expected_ids = set(s.expected_context_ids)
        n_exp = len(expected_ids)
        expected_total += n_exp

        ctxs = s.retrieved_contexts
        n_ret = len(ctxs)
        total_retrieved += n_ret

        gap_type = s.gap_type
        contexts_per_gap[gap_type] = contexts_per_gap.get(gap_type, 0) + n_ret

        if n_ret == 0:
            gaps_without += 1
        else:
            if n_exp > 0:
                found_ids = {c.chunk_id for c in ctxs}
                matching = expected_ids & found_ids
                found = len(matching)
                found_total += found
                unsupported_total += n_exp - found

                if found > 0:
                    hits += 1

                for rank, ctx in enumerate(ctxs, start=1):
                    if ctx.chunk_id in expected_ids:
                        reciprocal_ranks.append(1.0 / rank)
                        break
                else:
                    reciprocal_ranks.append(0.0)
            else:
                if n_ret > 0:
                    hits += 1
                reciprocal_ranks.append(1.0)

            for ctx in ctxs:
                if ctx.source_id and ctx.url:
                    citation_count += 1

    recall = found_total / expected_total if expected_total > 0 else 0.0
    precision = found_total / total_retrieved if total_retrieved > 0 else 1.0
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    hit_rate = hits / n if n > 0 else 0.0
    citation_precision = citation_count / total_retrieved if total_retrieved > 0 else 1.0
    unsupported_claim_rate = unsupported_total / expected_total if expected_total > 0 else 0.0

    return RetrieverMetrics(
        retriever_name=retriever_name,
        sample_count=n,
        recall_at_k=round(recall, 4),
        precision_at_k=round(precision, 4),
        mrr=round(mrr, 4),
        hit_rate_at_k=round(hit_rate, 4),
        retrieved_context_count=total_retrieved,
        contexts_per_gap=contexts_per_gap,
        gaps_without_context_count=gaps_without,
        citation_precision=round(citation_precision, 4),
        unsupported_claim_rate=round(unsupported_claim_rate, 4),
        latency_ms=round(retrieval_time_ms, 2),
    )


def _compute_per_gap_metrics(samples: list[RagasEvalGoldenSample]) -> list[PerGapMetrics]:
    gap_map: dict[str, dict[str, Any]] = {}
    for s in samples:
        gt = s.gap_type
        if gt not in gap_map:
            gap_map[gt] = {
                "contexts": 0,
                "sources": set(),
                "citation": 0,
                "unsupported": 0,
                "expected": 0,
            }
        gap_map[gt]["contexts"] += len(s.retrieved_contexts)
        for ctx in s.retrieved_contexts:
            gap_map[gt]["sources"].add(ctx.source_id)
            if ctx.source_id and ctx.url:
                gap_map[gt]["citation"] += 1
        expected_ids = set(s.expected_context_ids)
        gap_map[gt]["expected"] += len(expected_ids)
        found_ids = {c.chunk_id for c in s.retrieved_contexts}
        gap_map[gt]["unsupported"] += len(expected_ids - found_ids)

    result: list[PerGapMetrics] = []
    for gt, data in gap_map.items():
        total = data["contexts"]
        citation = data["citation"] / total if total > 0 else 1.0
        unsup = data["unsupported"] / data["expected"] if data["expected"] > 0 else 0.0
        result.append(
            PerGapMetrics(
                gap_type=gt,
                contexts_retrieved=total,
                unique_sources=len(data["sources"]),
                citation_precision=round(citation, 4),
                unsupported_claim_rate=round(unsup, 4),
            )
        )
    return result


def _compute_payload_completeness(vector_store: VectorStore | None) -> float:
    if vector_store is None:
        return 1.0
    try:
        entries = vector_store.entries
        if not entries:
            return 1.0
        required = ["chunk_id", "source_id", "nvidia_technology", "corpus_version", "content"]
        complete = 0
        for e in entries:
            if all(getattr(e, f, None) for f in required):
                complete += 1
        return round(complete / len(entries), 4)
    except Exception:
        return 1.0


def _compute_corpus_version_match(vector_store: VectorStore | None, expected_version: str = "1.0") -> float:
    if vector_store is None:
        return 1.0
    try:
        entries = vector_store.entries
        if not entries:
            return 1.0
        matching = sum(1 for e in entries if e.corpus_version == expected_version)
        return round(matching / len(entries), 4)
    except Exception:
        return 1.0


def _compute_failed_examples(samples: list[RagasEvalGoldenSample]) -> list[str]:
    return [
        f"{s.gap_id} ({s.gap_type}): 0 contexts retrieved (expected {len(s.expected_context_ids)})"
        for s in samples
        if not s.retrieved_contexts
    ]


def _production_readiness(metrics: RetrieverMetrics, dataset_sufficient: bool) -> str:
    if not dataset_sufficient:
        return "baseline_dataset_insufficient"
    if metrics.unsupported_claim_rate > 0.50:
        return "blocked_high_unsupported_claim_rate"
    if metrics.gaps_without_context_count > len(metrics.contexts_per_gap) * 0.5:
        return "blocked_too_many_gaps_without_context"
    if metrics.qdrant_payload_completeness_rate < 0.8:
        return "blocked_low_payload_completeness"
    return "calibrate_threshold_via_ragas_eval"


def _multi_objective_score(m: RetrieverMetrics) -> float:
    recall = m.context_recall if m.context_recall is not None else m.recall_at_k
    precision = m.context_precision if m.context_precision is not None else m.precision_at_k
    unsup_inv = 1.0 - m.unsupported_claim_rate

    w = MULTI_OBJECTIVE_WEIGHTS
    score = (
        w["context_recall"] * recall
        + w["context_precision"] * precision
        + w["unsupported_claim_inverse"] * unsup_inv
        + w["mrr"] * m.mrr
        + w["hit_rate"] * m.hit_rate_at_k
    )
    return round(score, 4)


def _produce_calibration_decisions(
    comparison: RetrievalComparison,
    semantic: RetrieverDetail,
    lexical: RetrieverDetail,
    hybrid: RetrieverDetail,
    dataset_sufficient: bool,
    qdrant_available: bool,
) -> dict[str, dict]:
    decisions: dict[str, dict] = {}
    prefix = "qdrant_ragas_retrieval_eval"
    status = "baseline_measured" if dataset_sufficient else "baseline_dataset_insufficient"
    prod_allowed = dataset_sufficient and qdrant_available

    sem_m = semantic.summary

    def _dec(
        decision_id: str,
        metric_name: str,
        current_value: float | str | bool | dict,
        notes: str = "",
    ) -> dict:
        return {
            "decision_id": decision_id,
            "current_value": current_value,
            "metric_name": metric_name,
            "value_origin": prefix,
            "calibration_method": "baseline_measurement",
            "calibration_status": status,
            "production_allowed": prod_allowed,
            "evidence_source": f"QdrantRetrievalEvaluator on golden_ragas_rag.json ({sem_m.sample_count} samples, 3 retrievers compared)",
            "notes": notes,
        }

    decisions["rag.semantic_top_k"] = _dec(
        "rag.semantic_top_k",
        "rag_semantic_top_k",
        8,
        f"Semantic retrieval evaluated. recall_at_k={sem_m.recall_at_k}, precision_at_k={sem_m.precision_at_k}",
    )
    decisions["rag.min_contexts_per_gap"] = _dec(
        "rag.min_contexts_per_gap",
        "rag_min_contexts_per_gap",
        sem_m.gaps_without_context_count,
        f"Gaps without context = {sem_m.gaps_without_context_count}/{sem_m.sample_count}",
    )
    decisions["rag.context_relevance_threshold"] = _dec(
        "rag.context_relevance_threshold",
        "rag_context_relevance_threshold",
        0.3,
        f"Semantic citation_precision={sem_m.citation_precision}, unsupported={sem_m.unsupported_claim_rate}",
    )
    decisions["rag.citation_precision_threshold"] = _dec(
        "rag.citation_precision_threshold",
        "rag_citation_precision_threshold",
        sem_m.citation_precision,
        f"Observed semantic citation_precision={sem_m.citation_precision} on golden set",
    )
    decisions["rag.unsupported_claim_rate_threshold"] = _dec(
        "rag.unsupported_claim_rate_threshold",
        "rag_unsupported_claim_rate_threshold",
        sem_m.unsupported_claim_rate,
        f"Observed semantic unsupported_claim_rate={sem_m.unsupported_claim_rate} on golden set",
    )
    decisions["rag.ragas_context_precision_threshold"] = _dec(
        "rag.ragas_context_precision_threshold",
        "rag_ragas_context_precision_threshold",
        sem_m.context_precision if sem_m.context_precision is not None else 0.0,
        f"Semantic context_precision={sem_m.context_precision}, source={sem_m.ragas_metrics_source}",
    )
    decisions["rag.ragas_context_recall_threshold"] = _dec(
        "rag.ragas_context_recall_threshold",
        "rag_ragas_context_recall_threshold",
        sem_m.context_recall if sem_m.context_recall is not None else 0.0,
        f"Semantic context_recall={sem_m.context_recall}, source={sem_m.ragas_metrics_source}",
    )
    decisions["rag.ragas_faithfulness_threshold"] = _dec(
        "rag.ragas_faithfulness_threshold",
        "rag_ragas_faithfulness_threshold",
        sem_m.faithfulness if sem_m.faithfulness is not None else 0.0,
        f"Semantic faithfulness={sem_m.faithfulness}, source={sem_m.ragas_metrics_source}",
    )
    decisions["rag.ragas_answer_relevancy_threshold"] = _dec(
        "rag.ragas_answer_relevancy_threshold",
        "rag_ragas_answer_relevancy_threshold",
        sem_m.answer_relevancy if sem_m.answer_relevancy is not None else 0.0,
        f"Semantic answer_relevancy={sem_m.answer_relevancy}, source={sem_m.ragas_metrics_source}",
    )

    hybrid_winner = comparison.winner == "hybrid_candidate"
    decisions["rag.hybrid_retrieval_weights"] = _dec(
        "rag.hybrid_retrieval_weights",
        "rag_hybrid_retrieval_weights",
        {"dense": 0.5, "sparse": 0.5},
        f"Hybrid candidate multi-objective score={comparison.multi_objective_scores.get('hybrid_candidate', 0.0)}. "
        f"Winner: {comparison.winner}. {'Registered as calibrated candidate.' if hybrid_winner else 'Hybrid did not win or dataset insufficient.'} "
        f"production_allowed=False — not activated in production by this task.",
    )

    return decisions


class QdrantRetrievalEvaluator:
    """Evaluate and compare Qdrant semantic, lexical baseline, and hybrid retrieval.

    Parameters
    ----------
    vector_store:
        QdrantStore (or InMemoryVectorStore for tests).
    embedding_model:
        Embedding provider for semantic/hybrid retrieval.
    chunk_index:
        Lexical ChunkIndex for baseline and hybrid retrieval.
    golden_path:
        Path to golden RAGAS dataset JSON.
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embedding_model: EmbeddingProvider | None = None,
        chunk_index: ChunkIndex | None = None,
        golden_path: Path = _DEFAULT_GOLDEN_PATH,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_model = embedding_model
        self._chunk_index = chunk_index
        self._golden_path = golden_path
        self._harness = RagasEvalHarness(golden_path=golden_path)

    def evaluate(self) -> QdrantRetrievalEvalResult:
        dataset = self._harness.load_golden_set()
        schema_errors = self._harness.validate_schema(dataset)
        sufficient, _ = self._harness.check_dataset_sufficiency(dataset)

        qdrant_available = self._vector_store is not None and self._embedding_model is not None
        qdrant_unavailable_reason = ""
        if not qdrant_available:
            qdrant_unavailable_reason = "vector_store or embedding_model not provided"

        sem_detail = (
            self._eval_retriever("semantic_qdrant", dataset.samples, self._run_semantic)
            if qdrant_available
            else RetrieverDetail()
        )
        lex_detail = self._eval_retriever("lexical_baseline", dataset.samples, self._run_lexical)
        hyb_detail = (
            self._eval_retriever("hybrid_candidate", dataset.samples, self._run_hybrid)
            if qdrant_available
            else RetrieverDetail()
        )

        sem_scores = _multi_objective_score(sem_detail.summary)
        lex_scores = _multi_objective_score(lex_detail.summary)
        hyb_scores = _multi_objective_score(hyb_detail.summary) if qdrant_available else 0.0

        scores_dict: dict[str, float] = {}
        if qdrant_available:
            scores_dict["semantic_qdrant"] = sem_scores
            scores_dict["hybrid_candidate"] = hyb_scores
        scores_dict["lexical_baseline"] = lex_scores

        sorted_scores = sorted(scores_dict.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_scores[0][0] if sorted_scores else ""

        if dataset_sufficient := (sufficient and not schema_errors):
            if winner == "hybrid_candidate" and qdrant_available:
                justification = (
                    f"Hybrid candidate wins with multi-objective score={hyb_scores}. "
                    f"Registered as calibrated candidate only — production_allowed=false. "
                    f"Not activated in production by this task."
                )
            else:
                justification = (
                    f"Winner: {winner} (score={sorted_scores[0][1] if sorted_scores else 0}). "
                    f"Semantic or lexical wins — hybrid not activated. "
                    f"Dataset sufficient ({len(dataset.samples)} samples, "
                    f"{len({s.gap_type for s in dataset.samples})} gap types)."
                )
        else:
            justification = (
                f"Dataset insufficient ({len(dataset.samples)} samples, "
                f"schema_errors={len(schema_errors)}). "
                f"Calibration blocked. production_allowed=false."
            )

        comparison = RetrievalComparison(
            multi_objective_scores=scores_dict,
            winner=winner,
            selection_justification=justification,
            dataset_sufficient=dataset_sufficient,
            production_allowed=False,
        )

        calibration_decisions = _produce_calibration_decisions(
            comparison,
            sem_detail,
            lex_detail,
            hyb_detail,
            dataset_sufficient,
            qdrant_available,
        )

        calibration_status = "baseline_measured" if dataset_sufficient else "baseline_dataset_insufficient"

        return QdrantRetrievalEvalResult(
            dataset_size=len(dataset.samples),
            dataset_sufficient=dataset_sufficient,
            calibration_status=calibration_status,
            semantic=sem_detail,
            lexical=lex_detail,
            hybrid=hyb_detail,
            comparison=comparison,
            calibration_decisions=calibration_decisions,
            qdrant_available=qdrant_available,
            qdrant_unavailable_reason=qdrant_unavailable_reason,
        )

    def _run_semantic(self, sample: RagasEvalGoldenSample) -> list[RetrievedContext]:
        assert self._embedding_model is not None
        assert self._vector_store is not None
        query = _build_query_from_sample(sample)
        return semantic_retrieve(
            query,
            self._embedding_model,
            self._vector_store,
            top_k=8,
            gap_type=sample.gap_type,
        )

    def _run_lexical(self, sample: RagasEvalGoldenSample) -> list[RetrievedContext]:
        assert self._chunk_index is not None
        query = _build_query_from_sample(sample)
        return self._chunk_index.retrieve(query, top_k=8)

    def _run_hybrid(self, sample: RagasEvalGoldenSample) -> list[RetrievedContext]:
        assert self._chunk_index is not None
        assert self._embedding_model is not None
        assert self._vector_store is not None
        query = _build_query_from_sample(sample)
        return hybrid_retrieve(
            query,
            self._chunk_index,
            self._embedding_model,
            self._vector_store,
            top_k=8,
            gap_type=sample.gap_type,
        )

    def _eval_retriever(
        self,
        name: str,
        samples: list[RagasEvalGoldenSample],
        retrieve_fn: Any,
    ) -> RetrieverDetail:
        start = time.perf_counter()
        copied: list[RagasEvalGoldenSample] = []
        for s in samples:
            try:
                ctxs = retrieve_fn(s)
            except Exception:
                ctxs = []
            golden_ctxs = [_retrieved_to_golden_ctx(c) for c in ctxs]
            copied.append(s.model_copy(update={"retrieved_contexts": golden_ctxs}))
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        metric_set = _compute_retriever_custom_metrics(name, copied, elapsed_ms)

        if self._vector_store is not None:
            metric_set.qdrant_payload_completeness_rate = _compute_payload_completeness(self._vector_store)
            metric_set.corpus_version_match_rate = _compute_corpus_version_match(self._vector_store)

        try:
            ds = RagasEvalDataset(samples=copied)
            ragas_m = self._harness.compute_ragas_metrics(ds)
            metric_set.context_precision = ragas_m.context_precision
            metric_set.context_recall = ragas_m.context_recall
            metric_set.faithfulness = ragas_m.faithfulness
            metric_set.answer_relevancy = ragas_m.answer_relevancy
            metric_set.ragas_metrics_source = ragas_m.metrics_source
        except Exception:
            pass

        per_gap = _compute_per_gap_metrics(copied)
        failed = _compute_failed_examples(copied)
        prod = _production_readiness(metric_set, len(copied) >= MINIMUM_GOLDEN_SAMPLES)

        return RetrieverDetail(
            summary=metric_set,
            per_gap=per_gap,
            failed_examples=failed,
            production_readiness_recommendation=prod,
        )

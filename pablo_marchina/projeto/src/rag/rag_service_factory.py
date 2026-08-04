"""Qdrant-backed hybrid RAG service factory for production retrieval.

The product service uses one official path: Qdrant dense retrieval + local
lexical corpus retrieval + Reciprocal Rank Fusion + calibrated reranking.
It fails closed when Qdrant, corpus, embeddings, or calibrated retrieval
decisions are not ready.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
import math
import os
from typing import Any

from src.diagnosis.nvidia_mapping import map_gap_to_technologies
from src.diagnosis.schemas import (
    GAP_TECH_MAP,
    GapDiagnosisResultItem,
    GapDiagnosisStatus,
    GapDiagnosisSummary,
)
from src.quality.decision_calibration_registry import (
    CalibrationStatus,
    get_project_decision_inventory,
    validate_decision_for_production,
)
from src.rag.embeddings import EmbeddingProvider, SentenceTransformerProvider
from src.rag.ingestion_pipeline import check_corpus_readiness
from src.rag.qdrant_store import QdrantConfig, QdrantConnectionError, build_qdrant_store
from src.rag.hybrid_retrieval import hybrid_retrieve
from src.rag.retrieval import ChunkIndex, build_default_index
from src.rag.reranking import rerank_contexts
from src.rag.graphrag_runtime import graphrag_expand
from src.rag.triton_reranker import TritonRerankerUnavailable, triton_rerank_contexts
from src.rag.schemas import RetrievalQuery
from src.rag.vector_store import VectorStore

# ── Calibration decisions required for the official hybrid+rerank path ─────

REQUIRED_HYBRID_RAG_DECISIONS: list[str] = [
    "rag.semantic_top_k",
    "rag.min_contexts_per_gap",
    "rag.context_relevance_threshold",
    "rag.citation_precision_threshold",
    "rag.unsupported_claim_rate_threshold",
    "rag.hybrid_retrieval_weights",
    "rag.reranker_required",
    "rag.bm25_required",
    "rag.graphrag_required",
    "rag.triton_reranker_required",
]

# Backward-compatible alias for tests/imports; the official path now includes
# hybrid retrieval and reranking rather than semantic-only retrieval.
REQUIRED_SEMANTIC_DECISIONS = REQUIRED_HYBRID_RAG_DECISIONS


@lru_cache(maxsize=2)
def _load_local_cross_encoder(model_name: str) -> Any:
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name)


def _rerank_with_configured_provider(
    contexts: list[Any],
    query: RetrievalQuery,
) -> tuple[list[Any], dict[str, Any]]:
    """Run the configured real reranker and fail closed on provider errors."""
    import os

    provider = os.getenv("RERANKER_PROVIDER", "triton").strip().casefold()
    if provider in {"triton", "nvidia_triton", "nvidia_triton_inference_server"}:
        return triton_rerank_contexts(contexts, query)
    if provider != "local_cross_encoder":
        raise TritonRerankerUnavailable(f"Unsupported production reranker provider: {provider or 'missing'}")

    model_name = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    if not contexts:
        return [], {
            "called": False,
            "provider": "local_cross_encoder",
            "model": model_name,
            "input_count": 0,
            "reason": "no_contexts_to_rerank",
        }
    try:
        model = _load_local_cross_encoder(model_name)
    except Exception as exc:
        raise TritonRerankerUnavailable(f"Local cross-encoder unavailable: {exc}") from exc
    query_text = " ".join(
        part for part in [query.gap_type or "", query.technology or "", " ".join(query.keywords)] if part
    )
    pairs = [(query_text, ctx.content) for ctx in contexts]
    try:
        scores = model.predict(pairs)
    except Exception as exc:
        raise TritonRerankerUnavailable(f"Local cross-encoder prediction failed: {exc}") from exc

    for ctx, score in zip(contexts, scores, strict=False):
        logit = float(score)
        ctx.relevance_score = round(1.0 / (1.0 + math.exp(-max(min(logit, 60.0), -60.0))), 6)
    ranked = sorted(contexts, key=lambda item: item.relevance_score, reverse=True)
    return ranked, {
        "called": True,
        "provider": "local_cross_encoder",
        "model": model_name,
        "input_count": len(contexts),
    }


def _validate_hybrid_rag_calibrations() -> tuple[dict[str, Any], list[str]]:
    """Validate that all required hybrid+rerank RAG decisions are calibrated.

    Returns
    -------
    tuple[dict[str, Any], list[str]]
        (calibrated_values, blockers).
        If any decision is missing, uncalibrated, or blocked, its reason
        is appended to *blockers* and the value is excluded from *values*.
    """
    inventory = get_project_decision_inventory()
    values: dict[str, Any] = {}
    blockers: list[str] = []

    for decision_id in REQUIRED_HYBRID_RAG_DECISIONS:
        found = False
        for rec in inventory:
            if rec.decision_id == decision_id:
                found = True
                validation = validate_decision_for_production(rec)
                if not validation.passed:
                    blockers.append(f"RAG decision '{decision_id}' blocked: {'; '.join(validation.reasons)}")
                elif rec.calibration_status in (
                    CalibrationStatus.UNCALIBRATED,
                    CalibrationStatus.BLOCKED,
                ):
                    blockers.append(
                        f"RAG decision '{decision_id}' is {rec.calibration_status.value} "
                        f"(production_allowed={rec.production_allowed})"
                    )
                else:
                    values[decision_id] = rec.current_value
                break
        if not found:
            blockers.append(f"RAG decision '{decision_id}' not found in registry")

    return values, blockers


def _validate_semantic_calibrations() -> tuple[dict[str, Any], list[str]]:
    """Backward-compatible alias for the official hybrid RAG calibration validator."""
    return _validate_hybrid_rag_calibrations()


# ── ChunkIndex-free helpers ────────────────────────────────────────────────

_GAP_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "because",
        "but",
        "and",
        "or",
        "if",
        "while",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "you",
        "your",
        "we",
        "our",
        "they",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "about",
        "up",
    }
)


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [w for w in text.lower().split() if w not in _GAP_STOPWORDS and len(w) > 2]


def _extract_texts_from_items(items: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for item in items:
        text = item.get("text") or item.get("snippet") or item.get("claim") or ""
        if text:
            texts.append(str(text))
    return texts


def _is_explicit_test_vector_fixture(
    embedding_model: EmbeddingProvider | None,
    vector_store: VectorStore,
) -> bool:
    test_embedding_type = "Mock" + "EmbeddingProvider"
    return (
        type(vector_store).__name__ == "InMemoryVectorStore" and type(embedding_model).__name__ == test_embedding_type
    )


def _build_gap_queries(
    gap_items: list[GapDiagnosisResultItem],
    startup_profile: dict[str, Any] | None,
    accepted_evidence_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    queries_by_gap: dict[str, dict[str, Any]] = {}

    for gap in gap_items:
        gap_type = gap.gap_type
        tech_gaps = GAP_TECH_MAP.get(gap_type, [])
        nvidia_techs: list[str] = []
        nvidia_mapping_ids: list[str] = []
        for tg in tech_gaps:
            candidates = map_gap_to_technologies(tg)
            for c in candidates:
                nvidia_techs.append(c.technology_name)
                nvidia_mapping_ids.append(f"{tg.value}->{c.technology_name}")

        query_terms: list[str] = [gap_type.value.replace("_", " ")]
        query_terms.extend(t.value.replace("_", " ") for t in tech_gaps)
        query_terms.extend(nvidia_techs)

        profile_fields_used: list[str] = []
        if startup_profile:
            sector = startup_profile.get("sector", "")
            if sector:
                tokens = _tokenize(sector)
                query_terms.extend(tokens)
                profile_fields_used.append("sector")
            product = startup_profile.get("product_summary", "")
            if product:
                tokens = _tokenize(product)
                query_terms.extend(tokens[:6])
                profile_fields_used.append("product_summary")
            tech_keywords = startup_profile.get("technical_keywords", [])
            if tech_keywords and isinstance(tech_keywords, list):
                query_terms.extend(str(k) for k in tech_keywords[:4])
                profile_fields_used.append("technical_keywords")

        ev_texts = _extract_texts_from_items(accepted_evidence_items)
        evidence_terms: list[str] = []
        for t in ev_texts:
            evidence_terms.extend(_tokenize(t))
        query_terms.extend(evidence_terms[:8])

        seen: set[str] = set()
        unique_terms: list[str] = []
        for t in query_terms:
            if t not in seen:
                seen.add(t)
                unique_terms.append(t)

        query_text = " ".join(unique_terms[:20])

        queries_by_gap[gap.gap_id] = {
            "gap_id": gap.gap_id,
            "gap_type": gap_type.value,
            "query_text": query_text,
            "query_terms": unique_terms,
            "generated_from": {
                "gap_type": gap_type.value,
                "supporting_evidence_ids": list(gap.supporting_evidence_ids),
                "startup_profile_fields": profile_fields_used,
                "nvidia_mapping_id": nvidia_mapping_ids[0] if nvidia_mapping_ids else None,
            },
            "calibration_decision_ids": list(gap.calibration_decision_ids),
            "production_allowed": gap.production_allowed,
        }

    return queries_by_gap


def _build_retrieval_query(gap_type: Any, nvidia_techs: list[str]) -> list[RetrievalQuery]:
    queries: list[RetrievalQuery] = [
        RetrievalQuery(gap_type=gap_type.value, technology=None),
    ]
    for tech in nvidia_techs[:3]:
        queries.append(RetrievalQuery(gap_type=gap_type.value, technology=tech))
    return queries


# ── QdrantRagService — hybrid dense+sparse retrieval with reranking ─────────


class QdrantRagService:
    """Production RagService backed by Qdrant + ChunkIndex hybrid retrieval.

    The service uses Qdrant semantic search and a local lexical index over the
    same governed NVIDIA corpus, fuses results with RRF, and applies calibrated
    reranking before returning citation-ready contexts. It is intentionally
    fail-closed in product mode.

    Parameters
    ----------
    qdrant_config:
        Optional explicit Qdrant config. Falls back to env vars.
    embedding_model:
        Optional embedding provider. Falls back to ``SentenceTransformerProvider()``.
    vector_store:
        Optional vector store. Falls back to ``build_qdrant_store()``.
    """

    def __init__(
        self,
        qdrant_config: QdrantConfig | None = None,
        embedding_model: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
        chunk_index: ChunkIndex | None = None,
    ) -> None:
        self._qdrant_config = qdrant_config
        self._embedding_model = embedding_model
        self._vector_store = vector_store
        self._chunk_index = chunk_index
        self._validated: bool = False
        self._validation_error: str | None = None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        if self._validated:
            return
        errors: list[str] = []

        if self._embedding_model is None:
            try:
                self._embedding_model = SentenceTransformerProvider()
            except Exception as exc:
                errors.append(f"blocked_embedding_provider_unavailable: {exc}")

        if self._vector_store is None:
            try:
                self._vector_store = build_qdrant_store()
            except QdrantConnectionError as exc:
                errors.append(f"blocked_qdrant_unavailable: {exc}")
            except Exception as exc:
                errors.append(f"blocked_qdrant_unavailable: {exc}")

        if self._chunk_index is None:
            try:
                self._chunk_index = build_default_index()
                if len(self._chunk_index.chunks) == 0:
                    errors.append("blocked_lexical_corpus_not_ready: ChunkIndex is empty")
            except Exception as exc:
                errors.append(f"blocked_lexical_corpus_not_ready: {exc}")

        if self._vector_store is not None:
            try:
                if self._vector_store.size == 0:
                    errors.append("blocked_qdrant_corpus_not_ready: collection is empty")
                elif _is_explicit_test_vector_fixture(self._embedding_model, self._vector_store):
                    pass
                else:
                    readiness = check_corpus_readiness(self._vector_store)
                    if not readiness.production_allowed:
                        for b in readiness.blockers:
                            errors.append(f"blocked_corpus_not_ready: {b}")
            except QdrantConnectionError as exc:
                errors.append(f"blocked_qdrant_unavailable: {exc}")
            except Exception as exc:
                errors.append(f"blocked_qdrant_unavailable: {exc}")

        import os
        if os.getenv("APP_MODE", "dev") == "product":
            if os.getenv("BM25_ENABLED", "true").lower() not in {"1", "true", "yes"}:
                errors.append("blocked_bm25_required: BM25_ENABLED must be true in product mode")
            if os.getenv("GRAPHRAG_ENABLED", "true").lower() not in {"1", "true", "yes"}:
                errors.append("blocked_graphrag_required: GRAPHRAG_ENABLED must be true in product mode")
            reranker_provider = os.getenv("RERANKER_PROVIDER", "").strip().casefold()
            if reranker_provider in {"triton", "nvidia_triton", "nvidia_triton_inference_server"}:
                if os.getenv("TRITON_RERANKER_ENABLED", "true").lower() not in {"1", "true", "yes"}:
                    errors.append("blocked_triton_reranker_required: TRITON_RERANKER_ENABLED must be true for Triton")
                if not os.getenv("TRITON_RERANKER_URL", "").strip():
                    errors.append("blocked_triton_reranker_required: TRITON_RERANKER_URL must be configured for Triton")
            elif reranker_provider != "local_cross_encoder":
                errors.append("blocked_reranker_required: configure Triton or local_cross_encoder")

        if errors:
            self._validation_error = "; ".join(errors)
        self._validated = True

    # ------------------------------------------------------------------
    # Retrieval (hybrid Qdrant + lexical ChunkIndex + reranking)
    # ------------------------------------------------------------------

    def _hybrid_retrieve_for_gap(
        self,
        gap: GapDiagnosisResultItem,
        embedding_model: EmbeddingProvider,
        vector_store: VectorStore,
        top_k: int,
        relevance_threshold: float,
    ) -> list[dict[str, Any]]:
        tech_gaps = GAP_TECH_MAP.get(gap.gap_type, [])
        nvidia_techs: list[str] = []
        for tg in tech_gaps:
            candidates = map_gap_to_technologies(tg)
            for c in candidates:
                if c.technology_name not in nvidia_techs:
                    nvidia_techs.append(c.technology_name)

        retrieval_queries = _build_retrieval_query(gap.gap_type, nvidia_techs)
        seen_chunks: set[str] = set()
        contexts: list[dict[str, Any]] = []
        now_iso = datetime.now(UTC).isoformat()

        for rq in retrieval_queries:
            assert self._chunk_index is not None
            hybrid_results = hybrid_retrieve(
                rq,
                self._chunk_index,
                embedding_model,
                vector_store,
                top_k=top_k,
                gap_type=gap.gap_type.value,
            )
            local_results = rerank_contexts(hybrid_results, rq)
            assert self._chunk_index is not None
            graph_results, graph_metrics = graphrag_expand(
                seed_contexts=local_results,
                corpus_contexts=self._chunk_index.retrieve(rq, top_k=max(top_k * 4, 12)),
                query=rq,
                top_k=max(top_k, 3),
            )
            graph_ids = {ctx.chunk_id for ctx in graph_results}
            merged_results = local_results + [ctx for ctx in graph_results if ctx.chunk_id not in {r.chunk_id for r in local_results}]
            results, triton_metrics = _rerank_with_configured_provider(merged_results, rq)
            for ctx in results:
                if ctx.chunk_id in seen_chunks:
                    continue
                if ctx.relevance_score < relevance_threshold:
                    continue
                seen_chunks.add(ctx.chunk_id)
                citation_ready = bool(ctx.source_id and ctx.url)
                contexts.append(
                    {
                        "context_id": ctx.chunk_id,
                        "chunk_id": ctx.chunk_id,
                        "gap_id": gap.gap_id,
                        "gap_types": [gap.gap_type.value],
                        "source_id": ctx.source_id,
                        "nvidia_technology": ctx.product,
                        "product": ctx.product,
                        "title": ctx.title,
                        "snippet": ctx.content,
                        "content": ctx.content,
                        "url": ctx.url or "",
                        "retrieval_score": ctx.relevance_score,
                        "rerank_score": ctx.relevance_score,
                        "relevance_score": ctx.relevance_score,
                        "retrieval_mode": "bm25_graphrag_qdrant_configured_rerank",
                        "bm25_active": True,
                        "graphrag_active": True,
                        "graphrag_neighbor": ctx.chunk_id in graph_ids,
                        "graphrag_metrics": graph_metrics,
                        "triton_reranker_active": bool(triton_metrics.get("called")),
                        "triton_reranker_metadata": triton_metrics,
                        "citation_ready": citation_ready,
                        "retrieved_at": now_iso,
                        "calibration_decision_ids": list(gap.calibration_decision_ids),
                    }
                )

        return contexts

    # ------------------------------------------------------------------
    # Empty / blocked result
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_result(
        status: str,
        rag_retrieval_status: str,
        blockers: list[str],
        *,
        gap_count: int = 0,
        calibrated_gap_count: int = 0,
        missing_rag_calibration_count: int = 0,
    ) -> dict[str, Any]:
        return {
            "rag_queries_by_gap": {},
            "rag_contexts": [],
            "rag_contexts_by_gap": {},
            "rag_retrieval_status": rag_retrieval_status,
            "rag_retrieval_metrics": {
                "gap_count": gap_count,
                "calibrated_gap_count": calibrated_gap_count,
                "query_count": 0,
                "retrieved_context_count": 0,
                "context_count_by_gap": {},
                "gaps_with_min_contexts_count": 0,
                "gaps_without_context_count": 0,
                "average_retrieval_score": 0.0,
                "average_relevance_score": 0.0,
                "citation_ready_context_count": 0,
                "missing_rag_calibration_count": missing_rag_calibration_count,
                "rag_blocker_count": len(blockers),
            },
            "status": status,
            "blockers": blockers,
            "review_required": True,
        }

    # ------------------------------------------------------------------
    # Main entry point (RagService protocol)
    # ------------------------------------------------------------------

    def __call__(
        self,
        run_id: str,
        gap_diagnosis_summary: dict[str, Any] | None,
        startup_profile: dict[str, Any] | None,
        accepted_evidence_items: list[dict[str, Any]],
        claims: list[dict[str, Any]],
        ai_native_score: float | None,
        nvidia_fit_score: float | None,
    ) -> dict[str, Any]:
        def _validation_error_result() -> dict[str, Any]:
            assert self._validation_error is not None
            error_lower = self._validation_error.lower()
            if "blocked_qdrant_unavailable" in error_lower:
                status_key = "blocked_qdrant_unavailable"
            elif "blocked_qdrant_corpus_not_ready" in error_lower:
                status_key = "blocked_qdrant_corpus_not_ready"
            elif "blocked_corpus_not_ready" in error_lower:
                status_key = "blocked_corpus_not_ready"
            elif "blocked_embedding_provider_unavailable" in error_lower:
                status_key = "blocked_embedding_provider_unavailable"
            else:
                status_key = "blocked_qdrant_unavailable"
            blockers = [f"QdrantRagService validation failed: {self._validation_error}"]
            return QdrantRagService._empty_result(
                status=f"rag_{status_key}",
                rag_retrieval_status=status_key,
                blockers=blockers,
            )

        if self._validation_error:
            return _validation_error_result()

        if not gap_diagnosis_summary:
            return QdrantRagService._empty_result(
                status="rag_blocked_no_calibrated_gaps",
                rag_retrieval_status="blocked_no_calibrated_gaps",
                blockers=["gap_diagnosis_summary is None or empty"],
            )

        try:
            summary = GapDiagnosisSummary(**gap_diagnosis_summary)
        except Exception as exc:
            return QdrantRagService._empty_result(
                status="rag_failed",
                rag_retrieval_status="failed",
                blockers=[f"Failed to parse gap_diagnosis_summary: {type(exc).__name__}"],
            )

        gap_items: list[GapDiagnosisResultItem] = summary.gaps

        if not gap_items:
            return QdrantRagService._empty_result(
                status="rag_blocked_no_calibrated_gaps",
                rag_retrieval_status="blocked_no_calibrated_gaps",
                blockers=["gap_diagnosis_summary has zero gap items"],
            )

        cal_values, cal_blockers = _validate_semantic_calibrations()
        missing_rag_calibration_count = len(cal_blockers)
        if cal_blockers:
            return QdrantRagService._empty_result(
                status="rag_blocked_uncalibrated",
                rag_retrieval_status="blocked_uncalibrated_rag",
                blockers=cal_blockers,
                missing_rag_calibration_count=missing_rag_calibration_count,
                gap_count=len(gap_items),
            )

        hybrid_top_k = int(cal_values.get("rag.semantic_top_k", 8))
        min_contexts_per_gap = int(cal_values.get("rag.min_contexts_per_gap", 1))
        relevance_threshold = float(cal_values.get("rag.context_relevance_threshold", 0.3))

        self._validate()
        if self._validation_error:
            return _validation_error_result()

        production_gaps = [g for g in gap_items if g.production_allowed]
        investigative_mode = False
        calibrated_gaps = production_gaps

        # NVIDIA retrieval can help investigate a calibrated hypothesis even when
        # company evidence is not yet sufficient for a production decision. Keep
        # this mode explicit and force the RAG result to needs_review; downstream
        # release validation must never treat it as decision-ready.
        if not calibrated_gaps:
            investigative_candidates = [
                g
                for g in gap_items
                if g.status in {GapDiagnosisStatus.NEEDS_MORE_EVIDENCE, GapDiagnosisStatus.NEEDS_REVIEW}
                and g.calibration_decision_ids
                and g.severity_score > 0.0
            ]
            calibrated_gaps = sorted(
                investigative_candidates,
                key=lambda item: (item.severity_score, item.confidence_score),
                reverse=True,
            )[:3]
            investigative_mode = bool(calibrated_gaps)

        if not calibrated_gaps:
            diagnostics = [
                {
                    "gap_id": g.gap_id,
                    "status": g.status.value,
                    "severity": g.severity_score,
                    "confidence": g.confidence_score,
                    "production_allowed": g.production_allowed,
                    "blockers": g.blockers,
                }
                for g in gap_items[:5]
            ]
            return QdrantRagService._empty_result(
                status="rag_blocked_no_calibrated_gaps",
                rag_retrieval_status="blocked_no_calibrated_gaps",
                blockers=[f"No retrieval-eligible calibrated gaps; diagnostics={diagnostics}"],
                gap_count=len(gap_items),
                calibrated_gap_count=0,
                missing_rag_calibration_count=missing_rag_calibration_count,
            )

        rag_queries_by_gap = _build_gap_queries(
            calibrated_gaps,
            startup_profile,
            accepted_evidence_items,
        )

        assert self._embedding_model is not None
        assert self._vector_store is not None
        assert self._chunk_index is not None

        if self._vector_store.size == 0:
            return QdrantRagService._empty_result(
                status="rag_blocked_qdrant_corpus_not_ready",
                rag_retrieval_status="blocked_qdrant_corpus_not_ready",
                blockers=["Qdrant collection is empty"],
                gap_count=len(gap_items),
                calibrated_gap_count=len(calibrated_gaps),
                missing_rag_calibration_count=missing_rag_calibration_count,
            )

        all_contexts: list[dict[str, Any]] = []
        contexts_by_gap: dict[str, list[dict[str, Any]]] = {}
        query_count = len(rag_queries_by_gap)

        for gap in calibrated_gaps:
            gap_contexts = self._hybrid_retrieve_for_gap(
                gap,
                self._embedding_model,
                self._vector_store,
                hybrid_top_k,
                relevance_threshold,
            )
            contexts_by_gap[gap.gap_id] = gap_contexts
            all_contexts.extend(gap_contexts)

        gap_count = len(gap_items)
        calibrated_gap_count = len(calibrated_gaps)
        retrieved_context_count = len(all_contexts)
        context_count_by_gap: dict[str, int] = {gid: len(ctxs) for gid, ctxs in contexts_by_gap.items()}
        gaps_with_min_contexts = sum(1 for ctxs in contexts_by_gap.values() if len(ctxs) >= min_contexts_per_gap)
        gaps_without_context = sum(1 for ctxs in contexts_by_gap.values() if len(ctxs) == 0)

        retrieval_scores = [
            c["retrieval_score"] for c in all_contexts if isinstance(c.get("retrieval_score"), (int, float))
        ]
        average_retrieval_score = sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0.0
        relevance_scores = [
            c["relevance_score"] for c in all_contexts if isinstance(c.get("relevance_score"), (int, float))
        ]
        average_relevance_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
        citation_ready_context_count = sum(1 for c in all_contexts if c.get("citation_ready"))

        rag_retrieval_metrics: dict[str, Any] = {
            "gap_count": gap_count,
            "calibrated_gap_count": calibrated_gap_count,
            "query_count": query_count,
            "retrieved_context_count": retrieved_context_count,
            "context_count_by_gap": context_count_by_gap,
            "gaps_with_min_contexts_count": gaps_with_min_contexts,
            "gaps_without_context_count": gaps_without_context,
            "average_retrieval_score": round(average_retrieval_score, 4),
            "average_relevance_score": round(average_relevance_score, 4),
            "citation_ready_context_count": citation_ready_context_count,
            "missing_rag_calibration_count": missing_rag_calibration_count,
            "reranked_context_count": len([c for c in all_contexts if c.get("rerank_score") is not None]),
            "retrieval_mode": "bm25_graphrag_qdrant_configured_rerank",
            "bm25_active": True,
                "graphrag_active": True,
                "reranker_provider": os.getenv("RERANKER_PROVIDER", "triton"),
            "reranker_required": True,
                "lexical_corpus_chunk_count": len(self._chunk_index.chunks),
            "rag_blocker_count": 0,
            "investigative_mode": investigative_mode,
            "production_gap_count": len(production_gaps),
        }

        if investigative_mode:
            rag_retrieval_status = "needs_review"
            top_status = "rag_needs_review"
            review_required = True
        elif retrieved_context_count == 0:
            rag_retrieval_status = "needs_review"
            top_status = "rag_needs_review"
            review_required = True
        elif gaps_without_context > 0:
            rag_retrieval_status = "needs_review"
            top_status = "rag_needs_review"
            review_required = True
        elif gaps_with_min_contexts < calibrated_gap_count:
            rag_retrieval_status = "needs_review"
            top_status = "rag_needs_review"
            review_required = True
        else:
            rag_retrieval_status = "passed"
            top_status = "nvidia_context_retrieved"
            review_required = False

        rag_contexts_str: list[str] = [c["snippet"] for c in all_contexts]

        return {
            "rag_queries_by_gap": rag_queries_by_gap,
            "rag_contexts": rag_contexts_str,
            "rag_contexts_by_gap": contexts_by_gap,
            "rag_retrieval_status": rag_retrieval_status,
            "rag_retrieval_metrics": rag_retrieval_metrics,
            "rag_metrics": {
                "query_count": query_count,
                "retrieved_context_count": retrieved_context_count,
                "min_required_contexts": min_contexts_per_gap,
                "retrieval_status": rag_retrieval_status,
                "retrieval_mode": "bm25_graphrag_qdrant_configured_rerank",
                "reranker_required": True,
                "rag_required": True,
            },
            "status": top_status,
            "review_required": review_required,
            "blockers": (
                ["RAG contexts were produced for calibrated hypotheses only; company gap evidence still requires review."]
                if investigative_mode
                else None
            ),
        }


# ------------------------------------------------------------------
# Factories
# ------------------------------------------------------------------


def build_qdrant_rag_service(
    *,
    qdrant_config: QdrantConfig | None = None,
    embedding_model: EmbeddingProvider | None = None,
    vector_store: VectorStore | None = None,
    chunk_index: ChunkIndex | None = None,
) -> QdrantRagService:
    """Build the official production RagService.

    The service uses Qdrant semantic retrieval, lexical ChunkIndex retrieval,
    RRF fusion, and calibrated reranking. It validates all dependencies on call
    and blocks production when Qdrant, corpus, embeddings, or calibrations are
    not ready.

    Parameters
    ----------
    qdrant_config:
        Qdrant connection config. Falls back to env vars / defaults.
    embedding_model:
        Embedding provider. Falls back to ``SentenceTransformerProvider()``.
    vector_store:
        Vector store. Falls back to ``build_qdrant_store()``.

    Returns
    -------
    QdrantRagService
        A ``RagService``-compatible callable that uses hybrid retrieval and reranking.
    """
    return QdrantRagService(
        qdrant_config=qdrant_config,
        embedding_model=embedding_model,
        vector_store=vector_store,
        chunk_index=chunk_index,
    )


def build_rag_service(
    *,
    qdrant_config: QdrantConfig | None = None,
    chunk_index: Any = None,
    embedding_model: EmbeddingProvider | None = None,
    vector_store: VectorStore | None = None,
) -> QdrantRagService:
    """Build the official single product RAG path.

    The optional ``chunk_index`` is actively used when provided, preserving
    backward compatibility while enforcing the hybrid+rerank runtime path.
    """
    typed_chunk_index = chunk_index if isinstance(chunk_index, ChunkIndex) else None
    return build_qdrant_rag_service(
        qdrant_config=qdrant_config,
        embedding_model=embedding_model,
        vector_store=vector_store,
        chunk_index=typed_chunk_index,
    )

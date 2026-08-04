"""Retrieve NVIDIA context from RAG corpus driven by calibrated gaps.

Uses ``GapDiagnosisResultItem`` entries with ``production_allowed=True`` as
the primary input for deterministic query building, retrieval via the existing
``ChunkIndex``, and quantitative metrics reporting.

No LLM, no scraping, no recommendations — pure retrieval pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.diagnosis.nvidia_mapping import map_gap_to_technologies
from src.diagnosis.schemas import GAP_TECH_MAP, GapDiagnosisResultItem, GapDiagnosisSummary, GapType
from src.quality.decision_calibration_registry import (
    get_project_decision_inventory,
    validate_decision_for_production,
)
from src.rag.embeddings import EmbeddingProvider
from src.rag.hybrid_retrieval import hybrid_retrieve
from src.rag.retrieval import ChunkIndex, build_default_index
from src.rag.schemas import RetrievalQuery
from src.rag.vector_store import VectorStore

# ── Required RAG calibration decisions ──────────────────────────────────────

REQUIRED_RAG_DECISIONS: list[str] = [
    "rag.gap_query_top_k",
    "rag.min_contexts_per_gap",
    "rag.context_relevance_threshold",
    "rag.citation_precision_threshold",
    "rag.unsupported_claim_rate_threshold",
    "rag.hybrid_retrieval_weights",
    "rag.reranker_required",
]

EXISTING_RAG_DECISIONS: list[str] = [
    "rag.top_k",
    "rag.min_required_contexts",
]


def _validate_rag_calibrations() -> tuple[dict[str, Any], list[str]]:
    inventory = get_project_decision_inventory()
    all_decisions = REQUIRED_RAG_DECISIONS + EXISTING_RAG_DECISIONS
    values: dict[str, Any] = {}
    blockers: list[str] = []

    for decision_id in all_decisions:
        found = False
        for rec in inventory:
            if rec.decision_id == decision_id:
                found = True
                validation = validate_decision_for_production(rec)
                if not validation.passed:
                    blockers.append(f"RAG decision '{decision_id}' blocked: {'; '.join(validation.reasons)}")
                elif rec.calibration_status.value in ("uncalibrated", "blocked"):
                    blockers.append(
                        f"RAG decision '{decision_id}' is {rec.calibration_status} "
                        f"(production_allowed={rec.production_allowed})"
                    )
                else:
                    values[decision_id] = rec.current_value
                break
        if not found:
            blockers.append(f"RAG decision '{decision_id}' not found in registry")

    return values, blockers


# ── Deterministic query builder per gap ─────────────────────────────────────

_STOPWORDS: frozenset[str] = frozenset(
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
    raw = text.lower().split()
    return [w for w in raw if w not in _STOPWORDS and len(w) > 2]


def _extract_texts_from_items(items: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for item in items:
        text = item.get("text") or item.get("snippet") or item.get("claim") or ""
        if text:
            texts.append(str(text))
    return texts


def _build_gap_queries(
    gap_items: list[GapDiagnosisResultItem],
    startup_profile: dict[str, Any] | None,
    accepted_evidence_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    queries_by_gap: dict[str, dict[str, Any]] = {}

    for gap in gap_items:
        gap_type: GapType = gap.gap_type
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


def _build_retrieval_query(gap_type: GapType, nvidia_techs: list[str]) -> list[RetrievalQuery]:
    queries: list[RetrievalQuery] = [
        RetrievalQuery(gap_type=gap_type.value, technology=None),
    ]
    for tech in nvidia_techs[:3]:
        queries.append(RetrievalQuery(gap_type=gap_type.value, technology=tech))
    return queries


def _retrieve_for_gap(
    gap: GapDiagnosisResultItem,
    idx: ChunkIndex,
    gap_query_top_k: int,
    relevance_threshold: float,
    *,
    vector_store: VectorStore | None = None,
    embedding_model: EmbeddingProvider | None = None,
) -> tuple[list[dict[str, Any]], int]:
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
        if vector_store is not None and embedding_model is not None and vector_store.size > 0:
            results = hybrid_retrieve(
                rq,
                idx,
                embedding_model,
                vector_store,
                top_k=gap_query_top_k,
                gap_type=gap.gap_type.value,
            )
        else:
            results = idx.retrieve(rq, top_k=gap_query_top_k)
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
                    "gap_id": gap.gap_id,
                    "source_id": ctx.source_id,
                    "nvidia_technology": ctx.product,
                    "title": ctx.title,
                    "snippet": ctx.content,
                    "url": ctx.url or "",
                    "retrieval_score": ctx.relevance_score,
                    "rerank_score": None,
                    "relevance_score": ctx.relevance_score,
                    "citation_ready": citation_ready,
                    "retrieved_at": now_iso,
                    "calibration_decision_ids": list(gap.calibration_decision_ids),
                }
            )

    return contexts, len(seen_chunks)


# ── Main entry point ───────────────────────────────────────────────────────


def retrieve_nvidia_context(
    run_id: str,
    gap_diagnosis_summary: dict[str, Any] | None,
    startup_profile: dict[str, Any] | None,
    accepted_evidence_items: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    ai_native_score: float | None,
    nvidia_fit_score: float | None,
    *,
    vector_store: VectorStore | None = None,
    embedding_model: EmbeddingProvider | None = None,
    chunk_index: ChunkIndex | None = None,
) -> dict[str, Any]:
    rag_retrieval_status: str = "unknown"
    blockers: list[str] = []
    review_required: bool = False

    # ── 1. Validate gap diagnosis summary exists ──────────────────────────
    if not gap_diagnosis_summary:
        return {
            "rag_queries_by_gap": {},
            "rag_contexts": [],
            "rag_contexts_by_gap": {},
            "rag_retrieval_status": "blocked_no_calibrated_gaps",
            "rag_retrieval_metrics": _empty_metrics(),
            "status": "rag_blocked_no_calibrated_gaps",
            "blockers": ["gap_diagnosis_summary is None or empty"],
            "review_required": True,
        }

    # ── 2. Parse gap diagnosis summary ───────────────────────────────────
    try:
        summary = GapDiagnosisSummary(**gap_diagnosis_summary)
    except Exception as exc:
        return {
            "rag_queries_by_gap": {},
            "rag_contexts": [],
            "rag_contexts_by_gap": {},
            "rag_retrieval_status": "failed",
            "rag_retrieval_metrics": _empty_metrics(),
            "status": "rag_failed",
            "blockers": [f"Failed to parse gap_diagnosis_summary: {type(exc).__name__}"],
            "review_required": False,
        }

    gap_items: list[GapDiagnosisResultItem] = summary.gaps

    if not gap_items:
        return {
            "rag_queries_by_gap": {},
            "rag_contexts": [],
            "rag_contexts_by_gap": {},
            "rag_retrieval_status": "blocked_no_calibrated_gaps",
            "rag_retrieval_metrics": _empty_metrics(),
            "status": "rag_blocked_no_calibrated_gaps",
            "blockers": ["gap_diagnosis_summary has zero gap items"],
            "review_required": True,
        }

    # ── 3. Validate RAG calibration decisions ────────────────────────────
    cal_values, cal_blockers = _validate_rag_calibrations()
    missing_rag_calibration_count = len(cal_blockers)
    if cal_blockers:
        return {
            "rag_queries_by_gap": {},
            "rag_contexts": [],
            "rag_contexts_by_gap": {},
            "rag_retrieval_status": "blocked_uncalibrated_rag",
            "rag_retrieval_metrics": _empty_metrics(missing_rag_calibration_count),
            "status": "rag_blocked_uncalibrated",
            "blockers": cal_blockers,
            "review_required": True,
        }

    gap_query_top_k = int(cal_values.get("rag.gap_query_top_k", 3))
    min_contexts_per_gap = int(cal_values.get("rag.min_contexts_per_gap", 1))
    relevance_threshold = float(cal_values.get("rag.context_relevance_threshold", 0.3))

    # ── 4. Filter gaps by production_allowed=False → blocked ─────────────
    #    and production_allowed=True → calibrated
    calibrated_gaps: list[GapDiagnosisResultItem] = [g for g in gap_items if g.production_allowed]

    if not calibrated_gaps:
        return {
            "rag_queries_by_gap": {},
            "rag_contexts": [],
            "rag_contexts_by_gap": {},
            "rag_retrieval_status": "blocked_no_calibrated_gaps",
            "rag_retrieval_metrics": _empty_metrics(
                missing_rag_calibration_count=missing_rag_calibration_count,
                gap_count=len(gap_items),
                calibrated_gap_count=0,
            ),
            "status": "rag_blocked_no_calibrated_gaps",
            "blockers": ["No calibrated gaps with production_allowed=True"],
            "review_required": True,
        }

    # ── 5. Build RAG queries per gap (deterministic, no LLM) ────────────
    rag_queries_by_gap = _build_gap_queries(
        calibrated_gaps,
        startup_profile,
        accepted_evidence_items,
    )

    # ── 6. Build ChunkIndex and retrieve ─────────────────────────────────
    try:
        idx = chunk_index if chunk_index is not None else build_default_index()
    except Exception as exc:
        return {
            "rag_queries_by_gap": rag_queries_by_gap,
            "rag_contexts": [],
            "rag_contexts_by_gap": {},
            "rag_retrieval_status": "failed",
            "rag_retrieval_metrics": _empty_metrics(
                missing_rag_calibration_count=missing_rag_calibration_count,
                gap_count=len(gap_items),
                calibrated_gap_count=len(calibrated_gaps),
            ),
            "status": "rag_failed",
            "blockers": [f"Failed to build chunk index: {type(exc).__name__}"],
            "review_required": False,
        }

    idx_has_chunks = bool(idx.chunks)
    vs_has_entries = vector_store is not None and vector_store.size > 0

    if not idx_has_chunks and not vs_has_entries:
        return {
            "rag_queries_by_gap": rag_queries_by_gap,
            "rag_contexts": [],
            "rag_contexts_by_gap": {},
            "rag_retrieval_status": "failed",
            "rag_retrieval_metrics": _empty_metrics(
                missing_rag_calibration_count=missing_rag_calibration_count,
                gap_count=len(gap_items),
                calibrated_gap_count=len(calibrated_gaps),
            ),
            "status": "rag_failed",
            "blockers": ["RAG corpus is empty — no chunks or vector entries available"],
            "review_required": False,
        }

    all_contexts: list[dict[str, Any]] = []
    contexts_by_gap: dict[str, list[dict[str, Any]]] = {}
    query_count = len(rag_queries_by_gap)

    for gap in calibrated_gaps:
        gap_contexts, _ = _retrieve_for_gap(
            gap,
            idx,
            gap_query_top_k,
            relevance_threshold,
            vector_store=vector_store,
            embedding_model=embedding_model,
        )
        contexts_by_gap[gap.gap_id] = gap_contexts
        all_contexts.extend(gap_contexts)

    # ── 7. Compute metrics ──────────────────────────────────────────────
    gap_count = len(gap_items)
    calibrated_gap_count = len(calibrated_gaps)
    retrieved_context_count = len(all_contexts)
    context_count_by_gap: dict[str, int] = {gid: len(ctxs) for gid, ctxs in contexts_by_gap.items()}
    gaps_with_min_contexts = sum(1 for gid, ctxs in contexts_by_gap.items() if len(ctxs) >= min_contexts_per_gap)
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

    rag_blocker_count = len(blockers)

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
        "rag_blocker_count": rag_blocker_count,
    }

    # ── 8. Determine status ─────────────────────────────────────────────
    if retrieved_context_count == 0:
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

    # ── 9. Build rag_contexts as list[str] for backward compat ──────────
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
            "rag_required": True,
        },
        "status": top_status,
        "review_required": review_required,
        "blockers": blockers if blockers else None,
    }


def _empty_metrics(
    missing_rag_calibration_count: int = 0,
    gap_count: int = 0,
    calibrated_gap_count: int = 0,
) -> dict[str, Any]:
    return {
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
        "rag_blocker_count": 1 if missing_rag_calibration_count > 0 else 0,
    }

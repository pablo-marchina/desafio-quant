from datetime import datetime, timezone

from app.rag.reranker import rerank_candidates
from app.rag.retriever import retrieve_hybrid
from app.rag.schemas import (
    NvidiaRagQueryRequest,
    NvidiaRagQueryResponse,
    NvidiaRagResult,
)


def run_nvidia_rag(
    payload: NvidiaRagQueryRequest,
) -> NvidiaRagQueryResponse:
    candidate_limit = max(
        payload.top_k * 4,
        12,
    )

    candidates = retrieve_hybrid(
        query=payload.query,
        candidate_limit=candidate_limit,
    )

    reranked_candidates = rerank_candidates(
        query=payload.query,
        candidates=candidates,
        top_k=payload.top_k,
    )

    results = [
        NvidiaRagResult(
            technology_id=candidate.technology_id,
            technology_name=candidate.technology_name,
            title=candidate.title,
            text=candidate.text,
            source_url=candidate.source_url,
            tags=candidate.tags,
            lexical_score=candidate.lexical_score,
            semantic_score=candidate.semantic_score,
            fused_score=candidate.fused_score,
            rerank_score=candidate.rerank_score or 0.0,
        )
        for candidate in reranked_candidates
    ]

    return NvidiaRagQueryResponse(
        query=payload.query,
        pipeline=(
            "BM25 + embeddings Qdrant + "
            "Reciprocal Rank Fusion + CrossEncoder reranker + "
            "metadata alignment"
        ),
        retrieved_at=datetime.now(timezone.utc),
        results=results,
    )
from src.models import RagCitationItem, RagResult

from .config import RERANK_TOPK
from .embeddings import EmbeddingClient
from .reranking import rerank_with_openrouter
from .retriever import retrieve
from .store import init_chroma


def _safe_float(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_summary(items: list[RagCitationItem]) -> str:
    if not items:
        return ""

    highlights: list[str] = []
    for item in items[:3]:
        snippet = " ".join((item.snippet or "").split())
        if snippet:
            highlights.append(f"{item.citation} {snippet[:220]}")
    return " ".join(highlights)


def answer_query(query: str, collection: str = "nvidia_kb") -> RagResult:
    """
    Fluxo simples de resposta:
    - gera embedding da query
    - recupera top-K do Chroma
    - rerankeia usando OpenRouter
    - retorna estrutura estavel com citacoes e metadados
    """
    emb = EmbeddingClient()
    q_emb = emb.embed([query])[0]
    client = init_chroma()
    res = retrieve(client, collection, q_emb)
    passages = []
    docs = res.get("documents", [[]])[0]
    metadatas = res.get("metadatas", [[]])[0]
    ids = res.get("ids", [[]])[0]
    distances = res.get("distances", [[]])[0]

    for index, (doc, metadata, document_id) in enumerate(zip(docs, metadatas, ids), start=1):
        retrieval_distance = distances[index - 1] if index - 1 < len(distances) else None
        retrieval_score = None
        if retrieval_distance is not None:
            score = _safe_float(retrieval_distance)
            if score is not None:
                retrieval_score = max(0.0, 1.0 - score)
        passages.append(
            {
                "id": document_id,
                "text": doc,
                "meta": metadata or {},
                "retrieval_score": retrieval_score,
                "retrieval_rank": index,
            }
        )

    scored = rerank_with_openrouter(query, passages, top_k=RERANK_TOPK)
    items: list[RagCitationItem] = []
    rerank_statuses = [item.get("rerank_status") for item in scored]
    rerank_providers = [item.get("rerank_provider") for item in scored]
    rerank_reasons = [item.get("rerank_reason") for item in scored if item.get("rerank_reason")]

    for index, passage in enumerate(scored, start=1):
        metadata = dict(passage.get("meta") or {})
        metadata["rerank_status"] = passage.get("rerank_status")
        metadata["rerank_provider"] = passage.get("rerank_provider")
        metadata["rerank_reason"] = passage.get("rerank_reason")
        items.append(
            RagCitationItem(
                citation=f"[{index}]",
                snippet=passage.get("text") or "",
                source_title=metadata.get("title")
                or metadata.get("source_title")
                or metadata.get("document_title"),
                source_url=metadata.get("url") or metadata.get("source_url"),
                source_metadata=metadata,
                retrieval_score=_safe_float(passage.get("retrieval_score")),
                rerank_score=_safe_float(passage.get("score")),
                document_id=passage.get("id"),
            )
        )

    return RagResult(
        query=query,
        summary=_build_summary(items),
        items=items,
        metadata={
            "retrieved_count": len(passages),
            "returned_count": len(items),
            "rerank_provider": rerank_providers[0] if rerank_providers else None,
            "rerank_status": (
                "ok" if any(status == "ok" for status in rerank_statuses)
                else rerank_statuses[0] if rerank_statuses else None
            ),
            "rerank_reasons": rerank_reasons,
        },
    )

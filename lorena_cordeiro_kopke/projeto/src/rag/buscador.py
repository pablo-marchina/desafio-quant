from __future__ import annotations

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from rag.client import get_client
from rag.embedding import gerar_embedding
from rag.setup_qdrant import COLLECTION_NAME


def _montar_filtro(filtros: dict) -> Filter | None:
    if not filtros:
        return None

    condicoes = []
    for campo, valor in filtros.items():
        if isinstance(valor, dict) and "$in" in valor:
            condicoes.append(FieldCondition(key=campo, match=MatchAny(any=valor["$in"])))
        else:
            condicoes.append(FieldCondition(key=campo, match=MatchValue(value=valor)))

    return Filter(must=condicoes)


_CATEGORIAS_PADRAO = ["produto", "caso_de_uso", "stack", "inception"]
_SCORE_THRESHOLD = 0.55
# Com reranking ativo, o cross-encoder é o árbitro semântico real.
# Um threshold alto aqui descartaria chunks relevantes antes de chegarem ao reranker.
_SCORE_THRESHOLD_RERANKING = 0.3


def buscar(
    query: str,
    filtros: dict | None = None,
    top_k: int = 10,
    reranking: bool = False,
    fator_candidatos: int = 3,
) -> list[dict]:
    client = get_client()
    embedding = gerar_embedding(query)

    filtros_efetivos = dict(filtros) if filtros else {}
    filtros_efetivos.setdefault("categoria", {"$in": _CATEGORIAS_PADRAO})

    limite = top_k * fator_candidatos if reranking else top_k
    threshold = _SCORE_THRESHOLD_RERANKING if reranking else _SCORE_THRESHOLD

    resultados = client.query_points(
        collection_name=COLLECTION_NAME,
        query=embedding,
        query_filter=_montar_filtro(filtros_efetivos),
        limit=limite,
        score_threshold=threshold,
        with_payload=True,
    ).points

    candidatos = [
        {"score": r.score, "texto": r.payload.get("texto", ""), **r.payload}
        for r in resultados
    ]

    if reranking:
        from rag.reranker import reranquear
        candidatos = reranquear(query, candidatos, top_k)

    return candidatos

"""Reranker local (fastembed cross-encoder) — reordena os trechos recuperados.

A busca vetorial traz candidatos por similaridade de cosseno, que às vezes deixa
passar um "quase" na frente do certo (ex.: Morpheus/cibersegurança para uma
startup de IoT). O reranker é um cross-encoder: lê o par (consulta, trecho) JUNTO
e dá uma nota de relevância mais precisa do que a distância entre vetores.

Modelo multilíngue local (a consulta vem em PT, os docs NVIDIA em EN), sem chave
nem custo — mesma filosofia dos embeddings locais. Trocar por Cohere no futuro é
só mexer aqui dentro; o resto do fluxo não muda.

STATUS: fora do fluxo por ora. Com a query por perfil técnico, a busca vetorial
pura (cosseno) ficou mais precisa e sem o custo do modelo de ~1 GB. Mantido como
opção para reavaliar depois de melhorar as fontes das tecnologias específicas.
"""

from __future__ import annotations

from functools import lru_cache

from fastembed.rerank.cross_encoder import TextCrossEncoder

# Único modelo de rerank multilíngue do fastembed (~1,1 GB, baixa só na 1ª vez).
MODEL_NAME = "jinaai/jina-reranker-v2-base-multilingual"


@lru_cache(maxsize=1)
def _get_model() -> TextCrossEncoder:
    """Carrega o modelo uma única vez e reaproveita (download só na 1ª chamada)."""
    return TextCrossEncoder(model_name=MODEL_NAME)


def rerank(query: str, chunks: list[dict], top_n: int = 5) -> list[dict]:
    """Reordena os chunks por relevância à consulta e devolve os top_n.

    Cada chunk é um dict {score, technology, source_url, text} vindo da busca.
    O 'score' passa a ser a nota do reranker; o cosseno original fica guardado
    em 'vector_score' (transparência). Preserva as demais chaves.
    """
    if not chunks:
        return []

    docs = [c.get("text") or "" for c in chunks]
    scores = list(_get_model().rerank(query, docs))  # uma nota por doc

    ordenados = sorted(zip(chunks, scores), key=lambda par: par[1], reverse=True)

    resultado: list[dict] = []
    for chunk, score in ordenados[:top_n]:
        item = dict(chunk)
        item["vector_score"] = chunk.get("score")  # mantém o cosseno original
        item["score"] = float(score)               # 'score' = nota do reranker
        resultado.append(item)
    return resultado

"""Geração de embeddings com fastembed (modelo local, sem API e sem custo).

Transforma texto em vetores (listas de números que capturam significado).
O MESMO modelo é usado para indexar os documentos e para as consultas — tem
que ser o mesmo dos dois lados, senão a busca por significado não bate.
"""

from __future__ import annotations

from functools import lru_cache

from fastembed import TextEmbedding

# Modelo multilíngue pequeno: entende português e inglês, baixa ~0,22 GB e
# roda em CPU local Gera vetores de 384 dimensões.
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _get_model() -> TextEmbedding:
    """Carrega o modelo uma única vez e reaproveita nas próximas chamadas.

    O download acontece só na primeira vez; depois fica em cache local.
    O @lru_cache garante que não recarregamos o modelo a cada chamada (custoso).
    """
    return TextEmbedding(model_name=MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Gera um vetor para cada texto da lista (usado na ingestão dos documentos).

    O fastembed devolve um gerador de arrays numpy; convertemos cada um para
    uma lista de floats simples (formato que o Qdrant aceita direto).
    """
    model = _get_model()
    return [vector.tolist() for vector in model.embed(texts)]


def embed_query(text: str) -> list[float]:
    """Gera o vetor de uma única pergunta (usado na hora da busca)."""
    return embed_texts([text])[0]

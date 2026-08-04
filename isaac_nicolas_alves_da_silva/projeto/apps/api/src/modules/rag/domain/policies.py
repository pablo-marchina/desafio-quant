"""Politica de fusao de rankings (RAG V3 - busca hibrida).

Busca vetorial (Qdrant, score cosine 0-1) e busca lexical (Postgres
ts_rank, escala arbitraria) nao sao comparaveis diretamente por valor.
Reciprocal Rank Fusion (RRF) usa so a posicao de cada item em cada
ranking, nao o score bruto - por isso nao precisa de normalizacao
ad-hoc entre escalas incompativeis.
"""

from dataclasses import dataclass
from uuid import UUID

DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class RankedChunk:
    """Um chunk em uma posicao de algum ranking (vetorial ou lexical)."""

    chunk_id: UUID
    document_id: UUID


@dataclass(frozen=True)
class FusedChunk:
    """Um chunk apos a fusao, com o score RRF (nao mais o score original)."""

    chunk_id: UUID
    document_id: UUID
    score: float


def fuse_rankings(
    *,
    ranked_lists: list[list[RankedChunk]],
    limit: int,
    k: int = DEFAULT_RRF_K,
) -> list[FusedChunk]:
    """Funde N rankings via Reciprocal Rank Fusion.

    Cada item recebe ``1 / (k + posicao)`` por ranking em que aparece
    (posicao comeca em 1). Itens presentes em mais de um ranking acumulam
    pontuacao - e exatamente o sinal que torna a fusao hibrida util. O
    score retornado e o score RRF (substitui o cosine/ts_rank original,
    que nao sao comparaveis entre si).
    """

    scores: dict[UUID, float] = {}
    representative: dict[UUID, RankedChunk] = {}

    for ranked_list in ranked_lists:
        for position, item in enumerate(ranked_list, start=1):
            scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + 1.0 / (
                k + position
            )
            representative.setdefault(item.chunk_id, item)

    ordered_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return [
        FusedChunk(
            chunk_id=representative[chunk_id].chunk_id,
            document_id=representative[chunk_id].document_id,
            score=scores[chunk_id],
        )
        for chunk_id in ordered_ids[:limit]
    ]

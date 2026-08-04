"""Hybrid fusion strategies — RRF and weighted score fusion.

All functions are pure, testable, and operate on lists of
RagEvidenceChunk.
"""

from __future__ import annotations

from src.rag.schemas import RagEvidenceChunk

_RRF_K = 60


def reciprocal_rank_fusion(
    dense: list[RagEvidenceChunk],
    sparse: list[RagEvidenceChunk],
    top_k: int = 5,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
) -> list[RagEvidenceChunk]:
    """Fuse dense and sparse results using Reciprocal Rank Fusion.

    Each list is ranked by position.  RRF scores are computed per chunk_id,
    then weighted by ``dense_weight`` and ``sparse_weight``.

    Parameters
    ----------
    dense:
        Results from dense retrieval (ranked by score_dense desc).
    sparse:
        Results from sparse retrieval (ranked by score_sparse desc).
    top_k:
        Maximum chunks in the fused result.
    dense_weight:
        Weight multiplier for dense RRF contributions.
    sparse_weight:
        Weight multiplier for sparse RRF contributions.

    Returns
    -------
    list[RagEvidenceChunk]
        Fused results sorted by score_fused desc, with score_fused populated.
    """
    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, RagEvidenceChunk] = {}

    for rank, chunk in enumerate(dense):
        cid = chunk.chunk_id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + dense_weight / (_RRF_K + rank)
        if cid not in chunk_map:
            chunk_map[cid] = chunk

    for rank, chunk in enumerate(sparse):
        cid = chunk.chunk_id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + sparse_weight / (_RRF_K + rank)
        if cid not in chunk_map:
            chunk_map[cid] = chunk

    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)
    fused = [chunk_map[cid] for cid in sorted_ids[:top_k]]

    max_score = max(rrf_scores.values()) if rrf_scores else 1.0
    for chunk in fused:
        chunk.score_fused = round(rrf_scores.get(chunk.chunk_id, 0.0) / max_score, 4)

    return fused


def weighted_score_fusion(
    dense: list[RagEvidenceChunk],
    sparse: list[RagEvidenceChunk],
    top_k: int = 5,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
) -> list[RagEvidenceChunk]:
    """Fuse dense and sparse results using weighted score combination.

    Simple linear combination::

        score_fused = dense_weight * score_dense + sparse_weight * score_sparse

    Parameters
    ----------
    dense:
        Results from dense retrieval.
    sparse:
        Results from sparse retrieval.
    top_k:
        Maximum chunks in the fused result.
    dense_weight:
        Weight for score_dense.
    sparse_weight:
        Weight for score_sparse.

    Returns
    -------
    list[RagEvidenceChunk]
        Fused results sorted by score_fused desc.
    """
    chunk_map: dict[str, RagEvidenceChunk] = {}

    for chunk in dense:
        cid = chunk.chunk_id
        if cid not in chunk_map:
            chunk_map[cid] = chunk
            chunk.score_fused = 0.0
        chunk_map[cid].score_fused += dense_weight * chunk.score_dense
        chunk_map[cid].score_dense = max(chunk_map[cid].score_dense, chunk.score_dense)

    for chunk in sparse:
        cid = chunk.chunk_id
        if cid not in chunk_map:
            chunk_map[cid] = chunk
            chunk.score_fused = 0.0
        chunk_map[cid].score_fused += sparse_weight * chunk.score_sparse
        chunk_map[cid].score_sparse = max(chunk_map[cid].score_sparse, chunk.score_sparse)

    fused = sorted(chunk_map.values(), key=lambda c: c.score_fused, reverse=True)[:top_k]

    max_score = max((c.score_fused for c in fused), default=1.0)
    for chunk in fused:
        if max_score > 0:
            chunk.score_fused = round(chunk.score_fused / max_score, 4)

    return fused


def deduplicate_chunks(chunks: list[RagEvidenceChunk]) -> list[RagEvidenceChunk]:
    """Remove chunks with duplicate chunk_id, keeping the first occurrence."""
    seen: set[str] = set()
    result: list[RagEvidenceChunk] = []
    for c in chunks:
        if c.chunk_id not in seen:
            seen.add(c.chunk_id)
            result.append(c)
    return result

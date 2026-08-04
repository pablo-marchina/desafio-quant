"""Testes da fusao de rankings via RRF (domain/policies.py)."""

from uuid import uuid4

from apps.api.src.modules.rag.domain.policies import RankedChunk, fuse_rankings


def _chunk() -> RankedChunk:
    return RankedChunk(chunk_id=uuid4(), document_id=uuid4())


def test_fuse_rankings_unions_disjoint_lists() -> None:
    a, b = _chunk(), _chunk()

    fused = fuse_rankings(ranked_lists=[[a], [b]], limit=10)

    assert {item.chunk_id for item in fused} == {a.chunk_id, b.chunk_id}


def test_fuse_rankings_ranks_item_in_both_lists_first() -> None:
    in_both = _chunk()
    only_first = RankedChunk(chunk_id=uuid4(), document_id=in_both.document_id)
    only_second = RankedChunk(chunk_id=uuid4(), document_id=in_both.document_id)

    fused = fuse_rankings(
        ranked_lists=[
            [only_first, in_both],
            [in_both, only_second],
        ],
        limit=10,
    )

    assert fused[0].chunk_id == in_both.chunk_id


def test_fuse_rankings_respects_limit() -> None:
    chunks = [_chunk() for _ in range(5)]

    fused = fuse_rankings(ranked_lists=[chunks], limit=2)

    assert len(fused) == 2


def test_fuse_rankings_higher_position_scores_higher() -> None:
    first, second, third = _chunk(), _chunk(), _chunk()

    fused = fuse_rankings(ranked_lists=[[first, second, third]], limit=10)

    assert [item.chunk_id for item in fused] == [
        first.chunk_id,
        second.chunk_id,
        third.chunk_id,
    ]
    assert fused[0].score > fused[1].score > fused[2].score


def test_fuse_rankings_empty_lists_return_empty() -> None:
    fused = fuse_rankings(ranked_lists=[[], []], limit=10)

    assert fused == []

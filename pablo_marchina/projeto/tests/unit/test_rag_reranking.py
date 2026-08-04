"""Tests for src.rag.reranking — deterministic reranking."""

from src.rag.reranking import rerank_contexts
from src.rag.schemas import RerankingConfig, RetrievalQuery, RetrievedContext


def _make_ctx(
    chunk_id: str,
    source_id: str = "src1",
    product: str = "NVIDIA NIM",
    gap_types: list[str] | None = None,
    url: str = "https://docs.nvidia.com/test",
    content: str = "Some content",
    score: float = 0.5,
) -> RetrievedContext:
    return RetrievedContext(
        chunk_id=chunk_id,
        source_id=source_id,
        title="Test",
        content=content,
        product=product,
        gap_types=gap_types or ["high_inference_cost"],
        url=url,
        relevance_score=score,
    )


def test_rerank_promotes_gap_match() -> None:
    ctx_match = _make_ctx("a", gap_types=["high_inference_cost"], score=0.3)
    ctx_no_match = _make_ctx("b", gap_types=["voice_need"], score=0.5)
    query = RetrievalQuery(gap_type="high_inference_cost")
    result = rerank_contexts([ctx_no_match, ctx_match], query)
    assert result[0].chunk_id == "a"


def test_rerank_promotes_technology_match() -> None:
    ctx_match = _make_ctx("a", product="NVIDIA NIM", content="NIM features", score=0.3)
    ctx_no_match = _make_ctx("b", product="TensorRT-LLM", content="LLM stuff", score=0.5)
    query = RetrievalQuery(technology="NVIDIA NIM")
    result = rerank_contexts([ctx_no_match, ctx_match], query)
    assert result[0].chunk_id == "a"


def test_rerank_penalizes_no_provenance() -> None:
    ctx_good = _make_ctx("a", source_id="src1", url="https://docs.nvidia.com/test", score=0.4)
    ctx_bad = _make_ctx("b", source_id="", url="", score=0.6)
    query = RetrievalQuery(gap_type="high_inference_cost")
    result = rerank_contexts([ctx_bad, ctx_good], query)
    assert result[0].chunk_id == "a"


def test_rerank_penalizes_duplicate() -> None:
    ctx1 = _make_ctx("a", score=0.5)
    ctx2 = _make_ctx("a", score=0.5)
    query = RetrievalQuery(gap_type="high_inference_cost")
    result = rerank_contexts([ctx1, ctx2], query)
    assert result[0].chunk_id == "a"
    # Second occurrence should have lower score
    assert result[0].relevance_score >= result[1].relevance_score


def test_rerank_empty_list() -> None:
    query = RetrievalQuery(gap_type="high_inference_cost")
    result = rerank_contexts([], query)
    assert result == []


def test_rerank_preserves_order_for_equal_scores() -> None:
    ctx_a = _make_ctx("a", score=0.5)
    ctx_b = _make_ctx("b", score=0.5)
    query = RetrievalQuery()
    result = rerank_contexts([ctx_a, ctx_b], query)
    assert [r.chunk_id for r in result] == ["a", "b"]


def test_rerank_uses_custom_config() -> None:
    cfg = RerankingConfig(boost_gap_match=0.0, penalty_irrelevant=0.0)
    ctx_match = _make_ctx("a", gap_types=["high_inference_cost"], score=0.3)
    ctx_no_match = _make_ctx("b", gap_types=["voice_need"], score=0.5)
    query = RetrievalQuery(gap_type="high_inference_cost")
    result = rerank_contexts([ctx_match, ctx_no_match], query, config=cfg)
    # With gap boost=0 and irrelevant penalty=0, original score decides
    assert result[0].chunk_id == "b"


def test_rerank_score_in_0_1_range() -> None:
    ctx = _make_ctx("a", score=0.5)
    query = RetrievalQuery(gap_type="high_inference_cost")
    result = rerank_contexts([ctx], query)
    assert 0.0 <= result[0].relevance_score <= 1.0


def test_rerank_penalizes_irrelevant() -> None:
    ctx_irrelevant = _make_ctx("a", gap_types=["voice_need"], score=0.9)
    ctx_relevant = _make_ctx("b", gap_types=["high_inference_cost"], score=0.3)
    query = RetrievalQuery(gap_type="high_inference_cost")
    result = rerank_contexts([ctx_irrelevant, ctx_relevant], query)
    # With penalty_irrelevant = -0.2 and boost_gap_match = +0.3,
    # the relevant one should come first
    assert result[0].chunk_id == "b"

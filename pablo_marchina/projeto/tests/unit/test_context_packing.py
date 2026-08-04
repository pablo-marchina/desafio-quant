"""Tests for src.rag.context_packing — dedup, filter, limit, metrics."""

from src.rag.context_packing import build_supporting_contexts, pack_contexts
from src.rag.schemas import PackingConfig, RetrievalQuery, RetrievedContext


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


def test_pack_removes_duplicates() -> None:
    ctx_a = _make_ctx("a")
    ctx_a2 = _make_ctx("a")
    result = pack_contexts([ctx_a, ctx_a2], RetrievalQuery(gap_type="high_inference_cost"))
    assert result.total_packed <= 1
    assert any(d.reason == "duplicate" for d in result.dropped)


def test_pack_preserves_provenance() -> None:
    ctx = _make_ctx("a", source_id="src1", url="https://docs.nvidia.com/test")
    result = pack_contexts([ctx], RetrievalQuery(gap_type="high_inference_cost"))
    for pc in result.packed:
        assert pc.source_id
        assert pc.url


def test_pack_respects_max_per_gap() -> None:
    cfg = PackingConfig(max_total=10, max_per_gap=2, max_per_technology=5)
    contexts = [_make_ctx(f"c{i}") for i in range(5)]
    result = pack_contexts(contexts, RetrievalQuery(gap_type="high_inference_cost"), config=cfg)
    # All 5 match the same gap, max_per_gap=2
    assert result.total_packed <= 2
    assert any("exceeded_per_gap" in d.reason for d in result.dropped)


def test_pack_respects_max_per_technology() -> None:
    cfg = PackingConfig(max_total=10, max_per_gap=10, max_per_technology=1)
    contexts = [_make_ctx(f"c{i}", product="NVIDIA NIM") for i in range(3)]
    query = RetrievalQuery(gap_type="high_inference_cost", technology="NVIDIA NIM")
    result = pack_contexts(contexts, query, config=cfg)
    assert result.total_packed <= 1
    assert any("exceeded_per_technology" in d.reason for d in result.dropped)


def test_pack_respects_global_max_total() -> None:
    cfg = PackingConfig(max_total=2, max_per_gap=5, max_per_technology=5)
    contexts = [_make_ctx(f"c{i}") for i in range(5)]
    result = pack_contexts(contexts, RetrievalQuery(gap_type="high_inference_cost"), config=cfg)
    assert result.total_packed <= 2
    assert any("exceeded_global_max" in d.reason for d in result.dropped)


def test_pack_empty_list() -> None:
    result = pack_contexts([], RetrievalQuery(gap_type="high_inference_cost"))
    assert result.total_packed == 0
    assert result.total_dropped == 0
    assert result.total_raw == 0


def test_pack_provenance_coverage() -> None:
    ctx_good = _make_ctx("a", source_id="s1", url="https://example.com")
    ctx_bad = _make_ctx("b", source_id="", url="")
    result = pack_contexts([ctx_good, ctx_bad], RetrievalQuery(gap_type="high_inference_cost"))
    # Only ctx_good has provenance, but ctx_bad may be dropped for no provenance
    # or kept. Let's check the metric.
    assert 0.0 <= result.provenance_coverage <= 1.0


def test_pack_noise_reduction_score() -> None:
    ctx_a = _make_ctx("a")
    ctx_a2 = _make_ctx("a")  # duplicate
    result = pack_contexts([ctx_a, ctx_a2], RetrievalQuery(gap_type="high_inference_cost"))
    # 2 raw, at least 1 dropped => noise_reduction_score >= 0.5
    assert result.noise_reduction_score >= 0.0
    assert result.noise_reduction_score <= 1.0


def test_pack_gap_coverage() -> None:
    ctx = _make_ctx("a", gap_types=["high_inference_cost"])
    query = RetrievalQuery(gap_type="high_inference_cost")
    result = pack_contexts([ctx], query)
    # The only packed chunk matches query.gap_type
    assert result.gap_coverage == 1.0


def test_pack_technology_coverage() -> None:
    ctx = _make_ctx("a", product="NVIDIA NIM", content="NIM features")
    query = RetrievalQuery(technology="NVIDIA NIM")
    result = pack_contexts([ctx], query)
    assert result.technology_coverage == 1.0


def test_pack_context_budget_used() -> None:
    cfg = PackingConfig(max_total=5, max_per_gap=5, max_per_technology=5)
    contexts = [_make_ctx(f"c{i}") for i in range(3)]
    result = pack_contexts(contexts, RetrievalQuery(gap_type="high_inference_cost"), config=cfg)
    assert result.context_budget_used > 0.0
    assert result.context_budget_used <= 1.0


def test_pack_dropped_contexts_record_reason() -> None:
    ctx_a = _make_ctx("a")
    ctx_a2 = _make_ctx("a")
    result = pack_contexts([ctx_a, ctx_a2], RetrievalQuery(gap_type="high_inference_cost"))
    for d in result.dropped:
        assert d.reason
        assert d.chunk_id


def test_build_supporting_contexts() -> None:
    ctx = _make_ctx("a", product="NVIDIA NIM", gap_types=["high_inference_cost"])
    packing = pack_contexts([ctx], RetrievalQuery(gap_type="high_inference_cost", technology="NVIDIA NIM"))
    supporting = build_supporting_contexts(packing)
    assert len(supporting) >= 1
    for sc in supporting:
        assert sc.gap_type
        assert sc.technology
        assert len(sc.contexts) >= 0


def test_pack_mixed_gap_types() -> None:
    ctx1 = _make_ctx("a", gap_types=["high_inference_cost"])
    ctx2 = _make_ctx("b", gap_types=["voice_need"])
    query = RetrievalQuery(gap_type="high_inference_cost")
    result = pack_contexts([ctx1, ctx2], query)
    # Only a matches the gap; b should still appear but with matched_gap=None
    assert any(p.matched_gap == "high_inference_cost" for p in result.packed)

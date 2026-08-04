from __future__ import annotations

from datetime import UTC, datetime

from scripts import run_source_quality_product_spike
from src.rag.schemas import RetrievedContext
from src.rag.source_quality import rank_contexts_by_source_quality, score_source_quality


def _contexts() -> list[RetrievedContext]:
    return [
        RetrievedContext(
            chunk_id="stale_blog",
            source_id="blog",
            title="Blog",
            content="High keyword overlap.",
            product="Triton Inference Server",
            gap_types=["high_latency"],
            url="https://example.com/triton",
            relevance_score=0.95,
            valid_until="2025-01-01T00:00:00+00:00",
        ),
        RetrievedContext(
            chunk_id="official_docs",
            source_id="triton_docs",
            title="Triton Docs",
            content="Official NVIDIA Triton guidance.",
            product="Triton Inference Server",
            gap_types=["high_latency"],
            url="https://docs.nvidia.com/triton/",
            relevance_score=0.76,
            valid_until="2027-01-01T00:00:00+00:00",
        ),
    ]


def test_source_quality_ranks_official_fresh_context_above_stale_high_relevance() -> None:
    ranked = rank_contexts_by_source_quality(
        _contexts(),
        now=datetime(2026, 6, 22, tzinfo=UTC),
    )

    assert ranked[0].context.chunk_id == "official_docs"
    assert ranked[0].features.trust_score == 1.0
    assert "official_nvidia_source" in ranked[0].features.reasons
    assert "expired_source" in ranked[1].features.reasons


def test_source_quality_scores_missing_provenance_lower() -> None:
    context = RetrievedContext(
        chunk_id="missing_url",
        source_id="",
        title="No provenance",
        content="NVIDIA NIM guidance.",
        product="NVIDIA NIM",
        gap_types=["external_api_dependency"],
        relevance_score=0.99,
    )

    score = score_source_quality(context, now=datetime(2026, 6, 22, tzinfo=UTC))

    assert score.provenance_score == 0.20
    assert score.trust_score == 0.25
    assert score.combined_score < 0.60


def test_source_quality_product_spike_report_promotes_product_spike() -> None:
    report = run_source_quality_product_spike.build_report(min_delta=0.10)

    assert report["decision"] == "PROMOTE_TO_PRODUCT_SPIKE"
    assert report["quality_delta"] >= 0.10
    assert report["regression_count"] == 0
    assert report["case_count"] == 2

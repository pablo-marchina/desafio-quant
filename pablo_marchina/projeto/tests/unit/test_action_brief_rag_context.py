"""Tests that Action Brief correctly consumes (or ignores) packed RAG context."""

from src.briefing import build_action_brief
from src.briefing.schemas import StartupActionBrief
from src.rag.context_packing import pack_contexts
from src.rag.schemas import PackingResult, RetrievalQuery, RetrievedContext


def _make_brief_with_packing() -> StartupActionBrief:
    """Create a synthetic StartupActionBrief with packed context."""
    from datetime import UTC, datetime

    from pydantic import HttpUrl

    from src.extraction.schemas import (
        ConfidenceLevel,
        Evidence,
        SourceType,
        StartupProfile,
    )
    from src.pipeline.run_pipeline import run_full_pipeline

    profile = StartupProfile(
        startup_name="RAG Brief Test",
        website=HttpUrl("https://example.com"),
        sector="AI",
        description="An AI company with inference needs.",
        product_summary="AI inference product.",
        ai_signals=["AI signal: inference", "AI signal: cost optimization"],
        sources=[],
        confidence_score=0.7,
    )
    ev = Evidence(
        claim="AI inference company",
        source_url=HttpUrl("https://example.com"),
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence="We provide AI inference solutions.",
        confidence=ConfidenceLevel.MEDIUM,
        collected_at=datetime.now(UTC),
    )
    result = run_full_pipeline("RAG Brief Test", profile=profile, evidence_list=[ev])

    # Build synthetic packed context
    ctx = RetrievedContext(
        chunk_id="nim_000",
        source_id="nim",
        title="NVIDIA NIM",
        content="NVIDIA NIM optimizes inference cost and latency for AI models.",
        product="NVIDIA NIM",
        gap_types=["high_inference_cost"],
        url="https://docs.nvidia.com/nim",
        relevance_score=0.85,
    )
    query = RetrievalQuery(gap_type="high_inference_cost", technology="TensorRT-LLM")
    packing = pack_contexts([ctx], query)

    return build_action_brief(result, packing_result=packing)


def test_brief_with_packed_context_has_context_fields() -> None:
    brief = _make_brief_with_packing()
    assert hasattr(brief, "packed_rag_contexts")
    assert hasattr(brief, "supporting_nvidia_context")
    assert hasattr(brief, "dropped_contexts_debug")


def test_brief_has_supporting_nvidia_context_section() -> None:
    brief = _make_brief_with_packing()
    section_titles = [s.title for s in brief.sections]
    assert "Supporting NVIDIA Context" in section_titles


def test_brief_works_without_rag_context() -> None:
    from datetime import UTC, datetime

    from pydantic import HttpUrl

    from src.extraction.schemas import (
        ConfidenceLevel,
        Evidence,
        SourceType,
        StartupProfile,
    )
    from src.pipeline.run_pipeline import run_full_pipeline

    profile = StartupProfile(
        startup_name="No RAG Co",
        website=HttpUrl("https://example.com"),
        sector="AI",
        description="Simple AI company.",
        product_summary="Simple product.",
        ai_signals=["AI signal"],
        sources=[],
        confidence_score=0.5,
    )
    ev = Evidence(
        claim="AI company",
        source_url=HttpUrl("https://example.com"),
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence="AI company.",
        confidence=ConfidenceLevel.LOW,
        collected_at=datetime.now(UTC),
    )
    result = run_full_pipeline("No RAG Co", profile=profile, evidence_list=[ev])
    brief = build_action_brief(result)
    assert brief.startup_name == "No RAG Co"
    assert len(brief.sections) >= 3


def test_brief_packed_context_is_empty_by_default() -> None:
    from datetime import UTC, datetime

    from pydantic import HttpUrl

    from src.extraction.schemas import (
        ConfidenceLevel,
        Evidence,
        SourceType,
        StartupProfile,
    )
    from src.pipeline.run_pipeline import run_full_pipeline

    profile = StartupProfile(
        startup_name="Default Co",
        website=HttpUrl("https://example.com"),
        sector="AI",
        description="Default.",
        product_summary="Default.",
        ai_signals=[],
        sources=[],
        confidence_score=0.5,
    )
    ev = Evidence(
        claim="Default",
        source_url=HttpUrl("https://example.com"),
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence="Default.",
        confidence=ConfidenceLevel.LOW,
        collected_at=datetime.now(UTC),
    )
    result = run_full_pipeline("Default Co", profile=profile, evidence_list=[ev])
    brief = build_action_brief(result)
    assert brief.packed_rag_contexts == []
    assert brief.supporting_nvidia_context == []
    assert brief.dropped_contexts_debug == []


def test_brief_recommended_motion_not_altered_by_packing() -> None:
    """recommended_motion should not change with or without RAG packing."""
    from datetime import UTC, datetime

    from pydantic import HttpUrl

    from src.extraction.schemas import (
        ConfidenceLevel,
        Evidence,
        SourceType,
        StartupProfile,
    )
    from src.pipeline.run_pipeline import run_full_pipeline

    profile = StartupProfile(
        startup_name="Motion Test",
        website=HttpUrl("https://example.com"),
        sector="AI",
        description="Stable company.",
        product_summary="Stable product.",
        ai_signals=["AI signal"],
        sources=[],
        confidence_score=0.7,
    )
    ev = Evidence(
        claim="Stable AI",
        source_url=HttpUrl("https://example.com"),
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence="Stable AI product.",
        confidence=ConfidenceLevel.MEDIUM,
        collected_at=datetime.now(UTC),
    )
    result = run_full_pipeline("Motion Test", profile=profile, evidence_list=[ev])

    brief_no_rag = build_action_brief(result)
    brief_with_rag = build_action_brief(result, packing_result=PackingResult())

    assert brief_no_rag.recommended_motion == brief_with_rag.recommended_motion

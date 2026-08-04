"""Tests for pipeline integration of RAG reranking + context packing.

Epic 14.1 â€” verifies that run_full_pipeline() orchestrates hybrid retrieval,
deterministic reranking, context packing, and propagates results to the
Startup Action Brief.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import HttpUrl

from src.briefing import build_action_brief
from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType, StartupProfile
from src.pipeline.run_pipeline import run_full_pipeline
from src.rag.embeddings import MockEmbeddingProvider
from src.rag.retrieval import build_default_index
from src.rag.schemas import PackingConfig, RerankingConfig
from src.rag.vector_store import InMemoryVectorStore, VectorEntry


def _make_profile(
    sector: str = "Technology",
    ai_signals: list[str] | None = None,
    tech_stack: list[str] | None = None,
    description: str = "An AI company using inference for core features.",
    product_summary: str = "AI-powered analytics platform.",
) -> StartupProfile:
    return StartupProfile(
        startup_name="RAG Pipeline Test",
        website=HttpUrl("https://example.com"),
        sector=sector,
        description=description,
        product_summary=product_summary,
        ai_signals=ai_signals or ["AI signal: machine learning"],
        tech_stack_signals=tech_stack or ["PyTorch", "Docker"],
        customers=["Hospital A"],
        funding=["Series A $5M"],
        sources=[],
        confidence_score=0.7,
    )


def _make_evidence(
    claim: str = "AI company",
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
) -> Evidence:
    return Evidence(
        claim=claim,
        source_url=HttpUrl("https://example.com"),
        source_type=SourceType.OFFICIAL_SITE,
        quote_or_evidence="The company uses AI in production.",
        confidence=confidence,
        collected_at=datetime.now(UTC),
    )


def _build_populated_store() -> InMemoryVectorStore:
    emb = MockEmbeddingProvider()
    store = InMemoryVectorStore()
    chunks: dict[str, str] = {
        "nim": "NVIDIA NIM optimizes inference cost and latency.",
        "tensorrt_llm": "TensorRT-LLM reduces inference cost.",
        "triton": "Triton Inference Server reduces latency.",
        "nemo_guardrails": "NeMo Guardrails provides agent governance.",
    }
    for src, content in chunks.items():
        store.add_entry(
            VectorEntry(
                chunk_id=f"{src}_000",
                source_id=src,
                title=src,
                content=content,
                product=src,
                gap_types=["high_inference_cost"],
                url=f"https://docs.nvidia.com/{src}",
                embedding=emb.embed(content),
            )
        )
    return store


# ------------------------------------------------------------------
# Pipeline + RAG integration
# ------------------------------------------------------------------


def test_pipeline_with_rag_context() -> None:
    """Pipeline with corpus + packing â†’ rag_output is populated with packed contexts."""
    profile = _make_profile(
        sector="HealthTech",
        ai_signals=[
            "AI signal: machine learning",
            "AI signal: deep learning",
            "AI signal: neural networks",
        ],
        tech_stack=["PyTorch", "TensorRT", "Docker"],
        description=(
            "AI-native healthcare platform using deep learning"
            " for medical imaging diagnostics deployed in production."
        ),
        product_summary="Real-time AI-powered medical imaging diagnostics.",
    )
    evidence = [
        _make_evidence("AI-native healthcare platform", ConfidenceLevel.HIGH),
        _make_evidence("Deployed in production hospitals", ConfidenceLevel.HIGH),
        _make_evidence("Uses PyTorch for model training", ConfidenceLevel.HIGH),
    ]
    idx = build_default_index()
    result = run_full_pipeline(
        "RAG Test",
        profile=profile,
        evidence_list=evidence,
        chunk_index=idx,
        reranking_config=RerankingConfig(),
        packing_config=PackingConfig(),
    )
    assert result.rag_output is not None
    assert (
        result.rag_output.packing_result is not None
    ), f"packing_result is None: {result.rag_output.rag_quality_summary}"
    assert result.rag_output.missing_context is False
    assert result.rag_output.packing_result.total_packed > 0


def test_pipeline_without_rag_context() -> None:
    """Pipeline without any RAG parameters â†’ rag_output may be None or missing."""
    profile = _make_profile()
    evidence = [_make_evidence("A company", ConfidenceLevel.LOW)]
    result = run_full_pipeline("No RAG", profile=profile, evidence_list=evidence)
    # With no chunk_index passed, build_default_index() runs and may or may not
    # have chunks depending on whether data/nvidia_corpus/ exists.
    # At minimum it should not crash.
    assert result.startup_name == "No RAG"
    assert result.recommended_motion is not None


def test_pipeline_rag_empty_index() -> None:
    """Empty ChunkIndex â†’ missing_context=True."""
    from src.rag.retrieval import ChunkIndex

    empty_idx = ChunkIndex([])
    profile = _make_profile()
    evidence = [_make_evidence("AI company")]
    result = run_full_pipeline(
        "Empty Index",
        profile=profile,
        evidence_list=evidence,
        chunk_index=empty_idx,
    )
    assert result.rag_output is not None
    assert result.rag_output.missing_context is True


def test_pipeline_rag_packed_contexts_in_brief() -> None:
    """build_action_brief() auto-extracts packing_result â†’ brief has supporting section."""
    profile = _make_profile(
        sector="HealthTech",
        ai_signals=["machine learning", "deep learning"],
        tech_stack=["PyTorch", "TensorRT"],
        description="AI healthcare platform using deep learning in production.",
        product_summary="Medical imaging diagnostics.",
    )
    evidence = [
        _make_evidence("Medical imaging", ConfidenceLevel.HIGH),
        _make_evidence("Production deployment", ConfidenceLevel.HIGH),
    ]
    idx = build_default_index()
    result = run_full_pipeline(
        "Brief RAG",
        profile=profile,
        evidence_list=evidence,
        chunk_index=idx,
        reranking_config=RerankingConfig(),
        packing_config=PackingConfig(),
    )
    brief = build_action_brief(result)
    section_titles = [s.title for s in brief.sections]
    if result.rag_output and result.rag_output.packing_result:
        assert "Supporting NVIDIA Context" in section_titles, section_titles
        assert len(brief.packed_rag_contexts) > 0
    else:
        assert brief.startup_name == "Brief RAG"


def test_pipeline_rag_dropped_not_in_brief_sections() -> None:
    """dropped_contexts_debug is in the schema but NOT in the executive sections."""
    profile = _make_profile(
        sector="HealthTech",
        ai_signals=["machine learning"],
        tech_stack=["PyTorch"],
        description="AI healthcare company in production.",
        product_summary="AI diagnostics.",
    )
    evidence = [
        _make_evidence("AI healthcare", ConfidenceLevel.HIGH),
        _make_evidence("Production", ConfidenceLevel.HIGH),
    ]
    idx = build_default_index()
    result = run_full_pipeline(
        "Drop Brief",
        profile=profile,
        evidence_list=evidence,
        chunk_index=idx,
        reranking_config=RerankingConfig(),
        packing_config=PackingConfig(max_total=1),
    )
    brief = build_action_brief(result)
    assert hasattr(brief, "dropped_contexts_debug")
    section_titles = [s.title for s in brief.sections]
    dropped_sections = [t for t in section_titles if "dropped" in t.lower()]
    assert len(dropped_sections) == 0


def test_pipeline_rag_motion_unchanged() -> None:
    """recommended_motion is the same whether RAG is enabled or not."""
    profile = _make_profile(
        sector="HealthTech",
        ai_signals=["machine learning", "deep learning"],
        tech_stack=["PyTorch"],
        description="AI healthcare platform in production hospitals.",
        product_summary="Medical AI diagnostics.",
    )
    evidence = [
        _make_evidence("AI healthcare", ConfidenceLevel.HIGH),
        _make_evidence("Production hospitals", ConfidenceLevel.HIGH),
    ]
    result_no_rag = run_full_pipeline("Motion1", profile=profile, evidence_list=evidence)
    idx = build_default_index()
    result_with_rag = run_full_pipeline(
        "Motion2",
        profile=profile,
        evidence_list=evidence,
        chunk_index=idx,
        reranking_config=RerankingConfig(),
        packing_config=PackingConfig(),
    )
    assert result_no_rag.recommended_motion == result_with_rag.recommended_motion


def test_pipeline_rag_preserves_provenance() -> None:
    """Packed contexts carry source_id and url."""
    profile = _make_profile(
        sector="HealthTech",
        ai_signals=["machine learning"],
        tech_stack=["PyTorch"],
        description="AI healthcare platform in production.",
        product_summary="AI diagnostics.",
    )
    evidence = [
        _make_evidence("AI healthcare", ConfidenceLevel.HIGH),
        _make_evidence("Production", ConfidenceLevel.HIGH),
    ]
    idx = build_default_index()
    result = run_full_pipeline(
        "Prov Test",
        profile=profile,
        evidence_list=evidence,
        chunk_index=idx,
        reranking_config=RerankingConfig(),
        packing_config=PackingConfig(),
    )
    if result.rag_output and result.rag_output.packing_result:
        for pc in result.rag_output.packing_result.packed:
            assert pc.source_id, f"Missing source_id on {pc.chunk_id}"
            assert pc.url, f"Missing url on {pc.chunk_id}"


def test_pipeline_rag_quality_summary_present() -> None:
    """When RAG runs, rag_quality_summary contains useful info."""
    profile = _make_profile(
        sector="HealthTech",
        ai_signals=["machine learning", "deep learning"],
        tech_stack=["PyTorch"],
        description="AI healthcare in production.",
        product_summary="AI medical imaging.",
    )
    evidence = [
        _make_evidence("AI healthcare", ConfidenceLevel.HIGH),
        _make_evidence("Production", ConfidenceLevel.HIGH),
    ]
    idx = build_default_index()
    result = run_full_pipeline(
        "Quality",
        profile=profile,
        evidence_list=evidence,
        chunk_index=idx,
        reranking_config=RerankingConfig(),
        packing_config=PackingConfig(),
    )
    if result.rag_output and not result.rag_output.missing_context:
        assert result.rag_output.rag_quality_summary
        assert "Retrieval mode" in result.rag_output.rag_quality_summary


def test_pipeline_rag_backward_compat() -> None:
    """Existing callers without RAG params still produce valid PipelineResult."""
    profile = _make_profile()
    evidence = [_make_evidence("Legacy test")]
    result = run_full_pipeline("Legacy", profile=profile, evidence_list=evidence)
    assert result.startup_name == "Legacy"
    assert result.gap_diagnosis is not None
    assert result.recommendation is not None
    assert result.reasoning


def test_pipeline_rag_retrieval_mode_lexical() -> None:
    """Without vector store, retrieval mode should be 'lexical'."""
    profile = _make_profile(
        sector="HealthTech",
        ai_signals=["machine learning"],
        tech_stack=["PyTorch"],
        description="AI healthcare platform in production.",
        product_summary="AI diagnostics.",
    )
    evidence = [
        _make_evidence("AI healthcare", ConfidenceLevel.HIGH),
        _make_evidence("Production", ConfidenceLevel.HIGH),
    ]
    idx = build_default_index()
    result = run_full_pipeline(
        "Lex Mode",
        profile=profile,
        evidence_list=evidence,
        chunk_index=idx,
    )
    if result.rag_output and not result.rag_output.missing_context:
        assert result.rag_output.retrieval_mode == "lexical"

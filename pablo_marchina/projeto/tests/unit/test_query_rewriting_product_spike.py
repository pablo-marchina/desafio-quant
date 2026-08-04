from __future__ import annotations

from scripts import run_query_rewriting_product_spike
from src.diagnosis.schemas import EvidenceTag, GapDiagnosisResult, GapWithEvidence
from src.extraction.schemas import ConfidenceLevel, TechnicalGap
from src.rag.query_rewriting import QueryRewriteConfig, build_query_variants, retrieve_multi_query
from src.rag.rag_pipeline import run_rag_pipeline
from src.rag.retrieval import ChunkIndex
from src.rag.schemas import RagChunk, RetrievalQuery


def _index() -> ChunkIndex:
    return ChunkIndex(
        [
            RagChunk(
                chunk_id="triton_inference",
                source_id="triton",
                title="Triton",
                content="NVIDIA Triton improves GPU inference model serving latency and throughput.",
                product="Triton Inference Server",
                gap_types=["high_latency"],
                url="https://docs.nvidia.com/triton/",
            ),
            RagChunk(
                chunk_id="generic_ai",
                source_id="generic",
                title="Generic AI",
                content="Generic AI delivery and enterprise analytics overview.",
                product="Generic AI",
                gap_types=["observability_gap"],
                url="https://example.com/generic",
            ),
        ]
    )


def test_query_variants_preserve_original_and_expand_keywords() -> None:
    query = RetrievalQuery(keywords=["scale", "delivery", "enterprise"])

    variants = build_query_variants(query, QueryRewriteConfig())

    assert variants[0] == query
    assert len(variants) >= 2
    assert "inference" in variants[1].keywords
    assert "serving" in variants[1].keywords


def test_multi_query_retrieval_recovers_context_baseline_misses() -> None:
    index = _index()
    query = RetrievalQuery(keywords=["scale", "delivery", "enterprise"])

    baseline = index.retrieve(query, top_k=3)
    candidate = retrieve_multi_query(index, query, top_k=3, config=QueryRewriteConfig())

    assert "triton_inference" not in [context.chunk_id for context in baseline]
    assert "triton_inference" in [context.chunk_id for context in candidate]


def test_rag_pipeline_uses_multi_query_mode_when_configured() -> None:
    diagnosis = GapDiagnosisResult(
        startup_name="Query Rewrite Test",
        diagnosed_gaps=[
            GapWithEvidence(
                gap=TechnicalGap.HIGH_LATENCY,
                detected=True,
                confidence=ConfidenceLevel.HIGH,
                evidence_tag=EvidenceTag.INFERRED,
                reasoning="Latency gap detected.",
            )
        ],
        nvidia_technology_candidates=[],
        confidence=ConfidenceLevel.HIGH,
        reasoning="test",
    )

    output = run_rag_pipeline(
        diagnosis,
        chunk_index=_index(),
        query_rewrite_config=QueryRewriteConfig(),
    )

    assert output.missing_context is False
    assert output.retrieval_mode == "lexical_multi_query"


def test_query_rewriting_product_spike_report_promotes_product_spike() -> None:
    report = run_query_rewriting_product_spike.build_report(min_delta=0.20)

    assert report["decision"] == "PROMOTE_TO_PRODUCT_SPIKE"
    assert report["quality_delta"] >= 0.20
    assert report["case_count"] == 2

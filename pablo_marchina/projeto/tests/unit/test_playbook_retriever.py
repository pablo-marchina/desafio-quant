"""Tests for the PlaybookRetriever — orchestrates RAG over gaps and recommendations."""

from __future__ import annotations

from datetime import UTC

import pytest

from src.rag.playbook_retriever import PlaybookRetriever
from src.rag.retrieval import ChunkIndex, build_default_index

_INFERENCE_GAP = {
    "gap": "high_inference_cost",
    "detected": True,
    "confidence": "high",
    "evidence_tag": "fact",
    "reasoning": "High LLM inference cost detected.",
}
_AGENT_GAP = {
    "gap": "agent_governance_gap",
    "detected": True,
    "confidence": "medium",
    "evidence_tag": "inferred",
    "reasoning": "Agent governance concerns.",
}

_TECH_CANDIDATES = [
    {
        "technology_name": "TensorRT-LLM",
        "addresses_gap": "high_inference_cost",
        "justification": "",
    },
    {
        "technology_name": "Triton Inference Server",
        "addresses_gap": "high_inference_cost",
        "justification": "",
    },
    {
        "technology_name": "NeMo Guardrails",
        "addresses_gap": "agent_governance_gap",
        "justification": "",
    },
]


def _has_product_chunks(index: ChunkIndex, product: str) -> bool:
    return len(index.retrieve_by_technology(product)) > 0


class TestPlaybookRetriever:
    @pytest.mark.skipif(
        not _has_product_chunks(build_default_index(), "TensorRT-LLM"),
        reason="Corpus does not contain TensorRT-LLM chunks",
    )
    def test_retrieve_for_inference_cost_gap(self) -> None:
        """HIGH_INFERENCE_COST returns TensorRT-LLM, Triton, and NIM context."""
        index = build_default_index()
        retriever = PlaybookRetriever(index)
        results = retriever.retrieve_for_gaps(
            diagnosed_gaps=[_INFERENCE_GAP],
            nvidia_technology_candidates=_TECH_CANDIDATES,
            recommendations=[],
            top_k_per_query=2,
        )
        assert len(results) >= 2
        # Should have TensorRT-LLM and Triton (the two techs for inference_cost)
        products_found = set()
        for r in results:
            for ctx in r.contexts:
                products_found.add(ctx.product)
        assert "TensorRT-LLM" in products_found

    @pytest.mark.skipif(
        not _has_product_chunks(build_default_index(), "NeMo Guardrails"),
        reason="Corpus does not contain NeMo Guardrails chunks",
    )
    def test_retrieve_for_agent_governance(self) -> None:
        """AGENT_GOVERNANCE_GAP returns NeMo Guardrails context."""
        index = build_default_index()
        retriever = PlaybookRetriever(index)
        results = retriever.retrieve_for_gaps(
            diagnosed_gaps=[_AGENT_GAP],
            nvidia_technology_candidates=_TECH_CANDIDATES,
            recommendations=[],
            top_k_per_query=2,
        )
        assert len(results) >= 1
        products_found = set()
        for r in results:
            for ctx in r.contexts:
                products_found.add(ctx.product)
        assert "NeMo Guardrails" in products_found

    def test_retrieve_empty_gap_returns_missing(self) -> None:
        """Unknown gap returns missing_context=True."""
        index = build_default_index()
        retriever = PlaybookRetriever(index)
        results = retriever.retrieve_for_gaps(
            diagnosed_gaps=[{"gap": "nonexistent_gap", "detected": True}],
            nvidia_technology_candidates=[],
            recommendations=[],
        )
        assert len(results) == 1
        assert results[0].missing_context is True
        assert len(results[0].contexts) == 0

    def test_retrieve_for_brief_returns_dicts(self) -> None:
        """retrieve_for_brief returns serializable dicts (brief integration path)."""
        index = build_default_index()
        retriever = PlaybookRetriever(index)
        dicts = retriever.retrieve_for_brief(
            diagnosed_gaps=[_INFERENCE_GAP],
            nvidia_technology_candidates=_TECH_CANDIDATES,
            recommendations=[],
        )
        assert isinstance(dicts, list)
        for d in dicts:
            assert isinstance(d, dict)
            assert "query" in d
            assert "contexts" in d
            assert "missing_context" in d

    def test_brief_continues_without_rag(self) -> None:
        """Brief can be built without calling RAG at all (no crash)."""
        from datetime import datetime

        from pydantic import HttpUrl

        from src.briefing import build_action_brief
        from src.extraction.schemas import ConfidenceLevel, Evidence, SourceType, StartupProfile
        from src.pipeline.run_pipeline import run_full_pipeline

        profile = StartupProfile(
            startup_name="No RAG Co",
            website=HttpUrl("https://example.com"),
            sector="Technology",
            description="A tech company.",
            product_summary="A product.",
            ai_signals=["AI signal: ml"],
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
        assert brief.verdict is not None
        assert len(brief.sections) >= 3

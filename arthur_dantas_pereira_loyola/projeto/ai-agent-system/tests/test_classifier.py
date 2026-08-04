from __future__ import annotations

from datetime import datetime

from pydantic import HttpUrl

from radar.agents.classifier import classify_startup
from radar.schemas import (
    EvidenceClaim,
    SourceDocument,
    StartupProfile,
)


def _source(text: str, source_type: str = "official_site") -> SourceDocument:
    return SourceDocument(
        url=HttpUrl("https://example.com/test"),
        domain="example.com",
        source_type=source_type,
        title="Test Source",
        text=text,
        retrieved_at=datetime.now(),
        collection_method="test",
    )


def test_classifier_marks_ai_native_when_signals_are_strong() -> None:
    text = (
        "Startup uses proprietary AI agents for autonomous workflow orchestration. "
        "Custom models with fine-tuning on proprietary data. "
        "Multi-agent system with computer vision and predictive pipelines. "
        "Uses CUDA, Triton Inference Server and NeMo for inference."
    )
    sources = [_source(text)]
    claims = [EvidenceClaim(source_document_id="src1", text=text[:500], claim_type="ai_usage", confidence=0.8)]
    profile = StartupProfile(
        name="AI Native Corp",
        sector="Robotics",
        cited_technologies=["CUDA", "Triton Inference Server", "NeMo"],
        evidence_ids=[c.id for c in claims],
    )
    state = {
        "query": "AI Native Corp",
        "sources": sources,
        "claims": claims,
        "extracted_startups": [profile],
    }

    result = classify_startup(state)
    assert result.label == "AI-Native"
    assert result.confidence >= 0.5


def test_classifier_marks_ai_enabled_for_api_usage() -> None:
    text = (
        "Our platform uses GPT-4 API for customer service automation and "
        "LLM-based chatbot with RAG pipeline."
    )
    sources = [_source(text)]
    claims = [EvidenceClaim(source_document_id="src1", text=text[:500], claim_type="ai_usage", confidence=0.6)]
    profile = StartupProfile(
        name="AI Enabled Corp",
        cited_technologies=["LLM", "RAG"],
        evidence_ids=[c.id for c in claims],
    )
    state = {
        "query": "AI Enabled Corp",
        "sources": sources,
        "claims": claims,
        "extracted_startups": [profile],
    }

    result = classify_startup(state)
    assert result.label == "AI-Enabled"


def test_classifier_marks_non_ai_when_no_evidence() -> None:
    sources = [_source("A traditional consulting firm offering business services.")]
    claims: list[EvidenceClaim] = []
    state = {
        "query": "Non AI Corp",
        "sources": sources,
        "claims": claims,
        "extracted_startups": [],
    }

    result = classify_startup(state)
    assert result.label == "Non-AI"


def test_classifier_includes_caveats_for_nvidia_techs() -> None:
    text = "Uses NVIDIA CUDA and RAPIDS for data processing."
    sources = [_source(text)]
    claims = [EvidenceClaim(source_document_id="src1", text=text[:500], claim_type="ai_usage", confidence=0.7)]
    profile = StartupProfile(
        name="Nvidia User",
        cited_technologies=["CUDA", "RAPIDS"],
        evidence_ids=[c.id for c in claims],
    )
    state = {
        "query": "Nvidia User",
        "sources": sources,
        "claims": claims,
        "extracted_startups": [profile],
    }

    result = classify_startup(state)
    has_inception_caveat = any("NVIDIA Inception" in c for c in result.caveats)
    assert has_inception_caveat


def test_classifier_boosted_by_funding_and_founders() -> None:
    text = "AI automation platform for logistics. Raised $15M Series A."
    sources = [_source(text)]
    claims = [EvidenceClaim(source_document_id="src1", text=text[:500], claim_type="ai_usage", confidence=0.65)]
    profile = StartupProfile(
        name="Funded AI",
        sector="Logistics",
        funding="Series A",
        founders=["Ana Silva"],
        cited_technologies=["LLM"],
        evidence_ids=[c.id for c in claims],
    )
    state = {
        "query": "Funded AI",
        "sources": sources,
        "claims": claims,
        "extracted_startups": [profile],
    }

    result = classify_startup(state)
    assert result.label == "AI-Enabled"


def test_classifier_always_has_rationale() -> None:
    sources = [_source("No AI here.")]
    state = {
        "query": "No AI",
        "sources": sources,
        "claims": [],
        "extracted_startups": [],
    }

    result = classify_startup(state)
    assert isinstance(result.rationale, str)
    assert len(result.rationale) > 0


def test_classifier_confidence_is_bounded() -> None:
    text = (
        "Proprietary AI agents with custom fine-tuned models and "
        "multi-agent orchestration on NVIDIA GPUs. "
        "CUDA, TensorRT-LLM, RAPIDS, Triton, NeMo. "
        "$50M Series C. Founded by three serial entrepreneurs."
    )
    sources = [_source(text)]
    claims = [
        EvidenceClaim(source_document_id="src1", text=text[:500], claim_type="ai_usage", confidence=0.9),
        EvidenceClaim(source_document_id="src1", text=text[:500], claim_type="ai_usage", confidence=0.85),
    ]
    profile = StartupProfile(
        name="Max Confidence",
        sector="Data & Analytics",
        funding="$50M Series C",
        founders=["Founder One", "Founder Two", "Founder Three"],
        cited_technologies=["CUDA", "TensorRT-LLM", "RAPIDS", "Triton Inference Server", "NeMo"],
        evidence_ids=[c.id for c in claims],
    )
    state = {
        "query": "Max Confidence",
        "sources": sources,
        "claims": claims,
        "extracted_startups": [profile],
    }

    result = classify_startup(state)
    assert result.confidence <= 1.0
    assert result.confidence >= 0.0

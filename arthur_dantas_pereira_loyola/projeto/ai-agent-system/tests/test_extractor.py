from __future__ import annotations

import json
from datetime import datetime

from pydantic import HttpUrl

from radar.agents.extractor import (
    _extract_funding,
    _extract_technologies,
    extract_startups_and_claims,
)
from radar.schemas import SourceDocument
from radar.settings import RadarSettings


def _source(text: str, title: str | None = None, source_type: str = "official_site") -> SourceDocument:
    return SourceDocument(
        url=HttpUrl("https://example.com/test"),
        domain="example.com",
        source_type=source_type,
        title=title,
        text=text,
        retrieved_at=datetime.now(),
        collection_method="test",
    )


def test_extractor_identifies_sector() -> None:
    text = "A startup atua no setor de saúde com IA para diagnósticos médicos."
    sources = [_source(text, "Health AI Platform")]
    startups, _ = extract_startups_and_claims({"query": "HealthAI", "sources": sources})
    assert startups[0].sector == "Healthcare"


def test_extractor_identifies_no_sector_when_absent() -> None:
    text = "Uma empresa de tecnologia que usa inteligência artificial."
    sources = [_source(text, "Tech Corp")]
    startups, _ = extract_startups_and_claims({"query": "TechCorp", "sources": sources})
    assert startups[0].sector is None


def test_extractor_extracts_product_name() -> None:
    text = "Nosso produto: Analytics Pro foi desenvolvido para análises preditivas."
    sources = [_source(text, "Analytics Pro")]
    startups, _ = extract_startups_and_claims({"query": "DataCorp", "sources": sources})
    assert startups[0].product is not None


def test_extractor_finds_founders() -> None:
    text = "Founded by João Silva and Maria Santos. CEO: Carlos Pereira."
    sources = [_source(text, "Startup X")]
    startups, _ = extract_startups_and_claims({"query": "StartupX", "sources": sources})
    assert len(startups[0].founders) >= 1


def test_extractor_finds_funding() -> None:
    text = "The startup raised $5 million in seed funding."
    sources = [_source(text, "Well Funded")]
    startups, _ = extract_startups_and_claims({"query": "WellFunded", "sources": sources})
    assert startups[0].funding is not None
    assert "seed" in startups[0].funding.lower() or "$5" in startups[0].funding


def test_extractor_no_funding_when_absent() -> None:
    text = "A startup desenvolve soluções de IA para o mercado."
    result = _extract_funding(text)
    assert result is None


def test_extractor_identifies_technologies() -> None:
    text = "Usamos CUDA para treinar LLMs com PyTorch e Triton Inference Server para deploy."
    sources = [_source(text, "Tech Stack")]
    startups, _ = extract_startups_and_claims({"query": "TechStack", "sources": sources})
    techs = startups[0].cited_technologies
    assert "CUDA" in techs
    assert "ML Framework" in techs
    assert "Triton Inference Server" in techs
    assert "LLM" in techs


def test_extractor_no_duplicate_technologies() -> None:
    text = ("Usamos CUDA e mais CUDA para treinar. GPU inference com Triton. "
            "Mais GPU e inference.")
    result = _extract_technologies(text)
    assert len(result) == len(set(result))


def test_extractor_handles_unknown_techs() -> None:
    text = "Usamos uma tecnologia proprietária não listada."
    sources = [_source(text, "Mystery Startup")]
    startups, _ = extract_startups_and_claims({"query": "Mystery", "sources": sources})
    assert startups[0].cited_technologies == []


def test_extractor_generates_ai_usage_summary() -> None:
    text = "AI agents for enterprise automation with proprietary data and custom models."
    sources = [_source(text, "AI Corp", source_type="official_site")]
    startups, claims = extract_startups_and_claims({"query": "AICorp", "sources": sources})
    assert startups[0].ai_usage_summary is not None
    assert any(c.claim_type == "ai_usage" for c in claims)


def test_extractor_collects_ai_claims_across_multiple_sources() -> None:
    sources = [
        _source("AI platform for healthcare diagnostics.", source_type="official_site"),
        _source("The company raised $10M Series A for LLM automation.", source_type="news"),
    ]
    _, claims = extract_startups_and_claims({"query": "MultiSource", "sources": sources})
    ai_claims = [c for c in claims if c.claim_type == "ai_usage"]
    assert len(ai_claims) >= 2


def test_llm_extractor_uses_extracted_startup_name(monkeypatch) -> None:
    from radar.agents import extractor as extractor_module

    def fake_llm_response(**_kwargs) -> str:
        return json.dumps({
            "name": "Voa Health",
            "sector": "Healthcare",
            "product": "Voa Health",
            "founders": ["Solano Todeschini"],
            "funding": "US$3 million",
            "technologies": ["LLM"],
            "ai_usage_summary": "Evidence says Voa Health uses AI in healthcare workflows.",
        })

    monkeypatch.setattr(
        extractor_module,
        "get_settings",
        lambda: RadarSettings(enable_external_providers=True),
    )
    monkeypatch.setattr(extractor_module, "run_llm_with_fallback", fake_llm_response)

    sources = [_source("Voa Health uses AI for healthcare workflows.", "Voa Health")]
    startups, _ = extract_startups_and_claims({"query": "startups brasileiras de IA em saude", "sources": sources})

    assert startups[0].name == "Voa Health"
    assert startups[0].sector == "Healthcare"

def test_extract_technologies_does_not_match_riva_as_substring() -> None:
    from radar.agents.extractor import _extract_technologies

    technologies = _extract_technologies(
        "The platform uses private data and enterprise innovation workflows."
    )

    assert "Riva" not in technologies
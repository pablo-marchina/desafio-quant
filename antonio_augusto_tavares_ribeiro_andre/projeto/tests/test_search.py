"""Testes do adapter de busca Tavily (F1.1).

O parsing (`_parse`) é validado offline sobre uma resposta crua fixa — não precisa
de `tavily-python` instalado nem de rede. A busca real (`search`) só roda com
`TAVILY_API_KEY`, espelhando o smoke do Nemotron (F0.7).
"""

from __future__ import annotations

import pytest

from packages.config import get_settings
from packages.scraping import SearchResult, search
from packages.scraping.search import _parse

# Resposta mínima no formato do Tavily (results: url/title/content/score).
_PAYLOAD = {
    "results": [
        {
            "url": "https://startup.example/produto",
            "title": "Produto de IA",
            "content": "Plataforma de agentes com RAG.",
            "score": 0.91,
            "published_date": "2026-05-01",
        },
        {
            "url": "https://news.example/post",
            "title": "Rodada seed",
            "content": "Startup levanta rodada.",
            "score": 0.74,
        },
        {"title": "sem url", "content": "ignorada", "score": 0.5},  # sem url → descartada
    ]
}


def test_parse_maps_fields() -> None:
    results = _parse(_PAYLOAD)
    assert all(isinstance(r, SearchResult) for r in results)
    first = results[0]
    assert first.url == "https://startup.example/produto"
    assert first.title == "Produto de IA"
    assert first.snippet == "Plataforma de agentes com RAG."
    assert first.score == pytest.approx(0.91)
    assert first.published_date == "2026-05-01"


def test_parse_drops_results_without_url() -> None:
    results = _parse(_PAYLOAD)
    assert len(results) == 2  # a entrada sem url é descartada
    assert all(r.url for r in results)


def test_parse_defaults_for_missing_fields() -> None:
    second = _parse(_PAYLOAD)[1]
    assert second.published_date is None
    assert second.snippet == "Startup levanta rodada."


def test_parse_empty_payload() -> None:
    assert _parse({}) == ()


def test_search_rejects_empty_query() -> None:
    with pytest.raises(ValueError):
        search("   ")


@pytest.mark.skipif(
    not get_settings().tavily_api_key,
    reason="busca real (F1.1) precisa de TAVILY_API_KEY",
)
def test_search_real() -> None:
    results = search("NVIDIA Inception startup Brasil", max_results=3)
    assert results and all(r.url.startswith("http") for r in results)

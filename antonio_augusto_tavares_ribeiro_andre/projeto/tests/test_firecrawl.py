"""Testes do adapter de extração Firecrawl (F1.2).

O parsing (`_parse`/`_as_dict`) é validado offline sobre uma resposta crua fixa —
não precisa de `firecrawl-py` instalado nem de rede. A extração real (`scrape`) só
roda com `FIRECRAWL_API_KEY`, espelhando o smoke da busca (F1.1) e do Nemotron (F0.7).
"""

from __future__ import annotations

import pytest

from packages.config import get_settings
from packages.scraping import ExtractedPage, scrape
from packages.scraping.firecrawl import _as_dict, _parse

# Resposta no formato do SDK v2 (Document.model_dump → markdown + metadata snake_case).
_PAYLOAD = {
    "markdown": "# Startup de IA\n\nPlataforma de agentes com RAG.",
    "metadata": {
        "title": "Startup de IA",
        "description": "Agentes com RAG.",
        "source_url": "https://startup.example/produto",
        "status_code": 200,
        "language": "pt",
    },
}

# Shape REST cru (camelCase, embrulhado em `data`) — fallback que também aceitamos.
_PAYLOAD_REST = {
    "data": {
        "markdown": "# Outra\n\ntexto",
        "metadata": {"title": "Outra", "sourceURL": "https://x.example/y", "statusCode": 200},
    }
}


def test_parse_maps_fields() -> None:
    page = _parse("https://startup.example/pedido-original", _PAYLOAD)
    assert isinstance(page, ExtractedPage)
    assert page.markdown.startswith("# Startup de IA")
    assert page.title == "Startup de IA"
    assert page.description == "Agentes com RAG."
    assert page.status_code == 200
    # source_url (segue redirect) tem prioridade sobre a URL pedida
    assert page.url == "https://startup.example/produto"
    assert page.metadata["language"] == "pt"


def test_parse_unwraps_rest_envelope_camelcase() -> None:
    page = _parse("https://x.example", _PAYLOAD_REST)
    assert page.title == "Outra"
    assert page.url == "https://x.example/y"  # sourceURL camelCase
    assert page.status_code == 200


def test_parse_defaults_for_missing_fields() -> None:
    page = _parse("https://x.example", {})
    assert page.url == "https://x.example"  # cai na URL pedida
    assert page.markdown == ""
    assert page.title == ""
    assert page.status_code is None
    assert page.is_empty


def test_as_dict_normalizes_objects() -> None:
    class _Doc:
        def model_dump(self) -> dict[str, str]:
            return {"markdown": "x"}

    assert _as_dict({"markdown": "y"}) == {"markdown": "y"}
    assert _as_dict(_Doc()) == {"markdown": "x"}
    assert _as_dict(None) == {}


def test_scrape_rejects_empty_url() -> None:
    with pytest.raises(ValueError):
        scrape("   ")


@pytest.mark.skipif(
    not get_settings().firecrawl_api_key,
    reason="extração real (F1.2) precisa de FIRECRAWL_API_KEY",
)
def test_scrape_real() -> None:
    page = scrape("https://example.com")
    assert not page.is_empty and page.url.startswith("http")

"""Testes do gate de política de ToS por fonte (F1.15).

Offline: o gate lê as seeds locais (F0.9) e decide a coleta por host, sem rede. Prova a
decisão travada — diretórios §9.1 proprietários (`api_only`/`deny`) barrados; notícias
§9.2 (`allow`) e sites oficiais não-listados liberados — e a anotação por-fonte que vai
para `evidence.source_policy`.
"""

from __future__ import annotations

import pytest

from packages.scraping import (
    SourcePolicyGate,
    ToSProhibited,
    source_allowed,
    source_guard,
    source_verdict,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://distrito.me/startups/alguma",
        "https://www.startse.com/base",
        "https://www.crunchbase.com/org/acme",
        "https://tracxn.com/d/companies/x",
        "https://cubo.network/startups",
    ],
)
def test_proprietary_directories_are_blocked(url: str) -> None:
    v = source_verdict(url)
    assert not v.allowed
    assert v.policy in {"api_only", "deny"}
    assert not source_allowed(url)


def test_news_source_is_allowed_with_annotation() -> None:
    v = source_verdict("https://braziljournal.com/startup-levanta-rodada")
    assert v.allowed and v.policy == "allow"
    assert v.annotation == "brazil-journal:allow"


def test_unlisted_official_site_allowed_by_default() -> None:
    v = source_verdict("https://minha-startup.com.br/produto")
    assert v.allowed
    assert v.source_id is None
    assert v.annotation == "unlisted:allow"


def test_subdomain_matches_governing_source() -> None:
    # Subdomínio de uma fonte listada herda a política dela.
    assert not source_allowed("https://api.distrito.me/v1/startups")


def test_guard_raises_on_prohibited_and_passes_on_allowed() -> None:
    with pytest.raises(ToSProhibited) as exc:
        source_guard("https://www.openstartups.net/ranking")
    assert exc.value.source_id == "open-startups"
    # fonte liberada não levanta
    source_guard("https://neofeed.com.br/materia")


def test_placeholder_host_is_treated_as_unlisted() -> None:
    # A seed "canais oficiais" usa example.com como placeholder — não governa URLs reais.
    v = source_verdict("https://example.com/qualquer")
    assert v.allowed and v.source_id is None


def test_gate_uses_injected_sources() -> None:
    # O gate aceita uma lista de fontes própria (não só as seeds default).
    from packages.scraping.seeds import Source

    deny = Source(
        id="x-proprietaria",
        name="X",
        url="https://x-data.example",
        type="directory",
        country="BR",
        policy="deny",
        robots="unknown",
        tos_scraping="prohibited",
        legal_basis="ToS proíbe.",
    )
    gate = SourcePolicyGate(sources=(deny,))
    assert not gate.allowed("https://x-data.example/lista")
    assert gate.allowed("https://outra.example/abc")  # não-listada → liberada

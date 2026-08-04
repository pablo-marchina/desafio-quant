"""Testes das queries deterministicas de enriquecimento (noticia-first).

A ordem importa: a primeira query preenche os primeiros slots, entao a busca
de noticia/lancamento/investimento precisa vir antes. Garante tambem que GitHub
continua coberto.
"""

from apps.api.src.modules.orchestration.application.use_cases.advance_url_ingestion_job import (
    _deterministic_enrichment_queries,
)


def queries(name: str = "Acme", missing: list[str] | None = None) -> list[str]:
    return _deterministic_enrichment_queries(
        startup_name=name, missing_signals=missing or []
    )


def test_first_query_is_news_oriented() -> None:
    first = queries()[0].lower()
    assert "notícia" in first or "lançamento" in first or "investimento" in first


def test_includes_github_query() -> None:
    assert any("github" in q.lower() for q in queries())


def test_includes_funding_and_founders_query() -> None:
    assert any(
        "fundadores" in q.lower() or "funding" in q.lower() for q in queries()
    )


def test_startup_name_is_quoted_in_every_query() -> None:
    for q in queries("NeuralMind"):
        assert '"NeuralMind"' in q


def test_missing_signals_are_threaded_in() -> None:
    qs = queries(missing=["customers"])
    assert any("customers" in q for q in qs)

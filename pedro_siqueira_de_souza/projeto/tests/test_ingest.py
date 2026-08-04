"""Testes da ingestão da base NVIDIA — offline.

Troca `rag.ingest.fetch_static` por uma função que devolve a fixture parseada;
o trafilatura roda de verdade sobre esse HTML (extração é determinística),
sem rede — mesma estratégia de tests/test_enricher.py.
"""
from pathlib import Path

import pytest
from scrapling import Selector

from rag.ingest import (
    NvidiaSource,
    ingest_all,
    ingest_source,
    save_corpus,
)
from scraping.fetch import ScrapeError

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def patch_ingest_fetch(monkeypatch):
    html = (FIXTURES / "nvidia_nim.html").read_text(encoding="utf-8")
    monkeypatch.setattr("rag.ingest.fetch_static", lambda *a, **k: Selector(html))


SOURCE = NvidiaSource(tech="NVIDIA NIM", url="https://example.com/nim")


def test_ingest_source_extrai_texto_principal(patch_ingest_fetch):
    doc = ingest_source(SOURCE)

    assert doc is not None
    assert doc.tech == "NVIDIA NIM"
    # conteúdo principal presente; trafilatura tirou nav/rodapé
    assert "microsserviços de inferência otimizados" in doc.text
    assert "Todos os direitos reservados" not in doc.text
    assert "Menu de navegação" not in doc.text
    assert doc.char_count > 0


def test_ingest_source_falha_de_rede_vira_none(monkeypatch):
    def boom(*a, **k):
        raise ScrapeError("rede caiu")

    monkeypatch.setattr("rag.ingest.fetch_static", boom)
    assert ingest_source(SOURCE) is None


def test_ingest_source_conteudo_curto_vira_none(monkeypatch):
    # página praticamente vazia (simula SPA que não renderizou sem JS)
    monkeypatch.setattr(
        "rag.ingest.fetch_static",
        lambda *a, **k: Selector("<html><body><p>oi</p></body></html>"),
    )
    assert ingest_source(SOURCE) is None


def test_ingest_all_ignora_fontes_que_falham(monkeypatch):
    html = (FIXTURES / "nvidia_nim.html").read_text(encoding="utf-8")

    def fetch(url, *a, **k):
        if "ok" in url:
            return Selector(html)
        raise ScrapeError("fonte quebrada")

    monkeypatch.setattr("rag.ingest.fetch_static", fetch)
    fontes = [
        NvidiaSource(tech="Boa", url="https://example.com/ok"),
        NvidiaSource(tech="Ruim", url="https://example.com/fail"),
    ]
    docs = ingest_all(fontes)

    assert [d.tech for d in docs] == ["Boa"]


def test_save_corpus_grava_jsonl(patch_ingest_fetch, tmp_path):
    import json

    docs = ingest_all([SOURCE])
    destino = tmp_path / "nvidia_docs.jsonl"
    save_corpus(docs, destino)

    linhas = destino.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 1
    registro = json.loads(linhas[0])
    assert registro["tech"] == "NVIDIA NIM"
    assert "url" in registro and "text" in registro

"""Testes do Enricher Agent — offline.

Troca `agents.enricher.fetch_static` por uma função que devolve a fixture
parseada e `agents.enricher.search_official_site` por um fake (sem rede). O
trafilatura roda de verdade sobre o HTML (extração é determinística).
"""
from pathlib import Path

import pytest
from scrapling import Selector

from agents.enricher import enricher_node

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def patch_enricher(monkeypatch):
    html = (FIXTURES / "startup_page.html").read_text(encoding="utf-8")
    monkeypatch.setattr("agents.enricher.fetch_static", lambda *a, **k: Selector(html))
    # Por padrão a busca não encontra nada (sem rede). Testes que exercitam a
    # descoberta sobrescrevem este retorno.
    monkeypatch.setattr("agents.enricher.search_official_site", lambda *a, **k: None)
    return monkeypatch


def test_enricher_preenche_content_de_quem_tem_url(patch_enricher):
    state = {"raw_startups": [
        {"name": "Salvy", "source": "latitud.com",
         "source_url": "https://www.latitud.com/portfolio",
         "detail_url": "https://salvy.com.br"},
    ]}
    out = enricher_node(state)
    salvy = out["raw_startups"][0]

    assert salvy["content"] is not None
    # conteúdo principal presente; trafilatura tirou o boilerplate do rodapé
    assert "telefonia móvel para empresas" in salvy["content"]
    assert "Todos os direitos reservados" not in salvy["content"]


def test_enricher_descobre_site_via_busca_quando_nao_tem_url(patch_enricher):
    # Fonte só deu o nome (sem detail_url) -> o enricher BUSCA o site oficial.
    patch_enricher.setattr(
        "agents.enricher.search_official_site", lambda *a, **k: "https://salvy.com.br"
    )
    state = {"raw_startups": [
        {"name": "Salvy", "source": "wow.ac",
         "source_url": "https://www.wow.ac/portfolio"},  # sem detail_url
    ]}
    out = enricher_node(state)
    salvy = out["raw_startups"][0]

    assert salvy["detail_url"] == "https://salvy.com.br"  # site descoberto guardado
    assert salvy["content"] is not None
    assert "1 sites descobertos" in out["messages"][0][1]


def test_enricher_escala_para_navegador_quando_estatico_vem_vazio(patch_enricher):
    # SPA: o HTTP puro devolve um shell sem conteúdo (trafilatura -> None);
    # o enricher escala para o navegador, que renderiza o JS e traz o texto.
    html_real = (FIXTURES / "startup_page.html").read_text(encoding="utf-8")
    patch_enricher.setattr(
        "agents.enricher.fetch_static",
        lambda *a, **k: Selector("<html><body><div id='root'></div></body></html>"),
    )
    patch_enricher.setattr(
        "agents.enricher.fetch_dynamic", lambda *a, **k: Selector(html_real)
    )
    state = {"raw_startups": [
        {"name": "Salvy", "source": "latitud.com",
         "source_url": "https://www.latitud.com/portfolio",
         "detail_url": "https://salvy.com.br"},
    ]}
    out = enricher_node(state)

    assert out["raw_startups"][0]["content"] is not None
    assert "telefonia móvel para empresas" in out["raw_startups"][0]["content"]
    assert "1 via navegador" in out["messages"][0][1]


def test_enricher_sem_site_descoberto_fica_sem_content(patch_enricher):
    # busca não encontra nada (fake retorna None) -> content permanece None
    state = {"raw_startups": [
        {"name": "Fantasma", "source": "wow.ac",
         "source_url": "https://www.wow.ac/portfolio"},
    ]}
    out = enricher_node(state)

    assert out["raw_startups"][0].get("content") is None
    assert "0/1 enriquecidas" in out["messages"][0][1]
    assert "0 sites descobertos" in out["messages"][0][1]


def test_enricher_nao_busca_quem_ja_tem_url(patch_enricher):
    # quem já tem detail_url NÃO deve disparar busca (evita custo/rede à toa)
    def nao_deveria(*a, **k):
        raise AssertionError("search_official_site não deveria ser chamado")

    patch_enricher.setattr("agents.enricher.search_official_site", nao_deveria)
    state = {"raw_startups": [
        {"name": "Salvy", "source": "latitud.com",
         "source_url": "https://www.latitud.com/portfolio",
         "detail_url": "https://salvy.com.br"},
    ]}
    out = enricher_node(state)
    assert out["raw_startups"][0]["content"] is not None


def test_enricher_nao_muta_o_estado_original(patch_enricher):
    original = {"name": "Salvy", "source": "latitud.com",
                "source_url": "https://www.latitud.com/portfolio",
                "detail_url": "https://salvy.com.br"}
    enricher_node({"raw_startups": [original]})

    # o dict original do estado não foi alterado (cópia rasa no nó)
    assert "content" not in original

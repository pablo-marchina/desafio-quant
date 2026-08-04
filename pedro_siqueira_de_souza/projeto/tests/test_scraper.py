"""Testes do Scraper Agent — sempre offline.

Mesma filosofia do FakeLLM: o teste troca a camada de rede por HTML salvo.
`fetch_dynamic` (em scraping.fetch, importado por scraping.wow) é substituído
por uma função que devolve um `Selector` montado a partir da fixture — então
o adapter roda a MESMA lógica de parsing, sem abrir navegador nem tocar a rede.
"""
from pathlib import Path

import pytest
from scrapling import Selector

from agents.scraper import scraper_node
from scraping.anjos import AnjosAdapter
from scraping.latitud import LatitudAdapter
from scraping.openstartups import OpenStartupsAdapter
from scraping.wow import WowAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def patch_wow_fetch(monkeypatch):
    """Faz `scraping.wow.fetch_dynamic` devolver a fixture parseada."""
    html = (FIXTURES / "wow_portfolio.html").read_text(encoding="utf-8")
    monkeypatch.setattr("scraping.wow.fetch_dynamic", lambda *a, **k: Selector(html))


@pytest.fixture
def patch_openstartups_fetch(monkeypatch):
    """Faz `scraping.openstartups.fetch_dynamic` devolver a fixture parseada."""
    html = (FIXTURES / "openstartups_ranking.html").read_text(encoding="utf-8")
    monkeypatch.setattr("scraping.openstartups.fetch_dynamic", lambda *a, **k: Selector(html))


@pytest.fixture
def patch_anjos_fetch(monkeypatch):
    """Faz `scraping.anjos.fetch_static` devolver a fixture parseada."""
    html = (FIXTURES / "anjos_cases.html").read_text(encoding="utf-8")
    monkeypatch.setattr("scraping.anjos.fetch_static", lambda *a, **k: Selector(html))


@pytest.fixture
def patch_latitud_fetch(monkeypatch):
    """Faz `scraping.latitud.fetch_dynamic` devolver a fixture parseada."""
    html = (FIXTURES / "latitud_portfolio.html").read_text(encoding="utf-8")
    monkeypatch.setattr("scraping.latitud.fetch_dynamic", lambda *a, **k: Selector(html))


def test_wow_adapter_descobre_startups_do_grid(patch_wow_fetch):
    startups = WowAdapter().discover()
    nomes = {s.name for s in startups}

    # nomes do grid entram; ruído (alt vazio, nome de arquivo, logo) NÃO.
    assert {"Becon", "Squid", "Aegro", "Movidesk", "Dietbox"} <= nomes
    assert "WOW Aceleradora" not in nomes
    assert "banner.png" not in nomes
    assert "" not in nomes
    # todas carregam a fonte e a página de origem
    assert all(s.source == "wow.ac" for s in startups)
    assert all(s.source_url.endswith("/portfolio") for s in startups)


def test_wow_adapter_enriquece_detail_url_dos_cases(patch_wow_fetch):
    por_nome = {s.name.lower(): s for s in WowAdapter().discover()}

    # case que TAMBÉM está no grid: enriquece a entrada existente
    assert por_nome["becon"].detail_url == "https://www.wow.ac/cases/becon"
    # case que NÃO está no grid: entra a partir do slug
    assert "treasy" in por_nome
    assert por_nome["treasy"].detail_url == "https://www.wow.ac/cases/treasy"
    # startup só do grid não tem detail_url
    assert por_nome["squid"].detail_url is None


def test_openstartups_adapter_extrai_nome_e_setor(patch_openstartups_fetch):
    startups = OpenStartupsAdapter().discover()
    por_nome = {s.name: s for s in startups}

    # cabeçalho (<th>) e linha de rank não-numérico ("-") são descartados
    assert "Linha Espúria" not in por_nome
    assert set(por_nome) == {"Leverpro", "Weknow", "Melvin"}
    # setor vem de graça desta fonte
    assert por_nome["Leverpro"].sector == "FinTechs"
    # quando há subsetor (2ª linha), fica só o setor principal
    assert por_nome["Melvin"].sector == "IndTechs"
    assert all(s.source == "openstartups.net" for s in startups)


def test_anjos_adapter_le_alts_estaticos(patch_anjos_fetch):
    startups = AnjosAdapter().discover()
    nomes = {s.name for s in startups}

    assert {"squid", "CleanCloud", "manipula-e", "conpass"} <= nomes
    # ruído filtrado: pixel do FB, logo da marca, nome de arquivo
    assert "fbpx" not in nomes
    assert "banner.png" not in nomes
    assert not any("logo" in n.lower() for n in nomes)
    assert all(s.source == "anjosdobrasil.net" for s in startups)


def test_latitud_adapter_deriva_nome_do_dominio(patch_latitud_fetch):
    por_nome = {s.name: s for s in LatitudAdapter().discover()}

    # investidas: nome derivado do domínio + site oficial em detail_url
    assert set(por_nome) == {"salvy", "datanomik", "tapi", "agentastra"}
    assert por_nome["salvy"].detail_url == "https://salvy.com.br"
    assert por_nome["tapi"].detail_url == "https://tapi.la"
    # ruído descartado: a própria Latitud, rede social, link com path profundo
    assert "latitud" not in por_nome
    assert "linkedin" not in por_nome
    assert "algumblog" not in por_nome


def test_scraper_node_agrega_por_fonte(patch_wow_fetch):
    resultado = scraper_node({"sources": ["wow.ac"]})

    assert len(resultado["raw_startups"]) > 0
    # itens são RawStartup serializados (dicts), prontos para o estado
    assert all(item["source"] == "wow.ac" for item in resultado["raw_startups"])
    assert len(resultado["messages"]) == 1


def test_scraper_node_ignora_fonte_sem_adapter():
    # fonte do catálogo que ainda não tem adapter no v1: não quebra, só avisa.
    resultado = scraper_node({"sources": ["distrito.me"]})

    assert resultado["raw_startups"] == []
    assert "sem adapter" in resultado["messages"][0][1]

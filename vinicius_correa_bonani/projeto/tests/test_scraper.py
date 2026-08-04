"""Testes do Scraper (offline — fetch monkeypatchado)."""

from app import scraper
from app.state import RadarState

HTML_FIXTURE = """
<html><head><title>Tractian</title></head><body>
<article>
<h1>Tractian</h1>
<p>A Tractian e uma startup de manutencao preditiva industrial que usa sensores
IoT e inteligencia artificial para monitorar maquinas em tempo real.</p>
<p>Fundada em 2019, atende clientes da industria de manufatura com analise de
vibracao e temperatura, prevendo falhas antes que acontecam.</p>
</article>
</body></html>
"""


def test_extract_text_pega_texto_principal():
    texto = scraper.extract_text(HTML_FIXTURE)
    assert "Tractian" in texto
    assert len(texto) > 50


def test_scraper_preenche_conteudo_com_fonte(monkeypatch):
    monkeypatch.setattr(scraper, "permitido_por_robots", lambda url: True)
    monkeypatch.setattr(scraper, "fetch_url", lambda url: HTML_FIXTURE)

    state = RadarState(urls_busca=["https://exemplo.com/tractian"])
    out = scraper.scraper(state)

    assert len(out["conteudo_bruto"]) == 1
    item = out["conteudo_bruto"][0]
    assert item["fonte"] == "https://exemplo.com/tractian"
    assert "Tractian" in item["texto"]


def test_scraper_acumula_e_deduplica_por_fonte(monkeypatch):
    # simula o retry do loop: já havia um trecho; a nova rodada traz a MESMA fonte
    # (deve ser pulada) + uma nova (deve ser acrescentada).
    monkeypatch.setattr(scraper, "permitido_por_robots", lambda url: True)
    monkeypatch.setattr(scraper, "fetch_url", lambda url: HTML_FIXTURE)

    state = RadarState(
        conteudo_bruto=[{"texto": "antigo", "fonte": "https://a.com/x"}],
        urls_busca=["https://a.com/x", "https://b.com/novo"],
    )
    out = scraper.scraper(state)

    fontes = [t["fonte"] for t in out["conteudo_bruto"]]
    assert fontes == ["https://a.com/x", "https://b.com/novo"]  # antigo preservado + novo
    assert out["conteudo_bruto"][0]["texto"] == "antigo"        # não re-raspou a fonte já vista

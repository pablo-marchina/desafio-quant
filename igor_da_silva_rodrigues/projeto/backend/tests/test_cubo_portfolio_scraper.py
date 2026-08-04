import requests

from app.scraping.cubo_portfolio_scraper import (
    StartupCubo,
    calcular_score_relevancia_ia,
    coletar_startups_cubo,
    scrape_cubo_startups_portfolio,
)


class FakeResponse:
    def __init__(self, json_data=None, text="", status_code=200):
        self._json_data = json_data
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._json_data


def test_calcular_score_relevancia_ia_identifies_strong_and_medium_terms():
    result = calcular_score_relevancia_ia(
        "Plataforma de inteligencia artificial, automacao e dados."
    )

    assert result["score"] == 5
    assert result["termos_fortes_encontrados"] == ["inteligencia artificial"]
    assert result["termos_medios_encontrados"] == ["automacao", "dados"]
    assert result["vale_aprofundar"] is True


def test_startup_cubo_to_dict_serializes_dataclass():
    startup = StartupCubo(
        nome="Clara",
        site="https://clara.com.br",
        cidade="Sao Paulo",
        estado="SP",
        pais="Brasil",
        categoria="Financeiro",
        descricao_curta="Descricao",
        logo_url=None,
        link_perfil_cubo="https://cubo.itau/startups-portfolio/clara",
    )

    payload = startup.to_dict()

    assert payload["nome"] == "Clara"
    assert payload["site"] == "https://clara.com.br"
    assert payload["fonte"] == "Cubo Itaú - Vitrine de Startups"
    assert payload["coletado_em"]


def test_coletar_startups_cubo_uses_api_pagination(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        if "api.site.cubo.itau/startups/" in url:
            slug = url.rsplit("/", 1)[-1]
            return FakeResponse(
                json_data={
                    "siteUrl": f"{slug}.com.br",
                    "countries": [{"name": "Brasil"}],
                    "segments": [{"name": "Financeiro"}],
                }
            )
        if "cubo.itau/startups-portfolio/" in url:
            return FakeResponse(text="<main><p>Localização: Sao Paulo, SP</p></main>")
        if params["page"] == 1:
            return FakeResponse(
                json_data={
                    "startups": [
                        _api_item("1", "clara", "Clara", "Financeiro"),
                        _api_item("2", "autou", "AutoU", "Produtividade"),
                    ],
                    "hasNext": True,
                }
            )
        return FakeResponse(
            json_data={
                "startups": [_api_item("3", "biti9", "Biti9", "Produtividade")],
                "hasNext": False,
            }
        )

    monkeypatch.setattr(requests, "get", fake_get)

    startups = coletar_startups_cubo(output_dir=tmp_path, delay_seconds=0)

    assert [startup.nome for startup in startups] == ["Clara", "AutoU", "Biti9"]
    assert calls[0][1]["page"] == 1
    assert any(call[1] and call[1].get("page") == 2 for call in calls)
    assert startups[0].link_perfil_cubo == "https://cubo.itau/startups-portfolio/clara"
    assert startups[0].site == "https://clara.com.br"
    assert startups[0].cidade == "Sao Paulo"
    assert startups[0].estado == "SP"
    assert list(tmp_path.glob("vitrine_cubo_*.json"))


def test_coletar_startups_cubo_resumes_from_source_offset(monkeypatch, tmp_path):
    requested_pages = []

    def fake_get(url, params=None, headers=None, timeout=None):
        if "api.site.cubo.itau/startups/" in url:
            return FakeResponse(json_data={"siteUrl": "startup51.example"})
        if "cubo.itau/startups-portfolio/" in url:
            return FakeResponse(text="<main></main>")
        requested_pages.append(params["page"])
        return FakeResponse(
            json_data={
                "startups": [_api_item("51", "startup-51", "Startup 51", "Dados")],
                "hasNext": False,
            }
        )

    monkeypatch.setattr(requests, "get", fake_get)

    startups = coletar_startups_cubo(
        limit=1,
        offset=50,
        output_dir=tmp_path,
        delay_seconds=0,
    )

    assert requested_pages == [2]
    assert [startup.nome for startup in startups] == ["Startup 51"]


def test_scrape_cubo_startups_portfolio_reports_missing_detail_fields(monkeypatch, tmp_path):
    def fake_get(url, params=None, headers=None, timeout=None):
        if "api.site.cubo.itau/startups/" in url:
            return FakeResponse(json_data={})
        if "cubo.itau/startups-portfolio/" in url:
            return FakeResponse(text="<main><h1>Clara</h1></main>")
        return FakeResponse(
            json_data={
                "startups": [_api_item("1", "clara", "Clara", "Financeiro")],
                "hasNext": False,
            }
        )

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.chdir(tmp_path)

    result = scrape_cubo_startups_portfolio(limit=1)

    assert result["status"] == "parcial"
    assert result["startups"][0]["site"] is None
    assert result["startups"][0]["cidade"] is None
    assert result["startups"][0]["estado"] is None
    assert len(result["erros"]) == 2


def test_coletar_startups_cubo_uses_jina_fallback_and_saves_markdown(
    monkeypatch,
    tmp_path,
):
    def fake_get(url, params=None, headers=None, timeout=None):
        if "api.site.cubo.itau" in url:
            raise requests.Timeout("api timeout")
        if "r.jina.ai" in url:
            return FakeResponse(
                text="""
## Clara
Plataforma de inteligencia artificial para financeiro.
Segmento
Financeiro
[Saiba mais](https://cubo.itau/startups-portfolio/clara)
""",
            )
        raise AssertionError("HTML fallback should not be called")

    monkeypatch.setattr(requests, "get", fake_get)

    startups = coletar_startups_cubo(limit=1, output_dir=tmp_path, delay_seconds=0)

    assert len(startups) == 1
    assert startups[0].nome == "Clara"
    assert startups[0].categoria == "Financeiro"
    assert list((tmp_path / "_markdown").glob("vitrine_cubo_*.md"))


def test_coletar_startups_cubo_uses_html_fallback(monkeypatch, tmp_path):
    def fake_get(url, params=None, headers=None, timeout=None):
        if "api.site.cubo.itau" in url or "r.jina.ai" in url:
            raise requests.ConnectionError("unavailable")
        return FakeResponse(
            text="""
<html>
  <body>
    <div class="startup card">
      <h2>Voltta</h2>
      <p>EnergyTech com automacao de recarga.</p>
      <a href="/startups-portfolio/voltta">Saiba mais</a>
      <img src="/logo.png" />
      <span>Segmento Energia</span>
    </div>
  </body>
</html>
""",
        )

    monkeypatch.setattr(requests, "get", fake_get)

    startups = coletar_startups_cubo(limit=1, output_dir=tmp_path, delay_seconds=0)

    assert len(startups) == 1
    assert startups[0].nome == "Voltta"
    assert startups[0].link_perfil_cubo == "https://cubo.itau/startups-portfolio/voltta"
    assert startups[0].logo_url == "https://cubo.itau/logo.png"


def test_coletar_startups_cubo_removes_duplicates_by_name(monkeypatch, tmp_path):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(
            json_data={
                "startups": [
                    _api_item("1", "clara", "Clara", "Financeiro"),
                    _api_item("2", "clara-duplicada", "Clara", "Financeiro"),
                ],
                "hasNext": False,
            }
        )

    monkeypatch.setattr(requests, "get", fake_get)

    startups = coletar_startups_cubo(output_dir=tmp_path, delay_seconds=0)

    assert len(startups) == 1


def _api_item(id_, slug, name, segment):
    return {
        "id": id_,
        "slug": slug,
        "name": name,
        "segment": segment,
        "description": "Plataforma com inteligencia artificial e dados.",
        "image_url": f"https://img.example/{slug}.png",
        "gold_seal": True,
        "gold_seal_image": "https://img.example/gold.png",
    }

import json

import pytest
import requests

from app.agents.scraper_agent import (
    FirecrawlClient,
    FirecrawlSearchClient,
    ScraperAgent,
    executar_scraper_agent,
    salvar_resultado_scraper,
)


class FakeResponse:
    def __init__(
        self,
        text="",
        status_code=200,
        url="https://example.com",
        json_payload=None,
        content=None,
    ):
        self.text = text
        self.status_code = status_code
        self.url = url
        self._json_payload = json_payload
        self.content = content if content is not None else text.encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if "localhost:8080/search" in url:
            return FakeResponse(
                url=url,
                json_payload={
                    "results": [
                        {
                            "title": "Caso IA via SearXNG",
                            "url": "https://example.com/ia",
                            "content": "Startup usa machine learning e NVIDIA para modelos.",
                        },
                        {
                            "title": "Sobre via SearXNG",
                            "url": "https://example.com/sobre",
                            "content": "Pagina institucional.",
                        },
                    ]
                },
            )
        if url == "https://static.example.com/artigo":
            return FakeResponse(
                text="""
                <html>
                  <head><title>Artigo Tecnico</title></head>
                  <body><article><h1>Artigo Tecnico</h1><p>Texto sobre machine learning em producao.</p></article></body>
                </html>
                """,
                url=url,
            )
        if url == "https://feed.example.com/rss":
            return FakeResponse(
                text="""
                <rss><channel>
                  <item>
                    <title>Clara Pagamentos usa IA</title>
                    <link>https://news.example.com/clara</link>
                    <description>Noticia sobre machine learning.</description>
                    <pubDate>Tue, 23 Jun 2026 10:00:00 GMT</pubDate>
                  </item>
                  <item>
                    <title>Outra empresa</title>
                    <link>https://news.example.com/outra</link>
                    <description>Sem relacao.</description>
                  </item>
                </channel></rss>
                """,
                url=url,
            )
        return FakeResponse(status_code=404, url=url)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if "api.firecrawl.dev/v2/search" in url:
            return FakeResponse(
                url=url,
                json_payload={
                    "data": {
                        "web": [
                            {
                                "title": "Caso IA via Firecrawl",
                                "url": "https://example.com/ia",
                                "description": "Startup usa machine learning e NVIDIA para modelos.",
                            }
                        ]
                    }
                },
            )
        if "api.firecrawl.dev/v2/scrape" in url:
            target_url = kwargs["json"]["url"]
            return FakeResponse(
                url=url,
                json_payload={
                    "success": True,
                    "data": {
                        "markdown": "# Caso IA\n\nUsamos machine learning e NVIDIA.",
                        "metadata": {
                            "title": "Caso IA",
                            "sourceURL": target_url,
                        },
                    },
                },
            )
        return FakeResponse(status_code=404, url=url)


class FakeWebCache:
    def __init__(self):
        self.values = {}
        self.usage = []

    def get(self, url):
        return self.values.get(url)

    def set(self, url, value):
        self.values[url] = value

    def record_usage(self, url, **payload):
        self.usage.append({"url": url, **payload})


class BudgetWebCache(FakeWebCache):
    def __init__(self, reservation):
        super().__init__()
        self.reservation = reservation

    def reserve_request(self, url, **payload):
        return self.reservation


class BrokenWebCache:
    def get(self, url):
        raise RuntimeError("cache indisponivel")

    def set(self, url, value):
        raise RuntimeError("cache indisponivel")

    def record_usage(self, url, **payload):
        raise RuntimeError("ledger indisponivel")


class PaymentRequiredSession:
    def __init__(self):
        self.calls = 0

    def post(self, *args, **kwargs):
        self.calls += 1
        response = FakeResponse(status_code=402)

        def raise_with_response():
            error = requests.HTTPError("HTTP 402")
            error.response = response
            raise error

        response.raise_for_status = raise_with_response
        return response


def test_scraper_agent_uses_searxng_and_firecrawl_for_web_search(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "searxng")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    session = FakeSession()
    plano = {
        "startup": "Clara Pagamentos",
        "tarefas": [
            {
                "id": "task_1",
                "tipo": "busca_web",
                "consulta": '"Clara Pagamentos" "machine learning"',
                "max_resultados": 2,
                "camada": 1,
                "objetivo": "Detectar mencoes diretas a ML",
            }
        ],
    }

    resultado = executar_scraper_agent(plano, session=session, delay_seconds=0)

    assert resultado["status"] == "completo"
    assert resultado["metricas"]["tarefas_executadas"] == 1
    assert resultado["metricas"]["total_resultados_busca"] == 2
    assert resultado["metricas"]["total_paginas_coletadas"] == 1
    assert resultado["resultados_buscas"][0]["provedor_busca"] == "searxng"
    assert resultado["resultados_buscas"][0]["potencial_alto"] is True
    assert resultado["paginas_completas"][0]["conteudo_markdown"].startswith("# Caso IA")
    assert any(call[0] == "GET" and "localhost:8080/search" in call[1] for call in session.calls)
    assert any(call[0] == "POST" and "api.firecrawl.dev/v2/scrape" in call[1] for call in session.calls)


def test_scraper_agent_uses_firecrawl_search_when_selected(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "firecrawl")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    plano = {
        "startup": "Clara Pagamentos",
        "tarefas": [
            {
                "id": "task_1",
                "tipo": "busca_web",
                "consulta": '"Clara Pagamentos" "machine learning"',
                "max_resultados": 2,
            }
        ],
    }

    resultado = executar_scraper_agent(plano, session=FakeSession(), delay_seconds=0)

    assert resultado["status"] == "completo"
    assert resultado["resultados_buscas"][0]["provedor_busca"] == "firecrawl"


def test_firecrawl_search_opens_circuit_after_payment_error(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    session = PaymentRequiredSession()
    ledger = BudgetWebCache(
        {"allowed": True, "reservation_id": "search-reservation", "warning": False}
    )
    client = FirecrawlSearchClient(session, delay_seconds=0, usage_ledger=ledger)

    with pytest.raises(requests.HTTPError):
        client.search("startup IA", 5)
    with pytest.raises(ValueError, match="desativado"):
        client.search("outra consulta", 5)

    assert session.calls == 1
    assert ledger.usage[0]["operation"] == "search"
    assert ledger.usage[0]["success"] is False


def test_scraper_agent_converts_search_planner_plan_to_search_tasks(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "searxng")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    plano = {
        "startup": "Clara Pagamentos",
        "plano_consultas": [
            {
                "consulta": '"Clara Pagamentos" "NVIDIA"',
                "objetivo": "Buscar stack NVIDIA",
                "camada": 3,
            }
        ],
    }

    resultado = executar_scraper_agent(plano, session=FakeSession(), delay_seconds=0)

    assert resultado["resultados"][0]["task_id"] == "task_1"
    assert resultado["resultados"][0]["tipo"] == "busca_web"
    assert resultado["resultados"][0]["camada"] == 3


def test_scraper_agent_uses_firecrawl_for_direct_access(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    plano = {
        "startup": "Clara Pagamentos",
        "tarefas": [
            {
                "id": "task_site",
                "tipo": "acesso_direto",
                "url": "https://example.com/ia",
                "extrator": "firecrawl",
                "camada": 6,
                "objetivo": "Coletar site com Firecrawl.",
            }
        ],
    }

    resultado = executar_scraper_agent(plano, session=FakeSession(), delay_seconds=0)

    assert resultado["status"] == "completo"
    assert resultado["paginas_completas"][0]["extrator"] == "firecrawl"
    assert resultado["paginas_completas"][0]["titulo_pagina"] == "Caso IA"


def test_firecrawl_reuses_cache_without_api_key(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    cache = FakeWebCache()
    url = "https://example.com/ia"
    cache.values[url] = {
        "url": url,
        "titulo_pagina": "Caso em cache",
        "conteudo_markdown": "# IA",
        "metadados": {},
        "extrator": "firecrawl",
    }
    session = FakeSession()
    client = FirecrawlClient(session, cache=cache, delay_seconds=0)

    resultado = client.scrape(url)

    assert resultado["metadados"]["cache_hit"] is True
    assert client.stats["cache_hits"] == 1
    assert not any(call[0] == "POST" for call in session.calls)
    assert cache.usage[0]["cache_hit"] is True


def test_firecrawl_stores_response_and_reuses_it(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    cache = FakeWebCache()
    session = FakeSession()
    client = FirecrawlClient(session, cache=cache, delay_seconds=0)

    first = client.scrape("https://example.com/ia")
    second = client.scrape("https://example.com/ia")

    assert first["titulo_pagina"] == "Caso IA"
    assert second["metadados"]["cache_hit"] is True
    assert client.stats["requests"] == 1
    assert client.stats["cache_hits"] == 1
    assert client.stats["failures"] == 0
    assert sum(call[0] == "POST" for call in session.calls) == 1


def test_firecrawl_enforces_request_budget(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    client = FirecrawlClient(FakeSession(), delay_seconds=0, max_requests=1)

    client.scrape("https://example.com/primeira")

    with pytest.raises(ValueError, match="Orcamento Firecrawl esgotado"):
        client.scrape("https://example.com/segunda")
    assert client.stats["requests"] == 1
    assert client.stats["budget_exceeded"] == 1


def test_firecrawl_enforces_atomic_batch_budget(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    cache = BudgetWebCache({"allowed": False, "used": 100, "warning": True})
    client = FirecrawlClient(FakeSession(), cache=cache, delay_seconds=0)

    with pytest.raises(ValueError, match="do lote esgotado"):
        client.scrape("https://example.com/ia")

    assert client.stats["batch_budget_exceeded"] == 1


def test_firecrawl_reports_batch_budget_warning(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    cache = BudgetWebCache(
        {"allowed": True, "reservation_id": "reservation-1", "used": 80, "warning": True}
    )
    client = FirecrawlClient(FakeSession(), cache=cache, delay_seconds=0)

    client.scrape("https://example.com/ia")

    assert client.stats["batch_budget_warning"] == 1
    assert cache.usage[0]["reservation_id"] == "reservation-1"


def test_firecrawl_continues_when_cache_is_unavailable(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-test")
    client = FirecrawlClient(
        FakeSession(), cache=BrokenWebCache(), delay_seconds=0
    )

    resultado = client.scrape("https://example.com/ia")

    assert resultado["titulo_pagina"] == "Caso IA"
    assert client.stats["requests"] == 1


def test_scraper_agent_uses_trafilatura_for_direct_access():
    plano = {
        "startup": "Clara Pagamentos",
        "tarefas": [
            {
                "id": "task_static",
                "tipo": "acesso_direto",
                "url": "https://static.example.com/artigo",
                "extrator": "trafilatura",
                "camada": 6,
                "objetivo": "Coletar artigo estatico.",
            }
        ],
    }

    resultado = executar_scraper_agent(plano, session=FakeSession(), delay_seconds=0)

    assert resultado["status"] == "completo"
    assert resultado["paginas_completas"][0]["extrator"] == "trafilatura"
    assert "machine learning" in resultado["paginas_completas"][0]["conteudo_textual"]


def test_scraper_agent_falls_back_to_trafilatura_when_firecrawl_key_is_missing(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    plano = {
        "startup": "Clara Pagamentos",
        "tarefas": [
            {
                "id": "task_static",
                "tipo": "acesso_direto",
                "url": "https://static.example.com/artigo",
                "extrator": "firecrawl",
                "camada": 6,
                "objetivo": "Coletar com fallback.",
            }
        ],
    }

    resultado = executar_scraper_agent(plano, session=FakeSession(), delay_seconds=0)

    assert resultado["status"] == "completo"
    assert resultado["paginas_completas"][0]["extrator"] == "trafilatura"


def test_scraper_agent_executes_feed_rss():
    plano = {
        "startup": "Clara Pagamentos",
        "tarefas": [
            {
                "id": "task_feed",
                "tipo": "feed_rss",
                "url": "https://feed.example.com/rss",
                "filtro_titulo": "Clara Pagamentos",
            }
        ],
    }

    resultado = executar_scraper_agent(plano, session=FakeSession(), delay_seconds=0)

    assert resultado["status"] == "completo"
    assert len(resultado["resultados"][0]["itens_filtrados"]) == 1
    assert resultado["resultados"][0]["itens_filtrados"][0]["titulo"] == "Clara Pagamentos usa IA"


def test_salvar_resultado_scraper_writes_json(tmp_path):
    resultado = {
        "startup": "Clara Pagamentos",
        "timestamp_coleta": "2026-06-23T14:30:00Z",
        "status": "completo",
        "metricas": {},
        "resultados": [],
        "resultados_buscas": [],
        "paginas_completas": [],
        "varredura_complementar": [],
        "erros": [],
    }

    path = salvar_resultado_scraper(resultado, tmp_path)
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert path.name.startswith("evidencias_clara-pagamentos_")
    assert saved["startup"] == "Clara Pagamentos"


class NoResultsSearchClient:
    def search(self, query, count):
        raise RuntimeError("No results found.")


def test_scraper_agent_isolates_unexpected_search_provider_error():
    plano = {
        "startup": "Clara Pagamentos",
        "tarefas": [
            {
                "id": "task_sem_resultado",
                "tipo": "busca_web",
                "consulta": '"Clara Pagamentos" termo inexistente',
                "max_resultados": 2,
            }
        ],
    }

    resultado = executar_scraper_agent(
        plano,
        search_client=NoResultsSearchClient(),
        delay_seconds=0,
    )

    assert resultado["status"] == "parcial"
    assert resultado["metricas"]["tarefas_executadas"] == 1
    assert resultado["metricas"]["tarefas_com_erro"] == 1
    assert resultado["erros"][0]["erro"] == "No results found."


def test_adaptive_stop_requires_tasks_sources_pages_and_layer(monkeypatch):
    monkeypatch.setenv("SCRAPER_MIN_TASKS", "8")
    monkeypatch.setenv("SCRAPER_MIN_UNIQUE_SOURCES", "10")
    monkeypatch.setenv("SCRAPER_MIN_FULL_PAGES", "3")
    metrics = {"tarefas_executadas": 8, "total_paginas_coletadas": 3}

    assert ScraperAgent._coverage_is_sufficient(
        metrics,
        {f"https://source{index}.example" for index in range(10)},
        highest_layer=4,
    )
    assert not ScraperAgent._coverage_is_sufficient(
        metrics,
        {"https://one.example"},
        highest_layer=4,
    )

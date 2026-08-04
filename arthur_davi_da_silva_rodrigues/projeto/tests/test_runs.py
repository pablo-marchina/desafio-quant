from datetime import UTC, datetime

import httpx
from fastapi.testclient import TestClient

from app.discovery.market import NewsArticle
from app.main import create_app


def test_discovery_run_returns_crawled_ranked_candidates(monkeypatch) -> None:
    fake_articles = (
        NewsArticle(
            title=(
                "Startup Clara AI usa IA generativa e agentes para automatizar "
                "documentos de saúde"
            ),
            url="https://news.example/clara-ai",
            published_at=datetime.now(UTC),
            source="News Example",
            query="IA generativa para saúde",
        ),
        NewsArticle(
            title="Clara AI capta rodada para copiloto médico com LLM",
            url="https://news.example/clara-ai-funding",
            published_at=datetime.now(UTC),
            source="Funding News",
            query="IA generativa para saúde",
        ),
        NewsArticle(
            title="Empresa Atlas AI lança plataforma de IA para atendimento",
            url="https://news.example/atlas",
            published_at=datetime.now(UTC),
            source="Tech News",
            query="IA generativa para saúde",
        ),
    )

    monkeypatch.setattr(
        "app.discovery.market.crawl_market_articles",
        lambda queries, client=None: fake_articles,
    )
    client = TestClient(create_app())

    response = client.post(
        "/runs/discovery",
        json={"query": "IA generativa para saúde", "country": "Brasil", "max_results": 8},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["run_type"] == "market_discovery"
    assert body["country"] == "Brasil"
    assert "saúde" in body["summary"]
    assert body["trend_signals"]
    assert body["suggested_queries"]
    assert body["source_targets"]
    assert body["live_search_links"]
    assert body["crawl_status"] == "succeeded"
    assert body["crawled_source_count"] == 3
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["name"] == "Clara AI"
    assert body["candidates"][0]["rank_score"] >= body["candidates"][1]["rank_score"]
    assert body["candidates"][0]["evidence_count"] == 2
    assert body["candidates"][0]["ai_native_signals"]
    assert body["candidates"][0]["nvidia_opportunity"]
    assert body["candidates"][0]["source_urls"]
    assert body["evaluation_checklist"]
    assert body["next_actions"]
    assert body["live_search_links"][0]["url"].startswith("https://www.google.com/search")


def test_discovery_run_can_rank_crawled_candidates_with_llm(monkeypatch) -> None:
    fake_articles = (
        NewsArticle(
            title="Clara AI capta rodada para copiloto médico com LLM",
            url="https://news.example/clara-ai-funding",
            published_at=datetime.now(UTC),
            source="Funding News",
            query="IA generativa para saúde",
        ),
    )

    monkeypatch.setattr(
        "app.discovery.market.crawl_market_articles",
        lambda queries, client=None: fake_articles,
    )
    monkeypatch.setattr("app.discovery.market.is_llm_enabled", lambda settings: True)
    monkeypatch.setattr(
        "app.discovery.market.generate_openai_json",
        lambda **kwargs: {
            "candidates": [
                {
                    "name": "Clara AI",
                    "sector": "Saúde",
                    "website": "https://clara.example",
                    "why_relevant": "Startup IA-native com copiloto médico baseado em LLM.",
                    "ai_native_signals": ["LLM", "copiloto médico"],
                    "nvidia_opportunity": ["TensorRT-LLM", "NVIDIA Clara"],
                    "wrapper_risk": 0.74,
                    "nvidia_fit": 0.91,
                    "urgency": 0.83,
                    "rank_score": 0.94,
                    "source_urls": ["https://news.example/clara-ai-funding"],
                    "analysis_text": "Candidata priorizada por LLM a partir do crawling.",
                }
            ],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/runs/discovery",
        json={"query": "IA generativa para saúde", "country": "Brasil", "max_results": 8},
    )

    assert response.status_code == 202
    candidate = response.json()["candidates"][0]
    assert candidate["name"] == "Clara AI"
    assert candidate["rank_score"] == 0.68
    assert candidate["nvidia_fit"] == 0.91
    assert candidate["analysis_text"] == "Candidata priorizada por LLM a partir do crawling."


def test_analyze_url_run_returns_planned_source_document() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/runs/analyze-url",
        json={"url": "https://example.com/blog/ai", "fetch": False},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["run_type"] == "analyze_url"
    assert body["source_document"]["source_type"] == "blog"
    assert body["source_document"]["scrape_status"] == "planned"
    assert body["startup_profile"] is None


def test_analyze_url_run_can_return_extracted_profile(monkeypatch) -> None:
    html = (
        "<html><head><title>MedAI - AI for hospitals</title></head>"
        "<body><p>MedAI automates healthcare workflows with AI agents and LLM copilots.</p>"
        "<p>The platform uses OpenAI APIs for triage automation.</p></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)

    def mock_collect_url(url: str, user_agent: str, client=None):
        from app.collectors.url import collect_url

        return collect_url(url, user_agent, client=client or http_client)

    monkeypatch.setattr("app.analysis.context.collect_url", mock_collect_url)
    monkeypatch.setattr("app.analysis.context.crawl_market_articles", lambda *args, **kwargs: ())

    api_client = TestClient(create_app())
    response = api_client.post(
        "/runs/analyze-url",
        json={"url": "https://medai.example", "fetch": True},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["source_document"]["scrape_status"] == "succeeded"
    assert body["startup_profile"]["name"] == "MedAI"
    assert "healthcare" in body["startup_profile"]["sectors"]
    assert "LLM" in body["startup_profile"]["technology_signals"]
    assert body["startup_profile"]["accepted_claims"]
    assert body["startup_profile"]["review_claims"]

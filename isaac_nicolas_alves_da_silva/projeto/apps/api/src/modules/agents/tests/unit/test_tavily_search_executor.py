"""Testes do executor Tavily usado pelo Search Planner."""

import httpx
import pytest

from apps.api.src.modules.agents.domain.exceptions import AgentSearchExecutionError
from apps.api.src.modules.agents.infrastructure.search_adapters.tavily_search_executor import (
    TavilySearchExecutor,
)


def _client_factory(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_tavily_search_executor_returns_unique_urls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        payload = request.read().decode("utf-8")
        assert "acme founders" in payload
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://acme.example.com/about/",
                        "title": "About",
                        "content": "Founders and company overview",
                        "score": 0.9,
                    },
                    {
                        "url": "https://acme.example.com/about",
                        "title": "Duplicate",
                        "content": "Duplicate",
                        "score": 0.8,
                    },
                    {
                        "url": "https://acme.example.com/team",
                        "title": "Team",
                        "content": "Leadership",
                        "score": 0.7,
                    },
                ]
            },
            request=request,
        )

    executor = TavilySearchExecutor(
        api_key="secret",
        search_url="https://api.tavily.com/search",
        client_factory=lambda: _client_factory(handler),
    )

    result = await executor.search(
        "acme founders",
        excluded_urls=["https://acme.example.com/team"],
    )

    assert result.query == "acme founders"
    assert [item.url for item in result.results] == [
        "https://acme.example.com/about"
    ]
    assert result.results[0].title == "About"
    assert result.results[0].score == 0.9


@pytest.mark.anyio
async def test_tavily_search_executor_raises_for_invalid_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": []}, request=request)

    executor = TavilySearchExecutor(
        api_key="secret",
        search_url="https://api.tavily.com/search",
        client_factory=lambda: _client_factory(handler),
    )

    with pytest.raises(AgentSearchExecutionError):
        await executor.search("acme founders")


def test_tavily_search_executor_requires_api_key() -> None:
    with pytest.raises(ValueError):
        TavilySearchExecutor(api_key="", search_url="https://api.tavily.com/search")

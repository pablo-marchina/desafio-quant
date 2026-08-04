"""Testes unitarios do planejador Gemini via LangChain."""

import pytest
from pydantic import ValidationError

from apps.api.src.modules.agents.application.dto import SearchPlanInput
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_search_planner import (
    LangChainSearchPlanResponse,
    LangChainGeminiSearchPlanner,
)


def make_input(**overrides) -> SearchPlanInput:
    defaults: dict = dict(
        startup_name="Startup XYZ",
        source_url="https://example.com",
        source_title="Startup XYZ",
        raw_text="Texto curto e inconclusivo.",
        reason="Faltam fontes confiaveis.",
        known_terms=["Startup XYZ", "AI"],
        excluded_urls=["https://example.com"],
        max_queries=3,
    )
    defaults.update(overrides)
    return SearchPlanInput(**defaults)


def test_planner_requires_api_key() -> None:
    with pytest.raises(ValueError):
        LangChainGeminiSearchPlanner(api_key="", model="gemini-test")


def test_planner_requires_model() -> None:
    with pytest.raises(ValueError):
        LangChainGeminiSearchPlanner(api_key="fake-key", model="")


def test_build_messages_limits_raw_text() -> None:
    planner = LangChainGeminiSearchPlanner(
        api_key="fake-key",
        model="gemini-test",
        max_text_characters=10,
    )

    messages = planner._build_messages(make_input(raw_text="1234567890ABCDE"))

    assert len(messages) == 2
    assert "Search Planner Agent" in messages[0].content
    assert "1234567890" in messages[1].content
    assert "ABCDE" not in messages[1].content


def test_response_rejects_duplicate_queries() -> None:
    with pytest.raises(ValidationError):
        LangChainSearchPlanResponse.model_validate(
            {
                "queries": [
                    {
                        "query": "Startup XYZ official website",
                        "purpose": "Encontrar fonte oficial.",
                        "priority": 1,
                    },
                    {
                        "query": "startup xyz official website",
                        "purpose": "Duplicada.",
                        "priority": 2,
                    },
                ],
                "reason": "Plano duplicado.",
            }
        )

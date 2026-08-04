"""Testes unitarios do revisor de recomendacoes Gemini via LangChain."""

import pytest

from apps.api.src.modules.agents.application.dto import RecommendationCandidate
from apps.api.src.modules.agents.domain.exceptions import AgentRecommendationError
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_recommendation_reviewer import (
    LangChainGeminiRecommendationReviewResponse,
    LangChainGeminiRecommendationReviewer,
    ReviewedRecommendationItem,
)


class FakeStructuredModel:
    def __init__(self, response: LangChainGeminiRecommendationReviewResponse) -> None:
        self.response = response
        self.received_messages = None

    async def ainvoke(self, messages, config=None):
        self.received_messages = messages
        return self.response


class FailingStructuredModel:
    async def ainvoke(self, messages, config=None):
        raise RuntimeError("Gemini timeout simulado")


def make_candidate(**overrides) -> RecommendationCandidate:
    defaults: dict = dict(
        technology_slug="nvidia-nim",
        technology_name="NVIDIA NIM",
        category="inference",
        score=0.8,
        justification="Evidencias mencionam: llm. NVIDIA NIM e indicada para: model serving.",
        matched_keywords=["llm"],
    )
    defaults.update(overrides)
    return RecommendationCandidate(**defaults)


def test_reviewer_requires_api_key() -> None:
    with pytest.raises(ValueError):
        LangChainGeminiRecommendationReviewer(api_key="", model="gemini-test")


def test_reviewer_requires_model() -> None:
    with pytest.raises(ValueError):
        LangChainGeminiRecommendationReviewer(api_key="fake-key", model="")


@pytest.mark.anyio
async def test_review_returns_empty_list_without_calling_llm() -> None:
    reviewer = LangChainGeminiRecommendationReviewer(
        api_key="fake-key",
        model="gemini-test",
        structured_model=FailingStructuredModel(),
    )

    result = await reviewer.review([])

    assert result == []


@pytest.mark.anyio
async def test_confident_candidate_is_kept_even_if_llm_says_discard() -> None:
    """Guarda em codigo: score >= 0.5 nunca e descartado, mesmo se o LLM disser keep=False."""

    confident = make_candidate(technology_slug="nvidia-nim", score=0.8)
    structured_model = FakeStructuredModel(
        LangChainGeminiRecommendationReviewResponse(
            items=[
                ReviewedRecommendationItem(
                    technology_slug="nvidia-nim",
                    keep=False,
                    business_justification="Tentativa de descarte indevido.",
                )
            ]
        )
    )
    reviewer = LangChainGeminiRecommendationReviewer(
        api_key="fake-key",
        model="gemini-test",
        structured_model=structured_model,
    )

    result = await reviewer.review([confident])

    assert len(result) == 1
    assert result[0].technology_slug == "nvidia-nim"
    assert result[0].justification == "Tentativa de descarte indevido."


@pytest.mark.anyio
async def test_ambiguous_candidate_is_discarded_when_llm_says_discard() -> None:
    ambiguous = make_candidate(technology_slug="cuda", score=0.3)
    structured_model = FakeStructuredModel(
        LangChainGeminiRecommendationReviewResponse(
            items=[
                ReviewedRecommendationItem(
                    technology_slug="cuda",
                    keep=False,
                    business_justification="Match espurio.",
                )
            ]
        )
    )
    reviewer = LangChainGeminiRecommendationReviewer(
        api_key="fake-key",
        model="gemini-test",
        structured_model=structured_model,
    )

    result = await reviewer.review([ambiguous])

    assert result == []


@pytest.mark.anyio
async def test_ambiguous_candidate_is_kept_with_enriched_justification_when_llm_says_keep() -> None:
    ambiguous = make_candidate(technology_slug="cuda", score=0.3)
    structured_model = FakeStructuredModel(
        LangChainGeminiRecommendationReviewResponse(
            items=[
                ReviewedRecommendationItem(
                    technology_slug="cuda",
                    keep=True,
                    business_justification="Match genuino, justificativa de negocio.",
                )
            ]
        )
    )
    reviewer = LangChainGeminiRecommendationReviewer(
        api_key="fake-key",
        model="gemini-test",
        structured_model=structured_model,
    )

    result = await reviewer.review([ambiguous])

    assert len(result) == 1
    assert result[0].justification == "Match genuino, justificativa de negocio."


@pytest.mark.anyio
async def test_candidate_missing_from_llm_response_is_kept_unchanged() -> None:
    candidate = make_candidate(technology_slug="cuda", score=0.3)
    structured_model = FakeStructuredModel(
        LangChainGeminiRecommendationReviewResponse(items=[])
    )
    reviewer = LangChainGeminiRecommendationReviewer(
        api_key="fake-key",
        model="gemini-test",
        structured_model=structured_model,
    )

    result = await reviewer.review([candidate])

    assert result == [candidate]


@pytest.mark.anyio
async def test_review_wraps_llm_failure() -> None:
    reviewer = LangChainGeminiRecommendationReviewer(
        api_key="fake-key",
        model="gemini-test",
        structured_model=FailingStructuredModel(),
    )

    with pytest.raises(AgentRecommendationError):
        await reviewer.review([make_candidate()])


def test_build_messages_includes_all_candidates() -> None:
    reviewer = LangChainGeminiRecommendationReviewer(
        api_key="fake-key",
        model="gemini-test",
        structured_model=FakeStructuredModel(
            LangChainGeminiRecommendationReviewResponse(items=[])
        ),
    )

    messages = reviewer._build_messages(
        [
            make_candidate(technology_slug="nvidia-nim", score=0.8),
            make_candidate(technology_slug="cuda", score=0.3),
        ]
    )

    assert len(messages) == 2
    assert "Recommendation Agent" in messages[0].content
    assert "nvidia-nim" in messages[1].content
    assert "cuda" in messages[1].content

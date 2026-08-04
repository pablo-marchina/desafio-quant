"""Testes da V11 do Recommendation Agent com LangGraph."""

from uuid import uuid4

import pytest

from apps.api.src.modules.agents.application.dto import (
    RecommendationAgentInput,
    RecommendationCandidate,
)
from apps.api.src.modules.agents.application.ports import (
    RecommendationReviewerPort,
    RecommendationToolPort,
)
from apps.api.src.modules.agents.graphs.recommendation.graph import (
    RecommendationAgentGraph,
)


class FakeRecommendationTool(RecommendationToolPort):
    def __init__(self, candidates: list[RecommendationCandidate]) -> None:
        self.candidates = candidates
        self.received_startup_id = None
        self.update_calls: list[tuple] = []

    async def generate(self, startup_id):
        self.received_startup_id = startup_id
        return self.candidates

    async def update_justifications(self, startup_id, justifications):
        self.update_calls.append((startup_id, justifications))


class FakeReviewer(RecommendationReviewerPort):
    def __init__(self, reviewed: list[RecommendationCandidate]) -> None:
        self.reviewed = reviewed
        self.received_candidates = None
        self.call_count = 0

    async def review(self, candidates):
        self.call_count += 1
        self.received_candidates = candidates
        return self.reviewed


def make_candidate(**overrides) -> RecommendationCandidate:
    defaults: dict = dict(
        technology_slug="nvidia-nim",
        technology_name="NVIDIA NIM",
        category="inference",
        score=0.8,
        justification="Justificativa tecnica.",
        matched_keywords=["llm"],
    )
    defaults.update(overrides)
    return RecommendationCandidate(**defaults)


@pytest.mark.anyio
async def test_graph_returns_reviewed_recommendations() -> None:
    candidate = make_candidate()
    reviewed_candidate = make_candidate(justification="Justificativa de negocio.")
    tool = FakeRecommendationTool([candidate])
    reviewer = FakeReviewer([reviewed_candidate])
    graph = RecommendationAgentGraph(recommendation_tool=tool, reviewer=reviewer)
    startup_id = uuid4()

    result = await graph.recommend(RecommendationAgentInput(startup_id=startup_id))

    assert tool.received_startup_id == startup_id
    assert reviewer.received_candidates == [candidate]
    assert result.recommendations == [reviewed_candidate]
    assert tool.update_calls == [
        (startup_id, {"nvidia-nim": "Justificativa de negocio."})
    ]


@pytest.mark.anyio
async def test_graph_skips_reviewer_when_no_candidates() -> None:
    tool = FakeRecommendationTool([])
    reviewer = FakeReviewer([])
    graph = RecommendationAgentGraph(recommendation_tool=tool, reviewer=reviewer)

    result = await graph.recommend(RecommendationAgentInput(startup_id=uuid4()))

    assert result.recommendations == []
    assert reviewer.call_count == 0
    assert tool.update_calls == []

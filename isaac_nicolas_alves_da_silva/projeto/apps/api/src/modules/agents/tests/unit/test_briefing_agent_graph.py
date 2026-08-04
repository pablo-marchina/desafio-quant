"""Testes da V12 do Briefing Agent com LangGraph."""

from uuid import uuid4

import pytest

from apps.api.src.modules.agents.application.dto import BriefingAgentInput
from apps.api.src.modules.agents.application.ports import (
    BriefingProseRewriterPort,
    BriefingToolPort,
)
from apps.api.src.modules.agents.graphs.briefing.graph import BriefingAgentGraph


class FakeBriefingTool(BriefingToolPort):
    def __init__(self, content: str) -> None:
        self.content = content
        self.received_startup_id = None
        self.update_calls: list[tuple] = []
        self.briefing_id = uuid4()

    async def generate(self, startup_id):
        self.received_startup_id = startup_id
        return self.content

    async def update_content(self, startup_id, content):
        self.update_calls.append((startup_id, content))
        return self.briefing_id


class FakeProseRewriter(BriefingProseRewriterPort):
    def __init__(self, rewritten: str) -> None:
        self.rewritten = rewritten
        self.received_content = None
        self.call_count = 0

    async def rewrite(self, content):
        self.call_count += 1
        self.received_content = content
        return self.rewritten


@pytest.mark.anyio
async def test_graph_returns_rewritten_content() -> None:
    deterministic = "# Briefing Executivo — Acme AI\n"
    rewritten = "# Briefing Executivo — Acme AI (revisado)\n"
    tool = FakeBriefingTool(deterministic)
    rewriter = FakeProseRewriter(rewritten)
    graph = BriefingAgentGraph(briefing_tool=tool, prose_rewriter=rewriter)
    startup_id = uuid4()

    result = await graph.generate(BriefingAgentInput(startup_id=startup_id))

    assert tool.received_startup_id == startup_id
    assert rewriter.received_content == deterministic
    assert rewriter.call_count == 1
    assert result.content == rewritten
    assert result.briefing_id == tool.briefing_id
    assert tool.update_calls == [(startup_id, rewritten)]

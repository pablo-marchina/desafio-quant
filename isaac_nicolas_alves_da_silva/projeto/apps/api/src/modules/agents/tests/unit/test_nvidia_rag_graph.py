"""Testes da V10 do NVIDIA RAG Agent com LangGraph."""

import pytest

from apps.api.src.modules.agents.application.dto import (
    NvidiaRagCitation,
    NvidiaRagInput,
    NvidiaRagResult,
)
from apps.api.src.modules.agents.application.ports import NvidiaRagToolPort
from apps.api.src.modules.agents.graphs.nvidia_rag.graph import NvidiaRagGraph


class FakeRagTool(NvidiaRagToolPort):
    """Tool falsa para testar o grafo sem chamar o modulo rag real."""

    def __init__(self, result: NvidiaRagResult) -> None:
        self.result = result
        self.received_query: str | None = None
        self.received_limit: int | None = None

    async def answer(self, query: str, *, limit: int = 5) -> NvidiaRagResult:
        self.received_query = query
        self.received_limit = limit
        return self.result


@pytest.mark.anyio
async def test_graph_returns_nvidia_rag_result() -> None:
    expected = NvidiaRagResult(
        answer="NIM e um microservico de inferencia da NVIDIA.",
        citations=[
            NvidiaRagCitation(
                source_url="https://docs.nvidia.com/nim/",
                quote="NIM e um microservico de inferencia.",
            )
        ],
    )
    fake_tool = FakeRagTool(expected)
    graph = NvidiaRagGraph(rag_tool=fake_tool)
    rag_input = NvidiaRagInput(query="O que e NIM?", limit=3)

    result = await graph.answer(rag_input)

    assert result == expected
    assert fake_tool.received_query == "O que e NIM?"
    assert fake_tool.received_limit == 3


@pytest.mark.anyio
async def test_graph_uses_default_limit() -> None:
    expected = NvidiaRagResult(answer="Sem citacoes.", citations=[])
    fake_tool = FakeRagTool(expected)
    graph = NvidiaRagGraph(rag_tool=fake_tool)

    result = await graph.answer(NvidiaRagInput(query="O que e Triton?"))

    assert result == expected
    assert fake_tool.received_limit == 5

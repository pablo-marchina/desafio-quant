"""Testes da V8 do Extraction Agent com LangGraph."""

import pytest

from apps.api.src.modules.agents.application.dto import (
    ExtractionInput,
    ExtractionResult,
)
from apps.api.src.modules.agents.application.public.extractor import (
    ExtractionService,
)
from apps.api.src.modules.agents.domain.enums import ExtractedFundingStage
from apps.api.src.modules.agents.graphs.extraction.graph import ExtractionGraph


class FakeExtractor(ExtractionService):
    """Extrator falso para testar o grafo sem chamar LLM real."""

    def __init__(self, result: ExtractionResult) -> None:
        self.result = result
        self.received_input: ExtractionInput | None = None

    async def extract(
        self, extraction_input: ExtractionInput
    ) -> ExtractionResult:
        self.received_input = extraction_input
        return self.result


def make_input(**overrides) -> ExtractionInput:
    defaults: dict = dict(
        name="Acme AI",
        sector="LLM customer service",
        description="Plataforma de atendimento com LLM proprietario.",
        evidence_texts=[
            "Acme foi fundada por Ana Silva e levantou USD 2M em Series A.",
        ],
    )
    defaults.update(overrides)
    return ExtractionInput(**defaults)


@pytest.mark.anyio
async def test_graph_returns_extraction_result() -> None:
    expected = ExtractionResult(
        founders=["Ana Silva"],
        funding_stage=ExtractedFundingStage.SERIES_A,
        funding_amount_usd=2_000_000.0,
        customers=[],
    )
    fake_extractor = FakeExtractor(expected)
    graph = ExtractionGraph(extractor=fake_extractor)
    extraction_input = make_input()

    result = await graph.extract(extraction_input)

    assert result == expected
    assert fake_extractor.received_input == extraction_input


@pytest.mark.anyio
async def test_graph_returns_sector_and_description_in_english() -> None:
    expected = ExtractionResult(
        founders=[],
        funding_stage=ExtractedFundingStage.UNKNOWN,
        funding_amount_usd=None,
        customers=[],
        sector="Data Analytics",
        description="Data platform with an AI agent for natural language queries.",
    )
    graph = ExtractionGraph(extractor=FakeExtractor(expected))

    result = await graph.extract(make_input())

    assert result.sector == "Data Analytics"
    assert result.description == (
        "Data platform with an AI agent for natural language queries."
    )


@pytest.mark.anyio
async def test_graph_preserves_unknown_funding_when_not_mentioned() -> None:
    expected = ExtractionResult(
        founders=[],
        funding_stage=ExtractedFundingStage.UNKNOWN,
        funding_amount_usd=None,
        customers=[],
    )
    graph = ExtractionGraph(extractor=FakeExtractor(expected))

    result = await graph.extract(make_input(evidence_texts=[]))

    assert result.funding_stage is ExtractedFundingStage.UNKNOWN
    assert result.founders == []

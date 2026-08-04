"""Testes da V9 do Startup Classifier Agent com LangGraph."""

import pytest

from apps.api.src.modules.agents.application.dto import (
    StartupClassificationInput,
    StartupClassificationResult,
)
from apps.api.src.modules.agents.application.public.startup_classifier import (
    StartupClassifierService,
)
from apps.api.src.modules.agents.domain.enums import StartupMaturityLevel
from apps.api.src.modules.agents.graphs.startup_classification.graph import (
    StartupClassificationGraph,
)


class FakeClassifier(StartupClassifierService):
    """Classificador falso para testar o grafo sem chamar LLM real."""

    def __init__(self, result: StartupClassificationResult) -> None:
        self.result = result
        self.received_input: StartupClassificationInput | None = None

    async def classify(
        self, classification_input: StartupClassificationInput
    ) -> StartupClassificationResult:
        self.received_input = classification_input
        return self.result


def make_input(**overrides) -> StartupClassificationInput:
    defaults: dict = dict(
        name="Acme AI",
        sector="LLM customer service",
        description="Plataforma de atendimento com LLM proprietario.",
        country="BR",
        website_url="https://acme.example.com",
        evidence_texts=["Acme treina modelos proprios de LLM para atendimento."],
    )
    defaults.update(overrides)
    return StartupClassificationInput(**defaults)


@pytest.mark.anyio
async def test_graph_returns_classification_result() -> None:
    expected = StartupClassificationResult(
        level=StartupMaturityLevel.AI_NATIVE,
        reason="Modelos proprios de LLM no core do produto.",
    )
    fake_classifier = FakeClassifier(expected)
    graph = StartupClassificationGraph(classifier=fake_classifier)
    classification_input = make_input()

    result = await graph.classify(classification_input)

    assert result == expected
    assert fake_classifier.received_input == classification_input


@pytest.mark.anyio
async def test_graph_preserves_non_ai_classification() -> None:
    expected = StartupClassificationResult(
        level=StartupMaturityLevel.NON_AI,
        reason="Nenhuma evidencia de uso de IA encontrada.",
    )
    graph = StartupClassificationGraph(classifier=FakeClassifier(expected))

    result = await graph.classify(make_input(evidence_texts=[]))

    assert result.level is StartupMaturityLevel.NON_AI

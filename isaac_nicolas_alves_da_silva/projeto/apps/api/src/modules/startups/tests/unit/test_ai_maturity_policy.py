"""Calibracao TAP para AI-native, AI-enabled e non-AI."""

import pytest

from apps.api.src.modules.startups.domain.enums import AiMaturityLevel
from apps.api.src.modules.startups.domain.policies import calibrate_ai_maturity_level


@pytest.mark.parametrize(
    "name,evidence",
    [
        (
            "Mistral",
            "Frontier AI lab building large language models, agents, training and inference infrastructure.",
        ),
        (
            "Runway",
            "Generative video platform building AI models for video generation and world simulation.",
        ),
        (
            "ModeloBR",
            "A empresa treina modelos proprios, faz pre-treino em portugues e oferece document analysis via API.",
        ),
        (
            "Pesquisa Neural",
            "DeepTech que desenvolve modelos de IA com transformer, fine-tuning e redes neurais proprietarias.",
        ),
        (
            "VisionLab",
            "Computer vision company using reinforcement learning and neural network research in production.",
        ),
    ],
)
def test_tap_keeps_core_ai_companies_as_ai_native(name: str, evidence: str) -> None:
    level, _ = calibrate_ai_maturity_level(
        level=AiMaturityLevel.AI_NATIVE,
        reason="IA e o produto central.",
        name=name,
        sector=None,
        description=None,
        website_url=None,
        evidence_texts=[evidence],
    )

    assert level is AiMaturityLevel.AI_NATIVE


@pytest.mark.parametrize(
    "name,evidence",
    [
        ("Notion AI", "Workspace with docs, meetings, project management and AI agents."),
        ("Grammarly", "Grammar and spelling assistant with AI suggestions."),
        ("Canva AI", "Design tool with AI features for presentations."),
    ],
)
def test_tap_downgrades_productivity_layers_to_ai_enabled(
    name: str, evidence: str
) -> None:
    level, reason = calibrate_ai_maturity_level(
        level=AiMaturityLevel.AI_NATIVE,
        reason="O texto fala bastante de AI.",
        name=name,
        sector=None,
        description=None,
        website_url=None,
        evidence_texts=[evidence],
    )

    assert level is AiMaturityLevel.AI_ENABLED
    assert "regua do TAP" in reason


def test_tap_keeps_non_ai_without_ai_signal() -> None:
    level, _ = calibrate_ai_maturity_level(
        level=AiMaturityLevel.NON_AI,
        reason="Marca de beleza sem sinal de IA.",
        name="Glossier",
        sector="Beauty",
        description=None,
        website_url="https://www.glossier.com/",
        evidence_texts=["Beauty ecommerce brand focused on skincare and makeup."],
    )

    assert level is AiMaturityLevel.NON_AI


def test_tap_upgrades_non_ai_to_ai_enabled_when_ai_layer_is_explicit() -> None:
    level, _ = calibrate_ai_maturity_level(
        level=AiMaturityLevel.NON_AI,
        reason="Classificacao inicial conservadora.",
        name="Canva",
        sector="Design",
        description=None,
        website_url="https://www.canva.com/",
        evidence_texts=["Design platform with AI assistant and generative design tools."],
    )

    assert level is AiMaturityLevel.AI_ENABLED

"""Testes unitarios do avaliador Gemini via LangChain."""

import pytest

from apps.api.src.modules.agents.application.dto import EvidenceValidationInput
from apps.api.src.modules.agents.infrastructure.llm.langchain_gemini_evidence_judge import (
    LangChainGeminiEvidenceJudge,
)


def make_input(**overrides) -> EvidenceValidationInput:
    defaults: dict = dict(
        url="https://example.com",
        title="Startup XYZ",
        raw_text="A Startup XYZ usa IA generativa para atendimento.",
        technical_score=0.90,
        text_score=0.80,
        evidence_score=0.30,
        quality_score=0.66,
    )
    defaults.update(overrides)
    return EvidenceValidationInput(**defaults)


def test_judge_requires_api_key() -> None:
    with pytest.raises(ValueError):
        LangChainGeminiEvidenceJudge(api_key="", model="gemini-test")


def test_judge_requires_model() -> None:
    with pytest.raises(ValueError):
        LangChainGeminiEvidenceJudge(api_key="fake-key", model="")


def test_build_messages_limits_raw_text() -> None:
    judge = LangChainGeminiEvidenceJudge(
        api_key="fake-key",
        model="gemini-test",
        max_text_characters=10,
    )

    messages = judge._build_messages(make_input(raw_text="1234567890ABCDE"))

    assert len(messages) == 2
    assert "Evidence Validation Agent" in messages[0].content
    assert "1234567890" in messages[1].content
    assert "ABCDE" not in messages[1].content

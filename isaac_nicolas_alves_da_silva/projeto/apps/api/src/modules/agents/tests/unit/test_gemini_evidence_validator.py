"""Testes unitários do adaptador Gemini do Evidence Validation Agent (v8)."""

import json

import pytest

from apps.api.src.modules.agents.application.dto import EvidenceValidationInput
from apps.api.src.modules.agents.domain.enums import AgentDecision
from apps.api.src.modules.agents.domain.exceptions import AgentInvestigationError
from apps.api.src.modules.agents.infrastructure.llm.gemini_evidence_validator import (
    GeminiEvidenceValidator,
)


class FakeResponse:
    """Resposta HTTP mínima usada para simular o cliente Gemini."""

    def __init__(self, payload: dict, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    """Cliente assíncrono falso usado como ``client_factory``."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.last_request: dict | None = None

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    async def post(self, url: str, *, headers: dict, json: dict) -> FakeResponse:
        self.last_request = {"url": url, "headers": headers, "json": json}
        return self.response


def make_input(**overrides) -> EvidenceValidationInput:
    """Cria um ``EvidenceValidationInput`` válido com defaults sensatos."""

    defaults: dict = dict(
        url="https://example.com",
        title="Startup XYZ",
        raw_text="A Startup XYZ usa modelos de visão computacional...",
        technical_score=0.90,
        text_score=0.80,
        evidence_score=0.20,
        quality_score=0.59,
    )
    defaults.update(overrides)
    return EvidenceValidationInput(**defaults)


def make_validator(response: FakeResponse) -> tuple[GeminiEvidenceValidator, FakeAsyncClient]:
    fake_client = FakeAsyncClient(response)

    validator = GeminiEvidenceValidator(
        api_key="fake-key",
        model="gemini-test",
        client_factory=lambda: fake_client,
    )
    return validator, fake_client


def gemini_payload(decision: str, reason: str) -> dict:
    """Monta o formato de resposta real da API do Gemini."""

    body = json.dumps({"decision": decision, "reason": reason})
    return {
        "candidates": [
            {"content": {"parts": [{"text": body}]}},
        ]
    }


def test_validator_requires_api_key() -> None:
    with pytest.raises(ValueError):
        GeminiEvidenceValidator(api_key="", model="gemini-test")


def test_validator_requires_model() -> None:
    with pytest.raises(ValueError):
        GeminiEvidenceValidator(api_key="fake-key", model="")


@pytest.mark.anyio
async def test_investigate_returns_accepted_decision() -> None:
    response = FakeResponse(
        gemini_payload("accepted", "Evidências suficientes encontradas.")
    )
    validator, fake_client = make_validator(response)

    result = await validator.investigate(make_input())

    assert result.decision is AgentDecision.ACCEPTED
    assert result.reason == "Evidências suficientes encontradas."
    assert fake_client.last_request is not None
    assert "gemini-test" in fake_client.last_request["url"]


@pytest.mark.anyio
async def test_investigate_returns_needs_more_sources_decision() -> None:
    response = FakeResponse(
        gemini_payload("needs_more_sources", "Faltam fontes adicionais.")
    )
    validator, _ = make_validator(response)

    result = await validator.investigate(make_input())

    assert result.decision is AgentDecision.NEEDS_MORE_SOURCES
    assert result.reason == "Faltam fontes adicionais."


@pytest.mark.anyio
async def test_investigate_raises_on_malformed_response() -> None:
    response = FakeResponse({"candidates": []})
    validator, _ = make_validator(response)

    with pytest.raises(AgentInvestigationError):
        await validator.investigate(make_input())


@pytest.mark.anyio
async def test_investigate_raises_on_invalid_decision_value() -> None:
    response = FakeResponse(gemini_payload("maybe", "Resposta fora do esperado."))
    validator, _ = make_validator(response)

    with pytest.raises(AgentInvestigationError):
        await validator.investigate(make_input())

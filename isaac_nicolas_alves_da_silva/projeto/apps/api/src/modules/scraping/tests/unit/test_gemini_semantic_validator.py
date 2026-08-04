"""Testes do adaptador Gemini para validacao semantica estruturada."""

import json

import httpx
import pytest

from apps.api.src.modules.scraping.application.dto import (
    DeterministicValidationResult,
    SemanticValidationInput,
)
from apps.api.src.modules.scraping.domain.enums import SemanticReviewDecision
from apps.api.src.modules.scraping.domain.exceptions import SemanticValidationError
from apps.api.src.modules.scraping.infrastructure.semantic_validators.gemini_semantic_validator import (
    GeminiSemanticValidator,
)


def make_input(raw_text: str = "Conteudo ambiguo sobre uma plataforma.") -> SemanticValidationInput:
    return SemanticValidationInput(
        url="https://example.com",
        title="Startup",
        raw_text=raw_text,
        deterministic=DeterministicValidationResult(
            technical_score=1.0,
            text_score=0.80,
            evidence_score=0.30,
            quality_score=0.62,
            warnings={"no_capability_description"},
        ),
    )


def make_client_factory(handler):
    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    return factory


def valid_semantic_json() -> str:
    return json.dumps(
        {
            "startup_match_score": 0.90,
            "evidence_clarity_score": 0.80,
            "source_reliability_score": 0.70,
            "statement_specificity_score": 0.60,
            "context_completeness_score": 0.50,
            "contradiction_detected": False,
            "decision": "accepted",
            "reason": "O texto descreve um produto de IA.",
        }
    )


@pytest.mark.anyio
async def test_sends_structured_request_and_maps_valid_response() -> None:
    captured_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": valid_semantic_json()}]}}
                ]
            },
        )

    validator = GeminiSemanticValidator(
        api_key="secret",
        model="gemini-test",
        client_factory=make_client_factory(handler),
    )

    assessment = await validator.validate(make_input())

    assert assessment.decision is SemanticReviewDecision.ACCEPTED
    assert assessment.startup_match_score == 0.90
    assert captured_request.headers["x-goog-api-key"] == "secret"
    assert captured_request.url.path.endswith("/gemini-test:generateContent")

    body = json.loads(captured_request.content)
    generation_config = body["generationConfig"]
    assert generation_config["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in generation_config
    assert body["generationConfig"]["temperature"] == 0


@pytest.mark.anyio
async def test_limits_text_sent_to_gemini() -> None:
    captured_body = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": valid_semantic_json()}]}}
                ]
            },
        )

    validator = GeminiSemanticValidator(
        api_key="secret",
        model="gemini-test",
        max_text_characters=10,
        client_factory=make_client_factory(handler),
    )

    await validator.validate(make_input(raw_text="A" * 100))

    prompt = captured_body["contents"][0]["parts"][0]["text"]
    assert "A" * 10 in prompt
    assert "A" * 11 not in prompt


@pytest.mark.anyio
async def test_rejects_invalid_structured_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"decision": "accepted"}'}]}}
                ]
            },
        )

    validator = GeminiSemanticValidator(
        api_key="secret",
        model="gemini-test",
        client_factory=make_client_factory(handler),
    )

    with pytest.raises(SemanticValidationError, match="invalida"):
        await validator.validate(make_input())


@pytest.mark.anyio
async def test_translates_timeout_to_known_error() -> None:
    # Com max_retries=1 o timeout não é retentado — falha imediatamente.
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append("call")
        raise httpx.ReadTimeout("timeout", request=request)

    validator = GeminiSemanticValidator(
        api_key="secret",
        model="gemini-test",
        timeout_seconds=2,
        max_retries=1,
        client_factory=make_client_factory(handler),
        sleep_fn=_no_sleep,
    )

    with pytest.raises(SemanticValidationError, match="indisponivel"):
        await validator.validate(make_input())

    assert len(calls) == 1


# ---------------------------------------------------------------------------
# Testes de retry / backoff (P0b)
# ---------------------------------------------------------------------------

async def _no_sleep(_: float) -> None:
    """Substitui asyncio.sleep nos testes para não bloquear."""


def _make_503_handler(then_ok: bool = True):
    """Retorna um handler que responde 503 nas primeiras chamadas e 200 depois.

    Se ``then_ok=False``, sempre responde 503 (para testar esgotamento).
    """
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3 and then_ok:
            return httpx.Response(503, text="Service Unavailable")
        if not then_ok:
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": valid_semantic_json()}]}}
                ]
            },
        )

    return handler, calls


@pytest.mark.anyio
async def test_retries_on_503_and_succeeds_on_third_attempt() -> None:
    handler, calls = _make_503_handler(then_ok=True)
    validator = GeminiSemanticValidator(
        api_key="secret",
        model="gemini-test",
        max_retries=3,
        client_factory=make_client_factory(handler),
        sleep_fn=_no_sleep,
    )

    assessment = await validator.validate(make_input())

    assert assessment.decision is SemanticReviewDecision.ACCEPTED
    assert calls["count"] == 3, f"Esperava 3 chamadas (2×503 + 1 ok), got {calls['count']}"


@pytest.mark.anyio
async def test_raises_semantic_error_after_all_retries_exhausted() -> None:
    handler, calls = _make_503_handler(then_ok=False)
    validator = GeminiSemanticValidator(
        api_key="secret",
        model="gemini-test",
        max_retries=3,
        client_factory=make_client_factory(handler),
        sleep_fn=_no_sleep,
    )

    with pytest.raises(SemanticValidationError, match="indisponivel"):
        await validator.validate(make_input())

    assert calls["count"] == 3


@pytest.mark.anyio
async def test_retries_on_timeout_and_succeeds() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": valid_semantic_json()}]}}]},
        )

    validator = GeminiSemanticValidator(
        api_key="secret",
        model="gemini-test",
        max_retries=3,
        client_factory=make_client_factory(handler),
        sleep_fn=_no_sleep,
    )

    assessment = await validator.validate(make_input())
    assert assessment.decision is SemanticReviewDecision.ACCEPTED
    assert calls["count"] == 2


@pytest.mark.anyio
async def test_no_retry_on_non_transient_http_error() -> None:
    """Erros 4xx não transitórios (ex: 401 Unauthorized) não devem ser retentados."""
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401, text="Unauthorized")

    validator = GeminiSemanticValidator(
        api_key="bad-key",
        model="gemini-test",
        max_retries=3,
        client_factory=make_client_factory(handler),
        sleep_fn=_no_sleep,
    )

    with pytest.raises(SemanticValidationError, match="nao conseguiu"):
        await validator.validate(make_input())

    assert calls["count"] == 1, "Erro 401 não deve gerar retry"


@pytest.mark.anyio
async def test_backoff_sleep_is_called_between_retries() -> None:
    """Verifica que o sleep é chamado com os delays corretos (1 s, 2 s)."""
    sleep_calls: list[float] = []

    async def recording_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="overload")

    validator = GeminiSemanticValidator(
        api_key="secret",
        model="gemini-test",
        max_retries=3,
        client_factory=make_client_factory(handler),
        sleep_fn=recording_sleep,
    )

    with pytest.raises(SemanticValidationError):
        await validator.validate(make_input())

    assert sleep_calls == [1.0, 2.0], f"Backoff errado: {sleep_calls}"

"""Validacao semantica estruturada usando a API REST do Gemini."""

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apps.api.src.modules.scraping.application.dto import (
    SemanticAssessment,
    SemanticValidationInput,
)
from apps.api.src.modules.scraping.application.ports import SemanticValidator
from apps.api.src.modules.scraping.domain.enums import SemanticReviewDecision
from apps.api.src.modules.scraping.domain.exceptions import SemanticValidationError

# Códigos HTTP que indicam sobrecarga ou instabilidade temporária do Gemini —
# tratados como transitórios: vale tentar de novo antes de desistir.
_TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({429, 500, 503, 504})

SleepFn = Callable[[float], Coroutine[Any, Any, None]]


class GeminiSemanticResponse(BaseModel):
    """Formato exato que o Gemini deve devolver."""

    model_config = ConfigDict(extra="forbid")

    startup_match_score: float = Field(ge=0.0, le=1.0)
    evidence_clarity_score: float = Field(ge=0.0, le=1.0)
    source_reliability_score: float = Field(ge=0.0, le=1.0)
    statement_specificity_score: float = Field(ge=0.0, le=1.0)
    context_completeness_score: float = Field(ge=0.0, le=1.0)
    contradiction_detected: bool
    decision: SemanticReviewDecision
    reason: str = Field(min_length=1, max_length=1000)


GeminiClientFactory = Callable[[], httpx.AsyncClient]


class GeminiSemanticValidator(SemanticValidator):
    """Interpreta apenas o conteudo atual, sem navegar ou buscar novas fontes."""

    api_base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_text_characters: int = 20_000,
        max_retries: int = 3,
        client_factory: GeminiClientFactory | None = None,
        sleep_fn: SleepFn | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY e obrigatoria.")
        if not model:
            raise ValueError("GEMINI_MODEL e obrigatorio.")

        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_text_characters = max_text_characters
        self.max_retries = max_retries
        self.client_factory = client_factory or self._create_default_client
        self._sleep = sleep_fn or asyncio.sleep

    def _create_default_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout_seconds)

    async def validate(
        self,
        semantic_input: SemanticValidationInput,
    ) -> SemanticAssessment:
        """Chama Gemini com retry exponencial para erros transitórios.

        503/429/500/504 e TimeoutException são retentadas até max_retries
        (backoff: 1 s, 2 s, 4 s, …). Erros permanentes (4xx não transitórios,
        resposta malformada) levantam SemanticValidationError imediatamente.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            if attempt > 0:
                await self._sleep(2 ** (attempt - 1))

            try:
                async with self.client_factory() as client:
                    response = await client.post(
                        f"{self.api_base_url}/{self.model}:generateContent",
                        headers={
                            "x-goog-api-key": self.api_key,
                            "Content-Type": "application/json",
                        },
                        json=self._build_request(semantic_input),
                    )

                if response.status_code in _TRANSIENT_STATUS_CODES:
                    last_error = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    continue

                response.raise_for_status()

            except httpx.TimeoutException as error:
                last_error = error
                continue
            except httpx.HTTPError as error:
                raise SemanticValidationError(
                    f"Gemini nao conseguiu concluir a validacao: {error}."
                ) from error

            try:
                content = response.json()
                text = content["candidates"][0]["content"]["parts"][0]["text"]
                parsed = GeminiSemanticResponse.model_validate_json(text)
            except (
                json.JSONDecodeError,
                KeyError,
                IndexError,
                TypeError,
                ValidationError,
            ) as error:
                raise SemanticValidationError(
                    "Gemini devolveu uma resposta semantica invalida."
                ) from error

            return SemanticAssessment(
                startup_match_score=parsed.startup_match_score,
                evidence_clarity_score=parsed.evidence_clarity_score,
                source_reliability_score=parsed.source_reliability_score,
                statement_specificity_score=parsed.statement_specificity_score,
                context_completeness_score=parsed.context_completeness_score,
                contradiction_detected=parsed.contradiction_detected,
                decision=parsed.decision,
                reason=parsed.reason,
            )

        raise SemanticValidationError(
            f"Gemini indisponivel apos {self.max_retries} tentativas."
        ) from last_error

    def _build_request(self, semantic_input: SemanticValidationInput) -> dict:
        """Monta prompt e schema sem incluir HTML ou contexto desnecessario."""

        text = semantic_input.raw_text[: self.max_text_characters]
        prompt = (
            "Avalie semanticamente o conteudo para o AI Venture Radar. "
            "Determine se ele apresenta evidencia util e especifica sobre uma "
            "startup ou produto que usa inteligencia artificial. Nao invente "
            "informacoes e sinalize contradicoes. Use somente o texto fornecido.\n\n"
            f"URL: {semantic_input.url}\n"
            f"Titulo: {semantic_input.title or 'ausente'}\n"
            f"Quality score: {semantic_input.deterministic.quality_score}\n"
            f"Warnings: {sorted(semantic_input.deterministic.warnings)}\n\n"
            f"Conteudo:\n{text}"
        )

        return {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": GeminiSemanticResponse.model_json_schema(),
            },
        }

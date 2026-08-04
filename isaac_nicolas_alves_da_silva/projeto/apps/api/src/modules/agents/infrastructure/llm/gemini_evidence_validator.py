"""Implementacao v1 do Evidence Validation Agent usando Gemini.

Esta e a primeira implementacao concreta do contrato publico
``EvidenceValidationService``. Ela faz UMA chamada estruturada ao Gemini,
pedindo para a LLM reavaliar o caso com mais contexto (incluindo o resultado
da revisao semantica simples que ja rodou) e decidir entre
``accepted`` / ``rejected`` / ``needs_more_sources``.

Isso ja cumpre o contrato e desbloqueia a integracao ponta a ponta com o
``scraping`` (v8). A versao com grafo LangGraph real
(``graphs/evidence_validation/``), capaz de buscar novas fontes, consultar o
RAG e comparar documentos, e um passo evolutivo posterior — descrito em
``docs/agents/modulo_agents_arquitetura.md`` — e pode substituir esta classe
sem que ``scraping`` precise mudar (o contrato publico continua o mesmo).
"""

import json
from collections.abc import Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apps.api.src.modules.agents.application.dto import (
    EvidenceValidationInput,
    EvidenceValidationResult,
)
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.agents.domain.enums import AgentDecision
from apps.api.src.modules.agents.domain.exceptions import AgentInvestigationError


class GeminiEvidenceResponse(BaseModel):
    """Formato exato que o Gemini deve devolver para esta investigacao."""

    model_config = ConfigDict(extra="forbid")

    decision: AgentDecision
    reason: str = Field(min_length=1, max_length=1000)


GeminiClientFactory = Callable[[], httpx.AsyncClient]


class GeminiEvidenceValidator(EvidenceValidationService):
    """Reavalia o caso com Gemini quando a revisao semantica simples falhou."""

    api_base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_text_characters: int = 20_000,
        client_factory: GeminiClientFactory | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY e obrigatoria.")
        if not model:
            raise ValueError("GEMINI_MODEL e obrigatorio.")

        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_text_characters = max_text_characters
        self.client_factory = client_factory or self._create_default_client

    def _create_default_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout_seconds)

    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
    ) -> EvidenceValidationResult:
        """Chama Gemini e converte a resposta validada para o DTO publico."""

        try:
            async with self.client_factory() as client:
                response = await client.post(
                    f"{self.api_base_url}/{self.model}:generateContent",
                    headers={
                        "x-goog-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json=self._build_request(investigation_input),
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise AgentInvestigationError(
                f"Gemini excedeu o timeout de {self.timeout_seconds}s "
                "durante a investigacao."
            ) from error
        except httpx.HTTPError as error:
            raise AgentInvestigationError(
                f"Gemini nao conseguiu concluir a investigacao: {error}."
            ) from error

        try:
            content = response.json()
            text = content["candidates"][0]["content"]["parts"][0]["text"]
            parsed = GeminiEvidenceResponse.model_validate_json(text)
        except (
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
            ValidationError,
        ) as error:
            raise AgentInvestigationError(
                "Gemini devolveu uma resposta de investigacao invalida."
            ) from error

        return EvidenceValidationResult(
            decision=parsed.decision,
            reason=parsed.reason,
        )

    def _build_request(self, investigation_input: EvidenceValidationInput) -> dict:
        """Monta um prompt com o contexto acumulado pela pipeline."""

        text = investigation_input.raw_text[: self.max_text_characters]
        prompt = (
            "Voce e um investigador de evidencias do AI Venture Radar. Uma "
            "primeira revisao semantica nao teve confianca suficiente ou "
            "encontrou possiveis contradicoes. Reavalie o caso com mais "
            "cuidado e decida: 'accepted' (o conteudo e util e confiavel), "
            "'rejected' (o conteudo nao deve ser usado) ou "
            "'needs_more_sources' (nao ha evidencias suficientes nesta unica "
            "pagina para decidir; seria necessario coletar outras fontes). "
            "Nao invente informacoes. Use somente o que foi fornecido.\n\n"
            f"URL: {investigation_input.url}\n"
            f"Titulo: {investigation_input.title or 'ausente'}\n\n"
            "--- Scores deterministicos ---\n"
            f"technical_score: {investigation_input.technical_score}\n"
            f"text_score: {investigation_input.text_score}\n"
            f"evidence_score: {investigation_input.evidence_score}\n"
            f"quality_score: {investigation_input.quality_score}\n"
            f"problems: {sorted(investigation_input.deterministic_problems)}\n"
            f"warnings: {sorted(investigation_input.deterministic_warnings)}\n\n"
            "--- Revisao semantica simples (ja realizada) ---\n"
            f"startup_match_score: {investigation_input.startup_match_score}\n"
            f"evidence_clarity_score: {investigation_input.evidence_clarity_score}\n"
            f"source_reliability_score: {investigation_input.source_reliability_score}\n"
            f"statement_specificity_score: {investigation_input.statement_specificity_score}\n"
            f"context_completeness_score: {investigation_input.context_completeness_score}\n"
            f"contradiction_detected: {investigation_input.contradiction_detected}\n"
            f"decisao da revisao simples: {investigation_input.semantic_decision}\n"
            f"motivo da revisao simples: {investigation_input.semantic_reason}\n"
            f"semantic_confidence calculada: {investigation_input.semantic_confidence}\n\n"
            f"Conteudo:\n{text}"
        )

        return {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": GeminiEvidenceResponse.model_json_schema(),
            },
        }

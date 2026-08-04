"""Avaliador Gemini via LangChain para o Evidence Validation Agent.

Este arquivo substitui a chamada HTTP manual da V1 por uma integracao usando
LangChain. A responsabilidade dele e pequena: receber o contexto da evidencia,
chamar o modelo Gemini e devolver um ``EvidenceValidationResult`` validado.

Ele ainda nao sabe nada sobre LangGraph. O grafo fica em
``graphs/evidence_validation`` e apenas usa este avaliador como uma ferramenta
de julgamento semantico.
"""

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.src.shared.observability import get_langfuse_callbacks

from apps.api.src.modules.agents.application.dto import (
    EvidenceValidationInput,
    EvidenceValidationResult,
)
from apps.api.src.modules.agents.application.public.semantic_investigator import (
    EvidenceValidationService,
)
from apps.api.src.modules.agents.domain.enums import AgentDecision
from apps.api.src.modules.agents.domain.exceptions import AgentInvestigationError


class LangChainGeminiEvidenceResponse(BaseModel):
    """Schema que a LLM deve obedecer.

    ``extra="forbid"`` evita que a resposta venha com campos inventados. Isso e
    importante porque a camada de agents precisa devolver uma decisao previsivel
    para o scraping.
    """

    model_config = ConfigDict(extra="forbid")

    decision: AgentDecision
    reason: str = Field(min_length=1, max_length=1000)


class LangChainGeminiEvidenceJudge(EvidenceValidationService):
    """Servico que usa Gemini, via LangChain, para julgar uma evidencia."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_text_characters: int = 20_000,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY e obrigatoria.")
        if not model:
            raise ValueError("GEMINI_MODEL e obrigatorio.")

        self.model = model
        self.max_text_characters = max_text_characters

        # ChatGoogleGenerativeAI e o adaptador oficial do LangChain para Gemini.
        # Usamos temperatura 0 para reduzir variacao nas decisoes de validacao.
        chat_model = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
        )

        # ``with_structured_output`` pede para o modelo devolver algo que siga o
        # schema Pydantic. Isso reduz bastante a chance de receber texto solto.
        self.structured_model = chat_model.with_structured_output(
            LangChainGeminiEvidenceResponse
        )

    async def investigate(
        self,
        investigation_input: EvidenceValidationInput,
    ) -> EvidenceValidationResult:
        """Chama Gemini via LangChain e converte a saida para o DTO publico."""

        messages = self._build_messages(investigation_input)

        try:
            parsed = await self.structured_model.ainvoke(
                messages, config={"callbacks": get_langfuse_callbacks()}
            )
        except (ValidationError, ValueError, TypeError) as error:
            raise AgentInvestigationError(
                "Gemini devolveu uma resposta de investigacao invalida."
            ) from error
        except Exception as error:
            raise AgentInvestigationError(
                f"Gemini nao conseguiu concluir a investigacao: {error}."
            ) from error

        if not isinstance(parsed, LangChainGeminiEvidenceResponse):
            raise AgentInvestigationError(
                "Gemini devolveu uma resposta de investigacao em formato inesperado."
            )

        return EvidenceValidationResult(
            decision=parsed.decision,
            reason=parsed.reason,
        )

    def _build_messages(
        self,
        investigation_input: EvidenceValidationInput,
    ) -> list[SystemMessage | HumanMessage]:
        """Monta as mensagens enviadas ao Gemini.

        A system message define o papel do agente. A human message leva os dados
        concretos da evidencia. Separar as duas deixa o prompt mais legivel.
        """

        text = investigation_input.raw_text[: self.max_text_characters]

        system_message = SystemMessage(
            content=(
                "Voce e o Evidence Validation Agent do AI Venture Radar. "
                "Sua tarefa e julgar se uma evidencia coletada pelo scraper "
                "pode ser usada com seguranca. Nao invente fatos. Use somente "
                "as informacoes fornecidas."
            )
        )

        human_message = HumanMessage(
            content=(
                "Reavalie esta evidencia e escolha uma decisao final:\n"
                "- accepted: o conteudo e util e confiavel;\n"
                "- rejected: o conteudo nao deve ser usado;\n"
                "- needs_more_sources: esta pagina sozinha nao basta.\n\n"
                f"URL: {investigation_input.url}\n"
                f"Titulo: {investigation_input.title or 'ausente'}\n\n"
                "--- Scores deterministicos ---\n"
                f"technical_score: {investigation_input.technical_score}\n"
                f"text_score: {investigation_input.text_score}\n"
                f"evidence_score: {investigation_input.evidence_score}\n"
                f"quality_score: {investigation_input.quality_score}\n"
                f"problems: {sorted(investigation_input.deterministic_problems)}\n"
                f"warnings: {sorted(investigation_input.deterministic_warnings)}\n\n"
                "--- Revisao semantica simples ---\n"
                f"startup_match_score: {investigation_input.startup_match_score}\n"
                f"evidence_clarity_score: {investigation_input.evidence_clarity_score}\n"
                f"source_reliability_score: "
                f"{investigation_input.source_reliability_score}\n"
                f"statement_specificity_score: "
                f"{investigation_input.statement_specificity_score}\n"
                f"context_completeness_score: "
                f"{investigation_input.context_completeness_score}\n"
                f"contradiction_detected: "
                f"{investigation_input.contradiction_detected}\n"
                f"semantic_decision: {investigation_input.semantic_decision}\n"
                f"semantic_reason: {investigation_input.semantic_reason}\n"
                f"semantic_confidence: {investigation_input.semantic_confidence}\n\n"
                f"Conteudo:\n{text}"
            )
        )

        return [system_message, human_message]

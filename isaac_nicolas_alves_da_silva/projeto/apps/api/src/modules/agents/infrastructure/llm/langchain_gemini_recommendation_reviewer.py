"""Revisor Gemini via LangChain para o Recommendation Agent.

Recebe os candidatos deterministicos ja gerados por
``recommendations`` (via ``RecommendationToolPort``) e usa Gemini para
duas coisas, no mesmo lote: julgar candidatos ambiguos (score baixo, pode
ser coincidencia de keyword) e reescrever a justificativa em linguagem de
negocio. Nao gera recomendacoes do zero e nao recalcula score — isso
continua sendo responsabilidade exclusiva de
``recommendations/domain/policies.py::match_technologies()``.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.src.shared.observability import get_langfuse_callbacks

from apps.api.src.modules.agents.application.dto import RecommendationCandidate
from apps.api.src.modules.agents.application.ports import RecommendationReviewerPort
from apps.api.src.modules.agents.domain.exceptions import AgentRecommendationError

# Abaixo deste score, o agente considera o candidato "ambiguo" — o LLM
# decide se mantem ou descarta. A partir daqui (inclusive), o candidato e'
# sempre mantido em codigo, independente do que o LLM responder: decisao
# imposta, nao confiada so ao prompt (regra 9 do CLAUDE.md). Limiar proprio
# de ``agents``, decoupled do `MIN_MATCH_SCORE=0.25` (piso de inclusao) de
# ``recommendations``.
AMBIGUOUS_SCORE_THRESHOLD = 0.5


class ReviewedRecommendationItem(BaseModel):
    """Schema que a LLM deve obedecer para cada candidato revisado."""

    model_config = ConfigDict(extra="forbid")

    technology_slug: str
    keep: bool
    business_justification: str = Field(min_length=1, max_length=600)


class LangChainGeminiRecommendationReviewResponse(BaseModel):
    """Schema completo da resposta do Gemini."""

    model_config = ConfigDict(extra="forbid")

    items: list[ReviewedRecommendationItem]


class LangChainGeminiRecommendationReviewer(RecommendationReviewerPort):
    """Servico que usa Gemini, via LangChain, para revisar recomendacoes."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        structured_model: Runnable[Any, Any] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY e obrigatoria.")
        if not model:
            raise ValueError("GEMINI_MODEL e obrigatorio.")

        self.model = model

        if structured_model is not None:
            self.structured_model = structured_model
        else:
            chat_model = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=api_key,
                temperature=temperature,
            )
            self.structured_model = chat_model.with_structured_output(
                LangChainGeminiRecommendationReviewResponse
            )

    async def review(
        self, candidates: list[RecommendationCandidate]
    ) -> list[RecommendationCandidate]:
        """Chama Gemini via LangChain e aplica a revisao com guarda em codigo."""

        if not candidates:
            return []

        messages = self._build_messages(candidates)

        try:
            parsed = await self.structured_model.ainvoke(
                messages, config={"callbacks": get_langfuse_callbacks()}
            )
        except (ValidationError, ValueError, TypeError) as error:
            raise AgentRecommendationError(
                "Gemini devolveu uma resposta de revisao invalida."
            ) from error
        except Exception as error:
            raise AgentRecommendationError(
                f"Gemini nao conseguiu concluir a revisao: {error}."
            ) from error

        if not isinstance(parsed, LangChainGeminiRecommendationReviewResponse):
            raise AgentRecommendationError(
                "Gemini devolveu uma resposta de revisao em formato inesperado."
            )

        reviewed_by_slug = {item.technology_slug: item for item in parsed.items}

        result: list[RecommendationCandidate] = []
        for candidate in candidates:
            reviewed = reviewed_by_slug.get(candidate.technology_slug)
            is_confident = candidate.score >= AMBIGUOUS_SCORE_THRESHOLD

            if reviewed is None:
                # Gemini nao devolveu este slug (lote incompleto/instavel).
                # Mantemos o candidato como veio do determinístico, sem
                # arriscar perder uma recomendacao por causa disso.
                result.append(candidate)
                continue

            if not is_confident and not reviewed.keep:
                continue

            result.append(
                RecommendationCandidate(
                    technology_slug=candidate.technology_slug,
                    technology_name=candidate.technology_name,
                    category=candidate.category,
                    score=candidate.score,
                    justification=reviewed.business_justification,
                    matched_keywords=candidate.matched_keywords,
                )
            )

        return result

    def _build_messages(
        self, candidates: list[RecommendationCandidate]
    ) -> list[SystemMessage | HumanMessage]:
        """Monta as mensagens enviadas ao Gemini."""

        candidates_block = "\n".join(
            f"- slug={c.technology_slug}; tecnologia={c.technology_name}; "
            f"categoria={c.category}; score={c.score:.2f}; "
            f"keywords={', '.join(c.matched_keywords) or '(nenhuma)'}; "
            f"justificativa_tecnica={c.justification}"
            for c in candidates
        )

        system_message = SystemMessage(
            content=(
                "Voce e o Recommendation Agent do AI Venture Radar. Para "
                "cada candidato de recomendacao de tecnologia NVIDIA, "
                "devolva: 'keep' (manter ou descartar — so importa para "
                "candidatos com score baixo, onde o match pode ser uma "
                "coincidencia de palavra-chave sem relacao real) e "
                "'business_justification' (reescreva a justificativa "
                "tecnica em linguagem de negocio, clara para um executivo, "
                "citando as keywords e o caso de uso — nunca invente fatos "
                "novos, so reformule o que ja foi fornecido)."
            )
        )

        human_message = HumanMessage(
            content=(
                "Revise estes candidatos de recomendacao:\n\n"
                f"{candidates_block}"
            )
        )

        return [system_message, human_message]

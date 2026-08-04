"""Reescritor de prosa Gemini via LangChain para o Briefing Agent.

Recebe o Markdown deterministico ja montado por
``briefing/domain/policies.py::build_briefing_markdown()`` (via
``BriefingToolPort``) e usa Gemini so para reescrever a prosa em
linguagem executiva — nunca monta secoes, decide riscos ou proximas
acoes; isso continua sendo responsabilidade exclusiva do template
deterministico.
"""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.src.shared.observability import get_langfuse_callbacks

from apps.api.src.modules.agents.application.ports import BriefingProseRewriterPort
from apps.api.src.modules.agents.domain.exceptions import AgentBriefingError

_URL_PATTERN = re.compile(r"https?://[^\s)\]]+")


class BriefingProseResponse(BaseModel):
    """Schema que a LLM deve obedecer."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=8000)


class LangChainGeminiBriefingProseRewriter(BriefingProseRewriterPort):
    """Servico que usa Gemini, via LangChain, para reescrever a prosa do briefing."""

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
                BriefingProseResponse
            )

    async def rewrite(self, content: str) -> str:
        """Chama Gemini via LangChain e aplica o fallback seguro em codigo."""

        messages = self._build_messages(content)

        try:
            parsed = await self.structured_model.ainvoke(
                messages, config={"callbacks": get_langfuse_callbacks()}
            )
        except (ValidationError, ValueError, TypeError) as error:
            raise AgentBriefingError(
                "Gemini devolveu uma resposta de reescrita invalida."
            ) from error
        except Exception as error:
            raise AgentBriefingError(
                f"Gemini nao conseguiu concluir a reescrita: {error}."
            ) from error

        if not isinstance(parsed, BriefingProseResponse):
            raise AgentBriefingError(
                "Gemini devolveu uma resposta de reescrita em formato inesperado."
            )

        if not self._preserves_citations(content, parsed.content):
            # Reescrita perdeu pelo menos uma URL do Markdown deterministico.
            # Fallback seguro: nunca arriscar rastreabilidade por prosa mais
            # bonita (regra 9 do CLAUDE.md — a saida do LLM e' validada
            # estruturalmente, nunca confiada direto).
            return content

        return parsed.content

    def _preserves_citations(self, original: str, rewritten: str) -> bool:
        original_urls = set(_URL_PATTERN.findall(original))
        if not original_urls:
            return True
        rewritten_urls = set(_URL_PATTERN.findall(rewritten))
        return original_urls.issubset(rewritten_urls)

    def _build_messages(self, content: str) -> list[SystemMessage | HumanMessage]:
        """Monta as mensagens enviadas ao Gemini."""

        system_message = SystemMessage(
            content=(
                "Voce e o Briefing Agent do AI Venture Radar. Reescreva o "
                "Markdown a seguir em linguagem executiva, clara para quem "
                "decide negocios na NVIDIA. Preserve a estrutura de secoes, "
                "todos os links/URLs de evidencia exatamente como estao, e "
                "todos os fatos e numeros — nunca invente, omita ou altere "
                "dados. So melhore a redacao da prosa."
            )
        )

        human_message = HumanMessage(content=content)

        return [system_message, human_message]

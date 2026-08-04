"""Planejador de buscas via LangChain + Gemini.

Este arquivo e a parte LLM do Search Planner Agent. Ele recebe um caso em que
faltam evidencias e pede ao Gemini para sugerir queries objetivas.

Ele nao executa busca, nao chama scraper e nao salva nada. A unica saida dele e
um ``SearchPlanResult`` validado.
"""

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.src.shared.observability import get_langfuse_callbacks

from apps.api.src.modules.agents.application.dto import (
    SearchPlanInput,
    SearchPlanResult,
    SearchQuerySuggestion,
)
from apps.api.src.modules.agents.application.public.search_planner import (
    SearchPlanningService,
)
from apps.api.src.modules.agents.domain.exceptions import AgentPlanningError


class LangChainSearchQueryResponse(BaseModel):
    """Schema de uma query sugerida pelo modelo."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=200)
    purpose: str = Field(min_length=3, max_length=300)
    priority: int = Field(ge=1, le=10)


class LangChainSearchPlanResponse(BaseModel):
    """Schema completo que o Gemini deve devolver."""

    model_config = ConfigDict(extra="forbid")

    queries: list[LangChainSearchQueryResponse] = Field(min_length=1, max_length=10)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("queries")
    @classmethod
    def query_texts_must_be_unique(
        cls,
        queries: list[LangChainSearchQueryResponse],
    ) -> list[LangChainSearchQueryResponse]:
        """Evita plano com queries duplicadas."""

        normalized = [query.query.strip().lower() for query in queries]
        if len(normalized) != len(set(normalized)):
            raise ValueError("queries duplicadas nao sao permitidas")
        return queries


class LangChainGeminiSearchPlanner(SearchPlanningService):
    """Gera queries de busca usando Gemini via LangChain."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_text_characters: int = 8_000,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY e obrigatoria.")
        if not model:
            raise ValueError("GEMINI_MODEL e obrigatorio.")

        self.model = model
        self.max_text_characters = max_text_characters

        chat_model = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
        )
        self.structured_model = chat_model.with_structured_output(
            LangChainSearchPlanResponse
        )

    async def plan_searches(self, plan_input: SearchPlanInput) -> SearchPlanResult:
        """Chama Gemini e converte a resposta para DTO publico."""

        messages = self._build_messages(plan_input)

        try:
            parsed = await self.structured_model.ainvoke(
                messages, config={"callbacks": get_langfuse_callbacks()}
            )
        except (ValidationError, ValueError, TypeError) as error:
            raise AgentPlanningError(
                "Gemini devolveu um plano de busca invalido."
            ) from error
        except Exception as error:
            raise AgentPlanningError(
                f"Gemini nao conseguiu gerar o plano de busca: {error}."
            ) from error

        if not isinstance(parsed, LangChainSearchPlanResponse):
            raise AgentPlanningError(
                "Gemini devolveu um plano de busca em formato inesperado."
            )

        queries = [
            SearchQuerySuggestion(
                query=item.query.strip(),
                purpose=item.purpose.strip(),
                priority=item.priority,
            )
            for item in parsed.queries[: plan_input.max_queries]
        ]

        if not queries:
            raise AgentPlanningError("Gemini nao sugeriu nenhuma query valida.")

        return SearchPlanResult(
            queries=queries,
            reason=parsed.reason.strip(),
        )

    def _build_messages(
        self,
        plan_input: SearchPlanInput,
    ) -> list[SystemMessage | HumanMessage]:
        """Monta o prompt do planejador.

        A instrucao principal reforca que o agente deve planejar buscas, nao
        concluir fatos. Quem validara as fontes depois sera outro fluxo.
        """

        text = plan_input.raw_text[: self.max_text_characters]

        system_message = SystemMessage(
            content=(
                "Voce e o Search Planner Agent do AI Venture Radar. "
                "Sua tarefa e planejar buscas para encontrar fontes melhores "
                "sobre uma startup, com foco principal no ecossistema "
                "brasileiro. Nao conclua fatos e nao invente dados: "
                "apenas gere queries objetivas e priorizadas."
            )
        )

        human_message = HumanMessage(
            content=(
                "Gere queries para buscar mais evidencias.\n\n"
                f"Startup conhecida: {plan_input.startup_name or 'desconhecida'}\n"
                f"Fonte atual: {plan_input.source_url}\n"
                f"Titulo atual: {plan_input.source_title or 'ausente'}\n"
                f"Motivo da duvida: {plan_input.reason}\n"
                f"Termos conhecidos: {sorted(plan_input.known_terms)}\n"
                f"URLs ja tentadas ou excluidas: {sorted(plan_input.excluded_urls)}\n"
                f"Numero maximo de queries: {plan_input.max_queries}\n\n"
                "Priorize buscas que ajudem a verificar: site oficial, produto, "
                "fundadores, funding, clientes, uso de IA e fontes confiaveis. "
                "Inclua sempre pelo menos uma query explicitamente voltada a IA "
                "(ex: artificial intelligence, machine learning, generative AI, "
                "LLM, AI product) e termos Brasil/Brazil quando fizer sentido "
                "para separar AI-native, AI-enabled e non-AI no contexto de "
                "startups brasileiras.\n\n"
                f"Texto que gerou a duvida:\n{text}"
            )
        )

        return [system_message, human_message]

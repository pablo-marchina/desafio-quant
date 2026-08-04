"""Classificador Gemini via LangChain para o Startup Classifier Agent.

Recebe o perfil/evidencias da startup, chama o modelo Gemini e devolve um
``StartupClassificationResult`` validado. Nao sabe nada sobre LangGraph —
o grafo fica em ``graphs/startup_classification`` e usa este classificador
como uma ferramenta de julgamento semantico.
"""

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.src.shared.observability import get_langfuse_callbacks

from apps.api.src.modules.agents.application.dto import (
    StartupClassificationInput,
    StartupClassificationResult,
)
from apps.api.src.modules.agents.application.public.startup_classifier import (
    StartupClassifierService,
)
from apps.api.src.modules.agents.domain.enums import StartupMaturityLevel
from apps.api.src.modules.agents.domain.exceptions import AgentClassificationError


class LangChainGeminiClassificationResponse(BaseModel):
    """Schema que a LLM deve obedecer."""

    model_config = ConfigDict(extra="forbid")

    level: StartupMaturityLevel
    reason: str = Field(min_length=1, max_length=1000)


class LangChainGeminiStartupClassifier(StartupClassifierService):
    """Servico que usa Gemini, via LangChain, para classificar uma startup."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_evidence_characters: int = 20_000,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY e obrigatoria.")
        if not model:
            raise ValueError("GEMINI_MODEL e obrigatorio.")

        self.model = model
        self.max_evidence_characters = max_evidence_characters

        chat_model = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
        )
        self.structured_model = chat_model.with_structured_output(
            LangChainGeminiClassificationResponse
        )

    async def classify(
        self,
        classification_input: StartupClassificationInput,
    ) -> StartupClassificationResult:
        """Chama Gemini via LangChain e converte a saida para o DTO publico."""

        messages = self._build_messages(classification_input)

        try:
            parsed = await self.structured_model.ainvoke(
                messages, config={"callbacks": get_langfuse_callbacks()}
            )
        except (ValidationError, ValueError, TypeError) as error:
            raise AgentClassificationError(
                "Gemini devolveu uma resposta de classificacao invalida."
            ) from error
        except Exception as error:
            raise AgentClassificationError(
                f"Gemini nao conseguiu concluir a classificacao: {error}."
            ) from error

        if not isinstance(parsed, LangChainGeminiClassificationResponse):
            raise AgentClassificationError(
                "Gemini devolveu uma resposta de classificacao em formato inesperado."
            )

        return StartupClassificationResult(
            level=parsed.level,
            reason=parsed.reason,
        )

    def _build_messages(
        self,
        classification_input: StartupClassificationInput,
    ) -> list[SystemMessage | HumanMessage]:
        """Monta as mensagens enviadas ao Gemini."""

        evidence_block = "\n".join(
            f"- {text[: self.max_evidence_characters]}"
            for text in classification_input.evidence_texts
        ) or "(nenhuma evidencia textual disponivel)"

        system_message = SystemMessage(
            content=(
                "Voce e o Startup Classifier Agent do AI Venture Radar. Sua "
                "tarefa e classificar a maturidade de IA de uma startup com "
                "base em evidencias publicas. O radar tem foco em startups "
                "brasileiras, mas a maturidade de IA deve ser julgada apenas "
                "pelas evidencias fornecidas. Nao invente fatos. Use somente "
                "as informacoes fornecidas."
            )
        )

        human_message = HumanMessage(
            content=(
                "Classifique esta startup em uma das categorias:\n"
                "- ai_native: a empresa vende IA como produto principal. "
                "Exemplos: laboratorios/model providers, plataformas de "
                "modelos, agentes autonomos, infraestrutura de treino ou "
                "inferencia, geracao de video/imagem/audio por IA. A empresa "
                "nao faria sentido sem IA. Exemplos canonicos: Mistral, "
                "Runway, Perplexity, Together AI;\n"
                "- ai_enabled: a empresa tem um produto principal que nao e "
                "somente IA, mas incorpora IA como camada relevante de "
                "produtividade, automacao, busca, escrita, design, analytics "
                "ou assistente. Mesmo que a pagina fale muito de 'AI', use "
                "ai_enabled quando a companhia continua sendo primariamente "
                "workspace, design, educacao, vendas, suporte, ecommerce ou "
                "SaaS vertical com recursos de IA. Exemplos canonicos: "
                "Notion AI, Grammarly, Canva AI, Intercom Fin;\n"
                "- non_ai: nao ha evidencia forte de uso de IA no produto ou "
                "operacao. Exemplos canonicos: Glossier, Allbirds, Warby "
                "Parker quando a evidencia fala apenas de varejo, beleza, "
                "moda, ecommerce ou historia da empresa.\n\n"
                "Regra de desempate: se a empresa TREINA, faz fine-tuning, "
                "hospeda, serve ou desenvolve MODELOS PROPRIOS de IA, classifique "
                "ai_native; ter API, app ou 'plataforma' NAO rebaixa para "
                "ai_enabled (model providers servem via API e continuam ai_native). "
                "Use ai_enabled apenas quando a IA e uma feature dentro de um "
                "produto que existiria sem ela (workspace, CRM, ecommerce, design, "
                "SaaS vertical). Na duvida entre treinar-modelo-proprio vs feature, "
                "pese o que e o nucleo do produto, nao o volume de marketing de 'AI'.\n\n"
                f"Nome: {classification_input.name}\n"
                f"Setor: {classification_input.sector or 'desconhecido'}\n"
                f"Descricao: {classification_input.description or 'ausente'}\n"
                f"Pais: {classification_input.country or 'desconhecido'}\n"
                f"Site: {classification_input.website_url or 'ausente'}\n\n"
                "--- Evidencias coletadas ---\n"
                f"{evidence_block}"
            )
        )

        return [system_message, human_message]

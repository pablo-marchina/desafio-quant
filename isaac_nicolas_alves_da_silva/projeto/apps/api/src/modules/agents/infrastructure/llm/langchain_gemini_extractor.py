"""Extrator Gemini via LangChain para o Extraction Agent.

Recebe o perfil/evidencias da startup, chama o modelo Gemini e devolve um
``ExtractionResult`` validado. Nao sabe nada sobre LangGraph — o grafo
fica em ``graphs/extraction`` e usa este extrator como uma ferramenta de
extracao estruturada.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.src.shared.observability import get_langfuse_callbacks

from apps.api.src.modules.agents.application.dto import (
    ExtractionInput,
    ExtractionResult,
)
from apps.api.src.modules.agents.application.public.extractor import (
    ExtractionService,
)
from apps.api.src.modules.agents.domain.enums import ExtractedFundingStage
from apps.api.src.modules.agents.domain.exceptions import AgentExtractionError

AiWorkloadTypeLiteral = Literal[
    "nlp", "vision", "recommendation", "simulation", "analytics", "mlops", "speech",
    "unknown",
]
AiModelTypeLiteral = Literal[
    "trains_own", "fine_tuning", "api_based", "classical_ml", "unknown",
]
AiDataModalityLiteral = Literal[
    "text", "image", "audio", "tabular", "3d", "log_network", "unknown",
]
AiDeploymentStageLiteral = Literal[
    "research", "mvp", "pilot", "production", "scale", "unknown",
]
AiInfraEnvironmentLiteral = Literal[
    "cloud", "on_premise", "edge", "hybrid", "unknown",
]
AiGpuNeedLiteral = Literal["high", "medium", "low", "unknown"]
AiLatencyRequirementLiteral = Literal["realtime", "batch", "unknown"]


class LangChainGeminiExtractionResponse(BaseModel):
    """Schema que a LLM deve obedecer."""

    model_config = ConfigDict(extra="forbid")

    # Campos existentes
    founders: list[str] = Field(default_factory=list, max_length=20)
    funding_stage: ExtractedFundingStage
    funding_amount_usd: float | None = None
    customers: list[str] = Field(default_factory=list, max_length=20)
    sector: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    country: str | None = Field(default=None, max_length=40)

    # Perfil estruturado de IA
    ai_workload_type: AiWorkloadTypeLiteral = "unknown"
    model_type: AiModelTypeLiteral = "unknown"
    data_modality: AiDataModalityLiteral = "unknown"
    deployment_stage: AiDeploymentStageLiteral = "unknown"
    infra_environment: AiInfraEnvironmentLiteral = "unknown"
    gpu_need: AiGpuNeedLiteral = "unknown"
    latency_requirement: AiLatencyRequirementLiteral = "unknown"
    scale_signal: str | None = Field(default=None, max_length=200)
    current_tools: list[str] = Field(default_factory=list, max_length=20)
    business_goal: str | None = Field(default=None, max_length=300)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    field_evidence_ids: dict[str, list[str]] = Field(default_factory=dict)


class LangChainGeminiExtractor(ExtractionService):
    """Servico que usa Gemini, via LangChain, para extrair dados estruturados."""

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
            LangChainGeminiExtractionResponse
        )

    async def extract(
        self,
        extraction_input: ExtractionInput,
    ) -> ExtractionResult:
        """Chama Gemini via LangChain e converte a saida para o DTO publico."""

        messages = self._build_messages(extraction_input)

        try:
            parsed = await self.structured_model.ainvoke(
                messages, config={"callbacks": get_langfuse_callbacks()}
            )
        except (ValidationError, ValueError, TypeError) as error:
            raise AgentExtractionError(
                "Gemini devolveu uma resposta de extracao invalida."
            ) from error
        except Exception as error:
            raise AgentExtractionError(
                f"Gemini nao conseguiu concluir a extracao: {error}."
            ) from error

        if not isinstance(parsed, LangChainGeminiExtractionResponse):
            raise AgentExtractionError(
                "Gemini devolveu uma resposta de extracao em formato inesperado."
            )

        return ExtractionResult(
            founders=parsed.founders,
            funding_stage=parsed.funding_stage,
            funding_amount_usd=parsed.funding_amount_usd,
            customers=parsed.customers,
            sector=parsed.sector,
            description=parsed.description,
            country=parsed.country,
            ai_workload_type=parsed.ai_workload_type,
            model_type=parsed.model_type,
            data_modality=parsed.data_modality,
            deployment_stage=parsed.deployment_stage,
            infra_environment=parsed.infra_environment,
            gpu_need=parsed.gpu_need,
            latency_requirement=parsed.latency_requirement,
            scale_signal=parsed.scale_signal,
            current_tools=list(parsed.current_tools),
            business_goal=parsed.business_goal,
            field_confidence=dict(parsed.field_confidence),
            field_evidence_ids=dict(parsed.field_evidence_ids),
        )

    def _build_messages(
        self,
        extraction_input: ExtractionInput,
    ) -> list[SystemMessage | HumanMessage]:
        """Monta as mensagens enviadas ao Gemini."""

        evidence_block = "\n".join(
            f"- {text[: self.max_evidence_characters]}"
            for text in extraction_input.evidence_texts
        ) or "(nenhuma evidencia textual disponivel)"

        system_message = SystemMessage(
            content=(
                "Voce e o Extraction Agent do AI Venture Radar. Sua tarefa e "
                "extrair fatos estruturados APENAS quando explicitamente "
                "mencionados nas evidencias. Nunca infira, deduza ou invente um "
                "dado que nao esteja escrito no texto. O radar tem foco em "
                "startups brasileiras; preserve sinais de Brasil quando "
                "aparecerem nas evidencias, mas nao invente pais, clientes ou "
                "fundadores por escopo.\n\n"
                "CAMPOS BASICOS:\n"
                "- founders: lista de fundadores mencionados.\n"
                "- funding_stage: estagio de funding ('pre_seed','seed','series_a',"
                "'series_b','series_c_plus','unknown').\n"
                "- funding_amount_usd: valor em USD ou null.\n"
                "- customers: clientes mencionados.\n"
                "- sector: rotulo curto de categoria em ingles (ex. 'Healthcare AI').\n"
                "- description: 1-2 frases em ingles resumindo o produto.\n"
                "- country: codigo ISO-2 do pais sede da empresa se mencionado "
                "ou claramente inferivel da evidencia (ex. 'BR' para "
                "Brasil/cidades brasileiras); senao null. Nao invente.\n\n"
                "PERFIL DE IA (sempre em ingles, baseado no que as evidencias "
                "realmente descrevem — use 'unknown' quando sem evidencia):\n"
                "- ai_workload_type: tipo de workload de IA principal "
                "('nlp','vision','recommendation','simulation','analytics','mlops','speech','unknown').\n"
                "- model_type: como a startup usa modelos "
                "('trains_own','fine_tuning','api_based','classical_ml','unknown').\n"
                "- data_modality: modalidade de dados principal "
                "('text','image','audio','tabular','3d','log_network','unknown').\n"
                "- deployment_stage: maturidade de deploy "
                "('research','mvp','pilot','production','scale','unknown').\n"
                "- infra_environment: ambiente de infraestrutura "
                "('cloud','on_premise','edge','hybrid','unknown').\n"
                "- gpu_need: necessidade de GPU "
                "('high','medium','low','unknown').\n"
                "- latency_requirement: requisito de latencia "
                "('realtime','batch','unknown').\n"
                "- scale_signal: volume/throughput observado se mencionado (texto curto ou null).\n"
                "- current_tools: frameworks/stack mencionados (lista).\n"
                "- business_goal: objetivo de negocio declarado (texto curto ou null).\n"
                "- field_confidence: dict com confianca (0-1) para TODOS os campos "
                "que voce preencheu com evidencia real — tanto campos basicos "
                "(ex. {'founders': 0.9, 'sector': 0.8}) quanto campos de perfil de IA "
                "(ex. {'ai_workload_type': 0.85}). "
                "Nao inclua campos que ficaram vazios, null ou 'unknown'.\n"
                "- field_evidence_ids: dict com os nomes dos campos preenchidos "
                "apontando para IDs de evidencia quando IDs forem fornecidos no "
                "texto de entrada. Se nao houver IDs explicitos, devolva {}."
            )
        )

        human_message = HumanMessage(
            content=(
                "Extraia os dados estruturados desta startup a partir das "
                "evidencias abaixo.\n\n"
                f"Nome: {extraction_input.name}\n"
                f"Setor: {extraction_input.sector or 'desconhecido'}\n"
                f"Descricao: {extraction_input.description or 'ausente'}\n\n"
                "--- Evidencias coletadas ---\n"
                f"{evidence_block}"
            )
        )

        return [system_message, human_message]

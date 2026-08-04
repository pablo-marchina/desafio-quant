"""Gerador de respostas RAG via LangChain + Gemini."""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.api.src.shared.observability import get_langfuse_callbacks
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apps.api.src.modules.rag.application.dto import (
    GenerateRagAnswerInput,
    RagAnswerView,
    RagCitationView,
)
from apps.api.src.modules.rag.application.public.answer_generator import (
    RagAnswerGenerator,
)
from apps.api.src.modules.rag.domain.exceptions import RagAnswerGenerationError

MAX_RAG_CITATIONS = 10
MAX_RAG_CITATION_QUOTE_CHARACTERS = 1000


class GeminiRagCitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    # O limite publico e aplicado em _to_view. Alguns modelos retornam
    # trechos longos demais mesmo com prompt curto; isso nao deve invalidar
    # a resposta inteira.
    quote: str = Field(min_length=1)


class GeminiRagAnswerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=4000)
    # Sem min_length: quando a evidencia recuperada nao responde a
    # pergunta, o Gemini deve dizer isso e devolver citations vazio, nao
    # inventar uma citacao so para satisfazer o schema. O caso de uso
    # (_to_view) trata lista vazia como erro de dominio explicito, nao
    # como falha de parsing do LLM.
    #
    # Nao limite aqui: modelos podem devolver citacoes extras mesmo quando
    # instruidos a serem breves. O limite publico e aplicado em _to_view para
    # evitar que uma resposta util falhe ainda no parsing estruturado.
    citations: list[GeminiRagCitationResponse] = Field(default_factory=list)


class LangChainGeminiRagAnswerGenerator(RagAnswerGenerator):
    """Gera respostas fundamentadas usando apenas evidencias recuperadas."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_evidence_characters: int = 12_000,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY e obrigatoria.")
        if not model:
            raise ValueError("GEMINI_MODEL e obrigatorio.")

        self.max_evidence_characters = max_evidence_characters
        chat_model = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
        )
        self.structured_model = chat_model.with_structured_output(
            GeminiRagAnswerResponse
        )

    async def generate(self, answer_input: GenerateRagAnswerInput) -> RagAnswerView:
        messages = self._build_messages(answer_input)

        try:
            parsed = await self.structured_model.ainvoke(
                messages, config={"callbacks": get_langfuse_callbacks()}
            )
        except (ValidationError, ValueError, TypeError) as error:
            raise RagAnswerGenerationError(
                "Gemini devolveu uma resposta RAG invalida."
            ) from error
        except Exception as error:
            raise RagAnswerGenerationError(
                f"Gemini nao conseguiu gerar a resposta RAG: {error}."
            ) from error

        if not isinstance(parsed, GeminiRagAnswerResponse):
            raise RagAnswerGenerationError(
                "Gemini devolveu uma resposta RAG em formato inesperado."
            )

        return self._to_view(answer_input, parsed)

    def _build_messages(
        self, answer_input: GenerateRagAnswerInput
    ) -> list[SystemMessage | HumanMessage]:
        evidence_text = self._format_evidences(answer_input)
        system_message = SystemMessage(
            content=(
                "Voce e o modulo RAG do AI Venture Radar. Responda somente com "
                "base nas evidencias fornecidas. Nao invente fatos. Cite o "
                "chunk_id de cada evidencia realmente usada na resposta. Se "
                "as evidencias recuperadas nao responderem a pergunta, diga "
                "isso claramente na resposta e devolva citations como uma "
                "lista vazia — nunca cite um chunk que nao sustenta a "
                "resposta so para preencher a lista."
            )
        )
        human_message = HumanMessage(
            content=(
                f"Pergunta:\n{answer_input.query}\n\n"
                "Evidencias recuperadas:\n"
                f"{evidence_text}\n\n"
                "Gere uma resposta curta, fundamentada, e uma lista de citacoes "
                "usando apenas chunk_id existentes nas evidencias."
            )
        )
        return [system_message, human_message]

    def _format_evidences(self, answer_input: GenerateRagAnswerInput) -> str:
        blocks: list[str] = []
        remaining = self.max_evidence_characters
        for index, evidence in enumerate(answer_input.evidences, start=1):
            text = evidence.text[:remaining]
            if not text:
                break
            block = (
                f"[{index}]\n"
                f"chunk_id: {evidence.chunk_id}\n"
                f"document_id: {evidence.document_id}\n"
                f"source_url: {evidence.source_url}\n"
                f"score: {evidence.score}\n"
                f"text: {text}\n"
            )
            blocks.append(block)
            remaining -= len(text)
            if remaining <= 0:
                break
        return "\n".join(blocks)

    def _to_view(
        self,
        answer_input: GenerateRagAnswerInput,
        parsed: GeminiRagAnswerResponse,
    ) -> RagAnswerView:
        evidences_by_id = {
            str(evidence.chunk_id): evidence for evidence in answer_input.evidences
        }
        citations: list[RagCitationView] = []

        for citation in parsed.citations[:MAX_RAG_CITATIONS]:
            evidence = evidences_by_id.get(citation.chunk_id)
            if evidence is None and citation.chunk_id.isdigit():
                evidence_index = int(citation.chunk_id) - 1
                if 0 <= evidence_index < len(answer_input.evidences):
                    evidence = answer_input.evidences[evidence_index]
            if evidence is None:
                raise RagAnswerGenerationError(
                    f"Resposta citou chunk inexistente: {citation.chunk_id}."
                )
            citations.append(
                RagCitationView(
                    chunk_id=evidence.chunk_id,
                    document_id=evidence.document_id,
                    source_url=evidence.source_url,
                    quote=citation.quote.strip()[
                        :MAX_RAG_CITATION_QUOTE_CHARACTERS
                    ],
                )
            )

        # citations vazio e' uma resposta valida, nao uma falha do sistema:
        # o prompt pede explicitamente "diga isso claramente" quando a
        # evidencia recuperada nao sustenta uma resposta. Tratar como erro
        # (antes: RagAnswerGenerationError -> HTTP 502) devolvia uma falha
        # de gateway para o que e' so o modelo sendo honesto sobre nao ter
        # informacao suficiente - encontrado avaliando a baseline de
        # qualidade do RAG (Fase 2, ver docs/roadmap_evolucao_tecnica_mvp.md).

        return RagAnswerView(
            query=answer_input.query,
            answer=parsed.answer.strip(),
            citations=citations,
            evidences=answer_input.evidences,
        )

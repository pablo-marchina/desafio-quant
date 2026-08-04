from __future__ import annotations

import json

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from src.models import Evidence

from ..config import (
    EXTRACTION_MAX_CHARS_PER_EVIDENCE,
    EXTRACTION_MAX_EVIDENCES,
    EXTRACTION_MODEL,
    GROQ_API_KEY,
)
from ..schemas import StructuredStartupExtraction
from .base import StructuredExtractionProvider


class GroqStructuredExtractionProvider(StructuredExtractionProvider):
    def __init__(self) -> None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY nao configurada para extracao estruturada.")
        self._parser = PydanticOutputParser(pydantic_object=StructuredStartupExtraction)
        self._llm = ChatGroq(
            model=EXTRACTION_MODEL,
            temperature=0.0,
            max_tokens=1800,
            api_key=GROQ_API_KEY,
        )
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "Voce e um extractor rigoroso para o pipeline TAPI de startups AI-native. "
                        "Use apenas fatos explicitamente presentes nas evidencias fornecidas. "
                        "Nao invente fatos e nao preencha campos por inferencia fraca. "
                        "Se um campo nao estiver claramente suportado, retorne null ou lista vazia. "
                        "Cada campo deve incluir confidence, confidence_reason, evidence_ids, "
                        "source_priority, source_urls e source_excerpts. "
                        "source_excerpts devem ser trechos literais curtos, sem parafrase, "
                        "copiados das evidencias. "
                        "Nao use titulo da pagina como citacao se o corpo trouxer evidencia melhor. "
                        "Diferencie descricao da startup, segmento de mercado, sinais de AI-native, "
                        "modelo de negocio e mercado-alvo. "
                        "Nao confunda categoria tecnologica com segmento de mercado. "
                        "Quando houver conflito entre site oficial e diretorio estruturado, "
                        "registre em contradictions e explique em extraction_notes. "
                        "Quando existir fonte estruturada confiavel como perfil do Cubo, "
                        "priorize-a para nome, segmento e URL oficial, salvo evidencia mais forte em fonte primaria. "
                        "ai_native_signals deve ser lista de sinais concretos como "
                        "'llm_application', 'computer_vision', 'ai_agents', 'predictive_models', "
                        "'workflow_automation_with_ai', nunca apenas 'sim' ou 'nao'."
                    ),
                ),
                (
                    "user",
                    (
                        "Startup alvo: {startup_name}\n\n"
                        "Regras de citacao:\n"
                        "- use trechos curtos e literais\n"
                        "- prefira no maximo 2 trechos por campo\n"
                        "- cada trecho deve sustentar diretamente o valor do campo\n"
                        "- se nao houver trecho forte, retorne campo nulo\n\n"
                        "Evidencias:\n{evidence_block}\n\n"
                        "{format_instructions}"
                    ),
                ),
            ]
        )

    def extract(
        self,
        startup_name: str,
        evidences: list[Evidence],
    ) -> StructuredStartupExtraction:
        payload = self._prompt.format_messages(
            startup_name=startup_name,
            evidence_block=_serialize_evidences(evidences),
            format_instructions=self._parser.get_format_instructions(),
        )
        response = self._llm.invoke(payload)
        return self._parser.parse(response.content)


def _serialize_evidences(evidences: list[Evidence]) -> str:
    selected = evidences[:EXTRACTION_MAX_EVIDENCES]
    rows = []
    for idx, evidence in enumerate(selected, start=1):
        excerpt = (evidence.content or evidence.excerpt or "")[:EXTRACTION_MAX_CHARS_PER_EVIDENCE]
        rows.append(
            {
                "index": idx,
                "evidence_id": evidence.id,
                "url": evidence.url,
                "title": evidence.title,
                "source_type": evidence.source_type,
                "is_validated": evidence.is_validated,
                "source_priority": evidence.metadata.get("source_priority"),
                "evidence_kind": evidence.metadata.get("evidence_kind"),
                "excerpt": excerpt,
            }
        )
    return json.dumps(rows, ensure_ascii=False, indent=2)

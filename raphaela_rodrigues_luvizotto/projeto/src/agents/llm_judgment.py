from __future__ import annotations

import json

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from src.extraction.config import EXTRACTION_MODEL, GROQ_API_KEY
from src.models import Evidence, RagResult, Startup

from .schemas import LlmJudgment

MAX_EVIDENCES = 6
MAX_RAG_ITEMS = 5
MAX_CHARS_PER_EVIDENCE = 1200
MAX_CHARS_PER_RAG_ITEM = 500


def evidence_citation_id(evidence: Evidence, index: int) -> str:
    return evidence.id or f"E{index}"


def judge_startup_with_llm(
    startup: Startup,
    evidences: list[Evidence],
    rag_context: RagResult,
) -> LlmJudgment:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada para julgamento via LLM.")

    parser = PydanticOutputParser(pydantic_object=LlmJudgment)
    llm = ChatGroq(
        model=EXTRACTION_MODEL,
        temperature=0.0,
        max_tokens=1600,
        api_key=GROQ_API_KEY,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "Voce e um analista rigoroso do NVIDIA Startup AI Radar. "
                    "Classifique a startup e recomende produtos NVIDIA usando apenas as evidencias "
                    "e o contexto RAG fornecidos. "
                    "Nao invente fatos, nao use conhecimento externo e nao cite IDs inexistentes. "
                    "Se a base estiver fraca, reduza score, use label uncertain e explique as lacunas. "
                    "Cada afirmacao material deve ser sustentada por citations usando os IDs disponiveis, "
                    "como E1, E2, [1], [2]. "
                    "Signals devem ser curtos e concretos. "
                    "Recommendations devem conter produtos ou solucoes NVIDIA com justificativa objetiva."
                ),
            ),
            (
                "user",
                (
                    "Startup estruturada:\n{startup_block}\n\n"
                    "Evidencias validadas:\n{evidence_block}\n\n"
                    "Contexto RAG NVIDIA:\n{rag_block}\n\n"
                    "Regras adicionais:\n"
                    "- use no maximo 4 signals\n"
                    "- use no maximo 3 recommendations\n"
                    "- use no maximo 3 next_steps\n"
                    "- quando nao houver base suficiente para produto especifico, retorne recommendation vazia\n\n"
                    "{format_instructions}"
                ),
            ),
        ]
    )
    response = llm.invoke(
        prompt.format_messages(
            startup_block=_serialize_startup(startup),
            evidence_block=_serialize_evidences(evidences),
            rag_block=_serialize_rag_context(rag_context),
            format_instructions=parser.get_format_instructions(),
        )
    )
    return parser.parse(response.content)


def _serialize_startup(startup: Startup) -> str:
    payload = {
        "name": startup.name,
        "segment": startup.segment,
        "short_description": startup.short_description,
        "canonical_url": startup.canonical_url,
        "tags": startup.tags,
        "source_urls": startup.source_urls,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _serialize_evidences(evidences: list[Evidence]) -> str:
    rows = []
    for index, evidence in enumerate(evidences[:MAX_EVIDENCES], start=1):
        evidence_id = evidence_citation_id(evidence, index)
        excerpt = (evidence.content or evidence.excerpt or "")[:MAX_CHARS_PER_EVIDENCE]
        rows.append(
            {
                "citation_id": evidence_id,
                "url": evidence.url,
                "title": evidence.title,
                "source_type": evidence.source_type,
                "is_validated": evidence.is_validated,
                "source_priority": evidence.metadata.get("source_priority"),
                "excerpt": excerpt,
            }
        )
    return json.dumps(rows, ensure_ascii=False, indent=2)


def _serialize_rag_context(rag_context: RagResult) -> str:
    rows = []
    for item in rag_context.items[:MAX_RAG_ITEMS]:
        rows.append(
            {
                "citation_id": item.citation,
                "source_title": item.source_title,
                "source_url": item.source_url,
                "snippet": (item.snippet or "")[:MAX_CHARS_PER_RAG_ITEM],
                "retrieval_score": item.retrieval_score,
                "rerank_score": item.rerank_score,
            }
        )
    return json.dumps(
        {
            "summary": rag_context.summary,
            "items": rows,
        },
        ensure_ascii=False,
        indent=2,
    )

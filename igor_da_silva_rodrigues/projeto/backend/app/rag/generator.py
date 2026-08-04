from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Protocol

from app.core.contracts import validate_contract
from app.core.schemas import (
    AIMaturityOutput,
    NVIDIARecommendationOutput,
    RetrievedChunk,
)
from app.rag.config import RAGConfig


PAIN_TERMS = {
    "custo": ("custo", "cost", "efficiency"),
    "latencia": ("latencia", "latency", "real-time", "realtime", "performance", "throughput"),
    "escalabilidade": ("escala", "scalability", "scalable", "throughput"),
    "governanca": ("governanca", "governance", "compliance", "audit"),
    "privacidade": ("privacidade", "privacy", "sensitive data", "data protection"),
    "vendor_lockin": ("vendor lock-in", "portability", "self-hosted", "on-premises"),
}


class RecommendationGenerator(Protocol):
    def generate(
        self,
        profile: AIMaturityOutput,
        chunks: list[RetrievedChunk],
    ) -> NVIDIARecommendationOutput: ...


class GroundedRecommendationGenerator:
    def generate(
        self,
        profile: AIMaturityOutput,
        chunks: list[RetrievedChunk],
    ) -> NVIDIARecommendationOutput:
        by_technology: dict[str, list[RetrievedChunk]] = defaultdict(list)
        for chunk in chunks:
            if _chunk_is_grounded(chunk, profile):
                by_technology[chunk.metadata.tecnologia].append(chunk)

        profile_pains = _profile_pains(profile)
        detected_technologies = {
            item.lower()
            for values in profile.tecnologias_utilizadas.model_dump().values()
            for item in values
        }
        recommendations: list[dict[str, Any]] = []
        for technology, supporting in by_technology.items():
            pain_matches = sorted(
                pain
                for pain in profile_pains
                if any(_chunk_supports_pain(chunk, pain) for chunk in supporting)
            )
            if profile_pains and not pain_matches and technology.lower() not in detected_technologies:
                continue
            best_score = max(
                (chunk.rerank_score if chunk.rerank_score is not None else chunk.retrieval_score)
                for chunk in supporting
            )
            fit_score = min(1.0, 0.55 + max(0.0, best_score) * 0.25 + len(pain_matches) * 0.1)
            citation_signals = [term for pain in pain_matches for term in PAIN_TERMS[pain]] + [technology]
            citations = [_citation(chunk, citation_signals) for chunk in supporting[:3]]
            recommendation = {
                "tecnologia": technology,
                "fit_score": round(fit_score, 2),
                "justificativa": _grounded_justification(technology, supporting[0], pain_matches),
                "dores_atendidas": pain_matches,
                "citacoes": citations,
            }
            recommendations.append(recommendation)

        recommendations.sort(key=lambda item: item["fit_score"], reverse=True)
        recommended_technologies = {
            str(item["tecnologia"]) for item in recommendations[:5]
        }
        utilized_chunks = []
        seen_chunks: set[str] = set()
        for chunk in chunks:
            if chunk.metadata.tecnologia not in recommended_technologies:
                continue
            if chunk.chunk_id in seen_chunks:
                continue
            utilized_chunks.append(chunk.model_dump(mode="json"))
            seen_chunks.add(chunk.chunk_id)
            if len(utilized_chunks) == 5:
                break
        payload = {
            "startup": profile.startup,
            "recomendacoes": recommendations[:5],
            "chunks_utilizados": utilized_chunks,
            "aviso": None if recommendations else "Nenhum chunk compatível foi recuperado; nenhuma recomendação foi inferida.",
        }
        return validate_contract(NVIDIARecommendationOutput, payload)


class OpenAIRecommendationGenerator:
    def __init__(self, config: RAGConfig) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY não configurada")
        from langchain_openai import ChatOpenAI

        self.structured_model = ChatOpenAI(
            model=config.generator_model,
            temperature=0.1,
            max_tokens=2000,
        ).with_structured_output(NVIDIARecommendationOutput)

    def generate(
        self,
        profile: AIMaturityOutput,
        chunks: list[RetrievedChunk],
    ) -> NVIDIARecommendationOutput:
        context = "\n\n".join(
            f"[{chunk.chunk_id}] {chunk.metadata.url_fonte} | {chunk.metadata.tecnologia}\n{chunk.content}"
            for chunk in chunks
        )
        prompt = (
            "Recomende apenas tecnologias NVIDIA presentes nos chunks. "
            "Toda recomendação deve citar chunk_id, URL e trecho específico. "
            "Não use conhecimento externo nem invente benefícios.\n\n"
            f"PERFIL DA STARTUP:\n{profile.model_dump_json(indent=2)}\n\n"
            f"CHUNKS RECUPERADOS:\n{context}"
        )
        result = self.structured_model.invoke(prompt)
        return validate_contract(NVIDIARecommendationOutput, result)


def create_generator(config: RAGConfig) -> RecommendationGenerator:
    if config.generator_provider == "openai":
        return OpenAIRecommendationGenerator(config)
    return GroundedRecommendationGenerator()


def _profile_pains(profile: AIMaturityOutput) -> set[str]:
    text = " ".join(profile.necessidades_limitacoes).lower()
    mapping = {
        "custo": "custo",
        "latência": "latencia",
        "latencia": "latencia",
        "escala": "escalabilidade",
        "governança": "governanca",
        "governanca": "governanca",
        "privacidade": "privacidade",
        "vendor lock-in": "vendor_lockin",
        "dependência": "vendor_lockin",
    }
    return {canonical for signal, canonical in mapping.items() if signal in text}


def _citation(chunk: RetrievedChunk, signals: list[str]) -> str:
    content = " ".join(chunk.content.split())
    lower = content.lower()
    positions = [lower.find(signal.lower()) for signal in signals if lower.find(signal.lower()) >= 0]
    start = max(0, min(positions) - 70) if positions else 0
    excerpt = content[start : start + 280]
    return (
        f"[{chunk.chunk_id}] {chunk.metadata.url_fonte} - "
        f"{chunk.metadata.titulo_secao}: {excerpt}"
    )


def _chunk_is_grounded(chunk: RetrievedChunk, profile: AIMaturityOutput) -> bool:
    searchable_evidence = " ".join(
        (
            chunk.content,
            chunk.metadata.titulo_secao,
            chunk.metadata.url_fonte,
        )
    ).lower()
    technology_terms = {
        chunk.metadata.tecnologia.lower(),
        chunk.metadata.tecnologia.lower().replace("-", " "),
    }
    if any(term in searchable_evidence for term in technology_terms):
        return True
    return any(
        _chunk_supports_pain(chunk, pain)
        for pain in _profile_pains(profile)
    )


def _chunk_supports_pain(chunk: RetrievedChunk, pain: str) -> bool:
    if pain not in chunk.metadata.dores_relacionadas:
        return False
    content = chunk.content.lower()
    return any(term in content for term in PAIN_TERMS.get(pain, (pain,)))


def _grounded_justification(
    technology: str,
    chunk: RetrievedChunk,
    pain_matches: list[str],
) -> str:
    pains = ", ".join(pain_matches) if pain_matches else "o perfil técnico identificado"
    return (
        f"{technology} apresenta aderência a {pains}. A recomendação se apoia na seção "
        f"'{chunk.metadata.titulo_secao}' da documentação recuperada."
    )

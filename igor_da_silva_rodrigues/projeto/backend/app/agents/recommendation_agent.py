from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from app.core.contracts import validate_contract
from app.core.schemas import (
    RecommendationRefinementOutput,
    RecommendationRefinerInput,
    RetrievedChunk,
)


PHASE_ORDER = {"curto_prazo": 0, "medio_prazo": 1, "longo_prazo": 2}
TECHNOLOGY_GUIDANCE = {
    "NIM": ("curto_prazo", "baixa", ["ambiente de deploy homologado"]),
    "Triton": ("curto_prazo", "media", ["modelos versionados", "containerizacao"]),
    "TensorRT-LLM": ("medio_prazo", "alta", ["GPU NVIDIA", "CUDA", "modelo compativel"]),
    "NeMo": ("medio_prazo", "media", ["caso de uso generativo definido", "dados de avaliacao"]),
    "RAPIDS": ("curto_prazo", "media", ["GPU NVIDIA", "CUDA", "pipeline de dados"]),
    "CUDA": ("medio_prazo", "alta", ["GPU NVIDIA", "equipe de engenharia"]),
    "Riva": ("medio_prazo", "media", ["caso de uso de voz", "GPU NVIDIA"]),
    "Omniverse": ("longo_prazo", "alta", ["fluxo 3D ou simulacao definido"]),
    "Clara": ("longo_prazo", "alta", ["caso de uso de saude", "governanca de dados"]),
    "Isaac": ("longo_prazo", "alta", ["plataforma robotica", "ambiente de simulacao"]),
    "Morpheus": ("medio_prazo", "alta", ["telemetria de seguranca", "GPU NVIDIA"]),
    "AI Enterprise": ("medio_prazo", "media", ["infraestrutura NVIDIA homologada"]),
    "Inception": ("curto_prazo", "baixa", ["elegibilidade ao programa"]),
}
VERTICAL_SIGNALS = {
    "Riva": {"voz", "speech", "audio", "atendimento"},
    "Omniverse": {"3d", "design", "digital twin", "simulacao", "metaverso"},
    "Clara": {"saude", "health", "medic", "hospital", "biotech"},
    "Isaac": {"robot", "industr", "logistica", "manufatura", "agtech"},
    "Morpheus": {"seguranca", "cyber", "fraude", "security"},
}


class RecommendationAgent:
    """Refine grounded RAG recommendations without creating unsupported claims."""

    def __init__(self, store: Any | None = None, top_k: int = 5) -> None:
        self.store = store
        self.top_k = top_k

    def refine(
        self,
        payload: RecommendationRefinerInput | dict[str, Any],
    ) -> RecommendationRefinementOutput:
        data = validate_contract(RecommendationRefinerInput, payload)
        profile = data.classificacao_ia
        raw = data.recomendacao_rag
        alerts: list[str] = []

        if not raw.recomendacoes:
            if raw.aviso:
                alerts.append(raw.aviso)
            return validate_contract(
                RecommendationRefinementOutput,
                {
                    "startup": profile.startup,
                    "recomendacao_refinada": {
                        "tecnologias_priorizadas": [],
                        "roadmap": _empty_roadmap(),
                        "fit_score": 0.0,
                        "alertas": alerts,
                        "perguntas_startup": _questions(profile.necessidades_limitacoes, []),
                    },
                },
            )

        chunks_by_technology = _group_chunks(raw.chunks_utilizados)
        ranked: list[dict[str, Any]] = []
        startup_text = " ".join(
            str(value) for value in data.startup_profile.values() if value
        ).lower()
        for recommendation in raw.recomendacoes:
            technology = recommendation.tecnologia
            if technology == "Inception":
                alerts.append(
                    "NVIDIA Inception foi removido do roadmap tecnico e deve ser tratado em Inception Fit."
                )
                continue
            chunks = chunks_by_technology.get(technology, [])
            if not chunks and self.store is not None:
                chunks = self._retrieve_support(technology, profile.classificacao, alerts)
            phase, complexity, dependencies = TECHNOLOGY_GUIDANCE[technology]
            mismatch = _vertical_alert(technology, startup_text)
            if mismatch:
                alerts.append(mismatch)
            ranked.append(
                {
                    "tecnologia": technology,
                    "fase": phase,
                    "problema_resolvido": _problem_statement(
                        recommendation.dores_atendidas,
                        profile.necessidades_limitacoes,
                    ),
                    "beneficio": _grounded_benefit(technology, chunks, recommendation.justificativa),
                    "dependencias": dependencies,
                    "riscos": _risk_statement(complexity, bool(chunks)),
                    "complexidade": complexity,
                    "fontes_evidencia": _source_urls(chunks, recommendation.citacoes),
                    "raw_fit": recommendation.fit_score,
                }
            )

        ranked.sort(
            key=lambda item: (
                PHASE_ORDER[item["fase"]],
                {"baixa": 0, "media": 1, "alta": 2}[item["complexidade"]],
                -item["raw_fit"],
                item["tecnologia"],
            )
        )
        technologies: list[dict[str, Any]] = []
        for order, item in enumerate(ranked, start=1):
            item = dict(item)
            item.pop("raw_fit")
            item["ordem"] = order
            technologies.append(item)

        fit_score = _aggregate_fit(raw.recomendacoes, technologies, profile.nivel_maturidade)
        result = {
            "startup": profile.startup,
            "recomendacao_refinada": {
                "tecnologias_priorizadas": technologies,
                "roadmap": _build_roadmap(technologies),
                "fit_score": fit_score,
                "alertas": list(dict.fromkeys(alerts)),
                "perguntas_startup": _questions(
                    profile.necessidades_limitacoes,
                    [item["tecnologia"] for item in technologies],
                ),
            },
        }
        return validate_contract(RecommendationRefinementOutput, result)

    def _retrieve_support(
        self,
        technology: str,
        classification: str,
        alerts: list[str],
    ) -> list[RetrievedChunk]:
        try:
            store = self.store
            if store is None:
                return []
            results = store.hybrid_search(
                f"beneficios implementacao requisitos {technology}",
                top_k=self.top_k,
                profile=classification,
            )
            return [chunk for chunk in results if chunk.metadata.tecnologia == technology]
        except Exception as exc:
            alerts.append(f"Consulta complementar ao RAG falhou para {technology}: {exc}")
            return []


def refinar_recomendacao(
    payload: RecommendationRefinerInput | dict[str, Any],
    store: Any | None = None,
) -> dict[str, Any]:
    return RecommendationAgent(store=store).refine(payload).model_dump(mode="json")


def _group_chunks(chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    grouped: dict[str, list[RetrievedChunk]] = defaultdict(list)
    for chunk in chunks:
        grouped[chunk.metadata.tecnologia].append(chunk)
    return grouped


def _problem_statement(pains: list[str], needs: list[str]) -> str:
    if pains:
        return "Atender as necessidades relacionadas a " + ", ".join(pains) + "."
    if needs:
        return "Contribuir para a necessidade declarada: " + needs[0].rstrip(".") + "."
    return "Validar aderencia ao caso de uso e aos objetivos tecnicos da startup."


def _grounded_benefit(
    technology: str,
    chunks: list[RetrievedChunk],
    fallback: str,
) -> str:
    if not chunks:
        return f"Beneficio potencial ainda a validar. Fundamentacao disponivel: {fallback}"
    content = " ".join(chunks[0].content.split())
    content = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", content)
    content = re.sub(r"https?://\S+", "", content)
    sentences = re.split(r"(?<=[.!?])\s+", content)
    selected = next(
        (sentence for sentence in sentences if technology.lower() in sentence.lower()),
        sentences[0],
    )
    excerpt = selected[:280].rsplit(" ", 1)[0] if len(selected) > 280 else selected
    return f"Conforme a documentacao recuperada: {excerpt.strip()}"


def _source_urls(chunks: list[RetrievedChunk], citations: list[str]) -> list[str]:
    urls = [chunk.metadata.url_fonte for chunk in chunks]
    for citation in citations:
        match = re.search(r"https?://[^\s]+", citation)
        if match:
            urls.append(match.group(0).rstrip(".,;:)"))
    return list(dict.fromkeys(urls))


def _vertical_alert(technology: str, startup_text: str) -> str | None:
    signals = VERTICAL_SIGNALS.get(technology)
    if signals and not any(signal in startup_text for signal in signals):
        return (
            f"{technology} foi preservada, mas sua aderencia depende de confirmar "
            "um caso de uso compativel com a vertical."
        )
    return None


def _risk_statement(complexity: str, grounded: bool) -> str:
    base = {
        "baixa": "Validar elegibilidade, integracao e responsavel tecnico.",
        "media": "Exige prova de conceito, baseline e capacidade de operacao.",
        "alta": "Exige equipe especializada, infraestrutura compativel e rollout gradual.",
    }[complexity]
    if not grounded:
        return base + " Faltam trechos tecnicos adicionais no RAG para confirmar o escopo."
    return base


def _aggregate_fit(recommendations: list[Any], technologies: list[dict[str, Any]], maturity: int) -> float:
    average = sum(item.fit_score for item in recommendations) / len(recommendations)
    grounded_ratio = sum(bool(item["fontes_evidencia"]) for item in technologies) / len(technologies)
    maturity_factor = min(1.0, max(0.5, maturity / 4))
    return round(min(1.0, average * 0.65 + grounded_ratio * 0.25 + maturity_factor * 0.1), 2)


def _empty_roadmap() -> dict[str, dict[str, list[str]]]:
    return {
        "curto_prazo": {"tecnologias": [], "acoes": []},
        "medio_prazo": {"tecnologias": [], "acoes": []},
        "longo_prazo": {"tecnologias": [], "acoes": []},
    }


def _build_roadmap(technologies: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    roadmap = _empty_roadmap()
    for item in technologies:
        phase = item["fase"]
        roadmap[phase]["tecnologias"].append(item["tecnologia"])
        roadmap[phase]["acoes"].append(
            f"Validar {item['tecnologia']} em prova de conceito com baseline e criterio de aceite."
        )
    return roadmap


def _questions(needs: list[str], technologies: list[str]) -> list[str]:
    questions = [
        "Qual e o volume atual e projetado de inferencias ou processamento de dados?",
        "Quais sao os baselines atuais de latencia, custo, vazao e disponibilidade?",
        "A equipe opera workloads em containers e possui acesso a infraestrutura com GPU NVIDIA?",
    ]
    if not needs:
        questions.append("Quais limitacoes tecnicas mais afetam hoje o roadmap de IA?")
    if "Riva" in technologies:
        questions.append("Existe um caso de uso de voz ou audio em producao ou no roadmap?")
    return questions

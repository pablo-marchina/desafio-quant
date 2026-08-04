from __future__ import annotations

import re
from typing import Any

from app.core.contracts import validate_contract
from app.core.schemas import (
    ImpactEstimationOutput,
    ImpactEstimatorInput,
    PrioritizedTechnology,
    RetrievedChunk,
)


NOT_MEASURED = "A mensurar em prova de conceito contra o baseline atual da startup."
KPI_BY_TECHNOLOGY = {
    "NIM": ["tempo de deploy", "disponibilidade do endpoint", "custo por requisicao"],
    "Triton": ["p99 latency (ms)", "requisicoes por segundo", "GPU utilization (%)"],
    "TensorRT-LLM": ["tokens por segundo", "time to first token (ms)", "custo por 1k tokens"],
    "NeMo": ["taxa de respostas validas", "tempo de desenvolvimento", "incidentes de seguranca"],
    "RAPIDS": ["tempo de processamento", "volume processado por hora", "custo por job"],
    "CUDA": ["tempo de execucao", "GPU utilization (%)", "custo por workload"],
    "Riva": ["latencia de transcricao", "word error rate", "requisicoes por segundo"],
    "Omniverse": ["tempo de simulacao", "iteracoes por ciclo", "tempo de colaboracao"],
    "Clara": ["tempo de processamento", "qualidade do modelo", "custo por exame"],
    "Isaac": ["tempo de simulacao", "taxa de sucesso da tarefa", "ciclos de validacao"],
    "Morpheus": ["eventos processados por segundo", "tempo de deteccao", "falsos positivos"],
    "AI Enterprise": ["disponibilidade", "tempo de atualizacao", "incidentes operacionais"],
    "Inception": ["creditos e beneficios utilizados", "tempo ate prova de conceito"],
}


class ImpactEstimatorAgent:
    """Estimate impact while separating sourced benchmarks from hypotheses."""

    def __init__(self, store: Any | None = None, top_k: int = 8) -> None:
        self.store = store
        self.top_k = top_k

    def estimate(
        self,
        payload: ImpactEstimatorInput | dict[str, Any],
    ) -> ImpactEstimationOutput:
        data = validate_contract(ImpactEstimatorInput, payload)
        refined = data.recomendacao_refinada.recomendacao_refinada
        estimates = []
        uncertainties: list[str] = []
        kpis: list[str] = []
        supported = 0

        for item in refined.tecnologias_priorizadas:
            chunks = self._retrieve_benchmarks(
                item,
                data.classificacao_ia.classificacao,
                uncertainties,
            )
            evidence_texts = [item.beneficio] + [chunk.content for chunk in chunks]
            evidence_urls = list(
                dict.fromkeys(
                    item.fontes_evidencia + [chunk.metadata.url_fonte for chunk in chunks]
                )
            )
            quantitative = _quantitative_sentences(evidence_texts)
            technical = _technical_impact(quantitative)
            cost_projection = _cost_projection(quantitative, data.dados_adicionais)
            if cost_projection:
                technical["custo"] = cost_projection

            confidence = "baixa"
            if evidence_urls:
                confidence = "alta" if quantitative else "media"
                supported += 1
            if not quantitative:
                uncertainties.append(
                    f"{item.tecnologia}: nenhum benchmark quantitativo foi encontrado; "
                    "ganhos devem ser medidos em prova de conceito."
                )

            estimates.append(
                {
                    "tecnologia": item.tecnologia,
                    "impacto_tecnico": technical,
                    "impacto_negocio": _business_impact(item, bool(quantitative)),
                    "fontes_evidencia": evidence_urls,
                    "confianca": confidence,
                    "premissas": _assumptions(item, data.dados_adicionais),
                }
            )
            kpis.extend(KPI_BY_TECHNOLOGY[item.tecnologia])

        index = _aggregate_index(
            refined.fit_score,
            supported,
            len(refined.tecnologias_priorizadas),
            data.classificacao_ia.nivel_maturidade,
        )
        if not data.dados_adicionais:
            uncertainties.append(
                "Volume, custo atual e baseline operacional nao foram informados pela startup."
            )
        result = {
            "startup": data.classificacao_ia.startup,
            "estimativas_impacto": estimates,
            "indice_impacto_agregado": index,
            "kpis_sugeridos": list(dict.fromkeys(kpis)),
            "incertezas": list(dict.fromkeys(uncertainties)),
            "resumo_executivo": _executive_summary(
                data.classificacao_ia.startup,
                len(estimates),
                index,
                supported,
            ),
        }
        return validate_contract(ImpactEstimationOutput, result)

    def _retrieve_benchmarks(
        self,
        item: PrioritizedTechnology,
        classification: str,
        uncertainties: list[str],
    ) -> list[RetrievedChunk]:
        if self.store is None:
            return []
        try:
            results = self.store.hybrid_search(
                f"{item.tecnologia} benchmark latency throughput cost performance case study",
                top_k=self.top_k,
                profile=classification,
            )
            return [chunk for chunk in results if chunk.metadata.tecnologia == item.tecnologia]
        except Exception as exc:
            uncertainties.append(f"{item.tecnologia}: consulta de benchmark ao RAG falhou: {exc}")
            return []


def estimar_impacto(
    payload: ImpactEstimatorInput | dict[str, Any],
    store: Any | None = None,
) -> dict[str, Any]:
    return ImpactEstimatorAgent(store=store).estimate(payload).model_dump(mode="json")


def _quantitative_sentences(texts: list[str]) -> list[str]:
    signals = re.compile(
        r"(?:\d+(?:[.,]\d+)?\s*(?:%|x|ms|s\b|tokens?|req(?:uests?)?/s|usd|\$))",
        re.IGNORECASE,
    )
    found = []
    for text in texts:
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
            if signals.search(sentence):
                found.append(sentence[:500])
    return list(dict.fromkeys(found))


def _technical_impact(quantitative: list[str]) -> dict[str, str]:
    dimensions = {
        "latencia": ("latencia", "latency", "time to first token", "ms"),
        "custo": ("custo", "cost", "econom", "usd", "$"),
        "vazao": ("vazao", "throughput", "tokens", "requests", "req/s", "x"),
        "escalabilidade": ("escala", "scalab", "concorr", "batch"),
        "governanca_seguranca": ("govern", "segur", "security", "guardrail", "compliance"),
    }
    result = {}
    for dimension, terms in dimensions.items():
        matched = [sentence for sentence in quantitative if any(term in sentence.lower() for term in terms)]
        result[dimension] = " ".join(matched[:2]) if matched else NOT_MEASURED
    return result


def _cost_projection(quantitative: list[str], additional: dict[str, Any]) -> str | None:
    monthly_cost = additional.get("custo_atual_apis") or additional.get("custo_mensal_atual")
    if not isinstance(monthly_cost, (int, float)) or monthly_cost <= 0:
        return None
    for sentence in quantitative:
        if not any(term in sentence.lower() for term in ("custo", "cost", "econom")):
            continue
        match = re.search(r"(\d{1,3})\s*(?:-|–|a|to)\s*(\d{1,3})\s*%", sentence, re.IGNORECASE)
        if not match:
            continue
        low, high = sorted((int(match.group(1)), int(match.group(2))))
        if high > 100:
            continue
        monthly_low = monthly_cost * low / 100
        monthly_high = monthly_cost * high / 100
        return (
            f"Projecao condicionada ao benchmark citado: economia mensal entre "
            f"USD {monthly_low:,.2f} e USD {monthly_high:,.2f}; validar em prova de conceito."
        )
    return None


def _business_impact(item: PrioritizedTechnology, quantitative: bool) -> str:
    if quantitative:
        return (
            "Se o benchmark for reproduzido no workload real, o ganho tecnico pode liberar "
            "capacidade, reduzir friccao operacional e acelerar entregas de produto."
        )
    return (
        "Impacto de negocio ainda nao quantificavel. A prova de conceito deve relacionar "
        f"os KPIs de {item.tecnologia} a custo, experiencia do cliente e time-to-market."
    )


def _assumptions(item: PrioritizedTechnology, additional: dict[str, Any]) -> list[str]:
    assumptions = [
        "A carga de teste deve representar o workload de producao.",
        "A comparacao deve usar hardware, qualidade e disponibilidade equivalentes.",
    ]
    if item.dependencias:
        assumptions.append("Pre-requisitos disponiveis: " + ", ".join(item.dependencias) + ".")
    if additional:
        assumptions.append("Dados adicionais fornecidos pela startup devem ser confirmados.")
    return assumptions


def _aggregate_index(fit: float, supported: int, total: int, maturity: int) -> int:
    if total == 0:
        return 0
    evidence_ratio = supported / total
    return round(min(100, fit * 55 + evidence_ratio * 25 + (maturity / 5) * 20))


def _executive_summary(startup: str, technologies: int, index: int, supported: int) -> str:
    if technologies == 0:
        return f"Nao ha recomendacoes NVIDIA fundamentadas para estimar impacto em {startup}."
    return (
        f"{startup} possui {technologies} tecnologia(s) no roadmap, com indice interno de "
        f"potencial {index}/100. {supported} recomendacao(oes) possuem fonte documental; "
        "os ganhos devem ser confirmados contra baselines da startup."
    )

"""Comparativo de reranker (F7.4) — NeMo Retriever × Cohere Rerank (qualidade × custo × latência).

O brief nomeia a Cohere no §5.3; o build escolheu o **NeMo Reranking NIM** (dogfood/narrativa,
F3.6). A F7.4 fecha a lacuna de essa escolha estar justificada **por omissão**: mede os dois (e a
espinha lexical offline como piso) no **mesmo** conjunto de perguntas NVIDIA (F3.9) e nas três
dimensões que decidem um reranker — **qualidade**, **latência** e **custo** — p/ a F7.5 decidir
**com dados**.

Como cada dimensão é medida (sem pressuposto):

- **Qualidade**: reusa a avaliação RAGAS (F3.9/F7.3) com o reranker injetado e o **mesmo scorer**
  (`LexicalRagasMetrics`) p/ todos — o que muda entre as linhas é só a **ordem** que cada reranker
  impõe aos contextos, então context precision/recall comparam *reranking × reranking* de forma
  justa e reproduzível (o juiz LLM consolidado é a F7.3, ortogonal a este corte).
- **Latência**: tempo de parede **só do passo de rerank** (a recuperação F3.5 é compartilhada e fica
  fora do cronômetro), em ms por consulta — o custo de latência que o reranker adiciona ao pipeline.
- **Custo**: taxa de referência por 1k consultas (`COST_PER_1K_QUERIES_USD`) — preço da
  Cohere vs catálogo grátis/GPU amortizada do NeMo. Não medido em rede; é a tabela de preço.

**Espinha verde / make-it-real:** o default é **offline-safe** — só o `LexicalReranker` (piso,
sem rede). Os backends de rede (NeMo, Cohere) entram por `include_network=True` (CLI `--nv`/
`--cohere`) e **degradam limpo** (linha `available=False` com o motivo) quando a credencial/dep
falta — sem falsear número. O comparativo NeMo×Cohere **ao vivo** exige a chave NVIDIA + a **Cohere
trial key** e a dep `cohere`; via `python -m packages.eval.reranker_comparison --nv --cohere`.
"""

from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field

from packages.rag import (
    CohereReranker,
    HybridRetriever,
    LexicalReranker,
    NeMoReranker,
    Reranker,
    RerankerUnavailable,
    build_retriever,
)

from .ragas import (
    RETRIEVE_LIMIT,
    LexicalRagasMetrics,
    RagQuestion,
    evaluate_rag,
    load_rag_questions,
)

#: Custo de referência por 1k consultas de rerank (F7.4) — taxas públicas / política do build:
#: Cohere Rerank 3.5 ≈ US$ 2,00 / 1k searches (preço público); NeMo = catálogo grátis no build /
#: GPU amortizada self-hosted (0,0 com a ressalva); lexical é offline (sem API).
COST_PER_1K_QUERIES_USD: dict[str, float] = {
    "lexical-offline": 0.0,
    "nv-rerankqa": 0.0,
    "cohere-rerank": 2.0,
}

#: Ressalva do custo 0,0 do NeMo — não é "de graça", é amortizado (catálogo/GPU). Honestidade no §8.
_COST_NOTE: dict[str, str] = {
    "nv-rerankqa": "catálogo build.nvidia.com (grátis no build) / GPU amortizada self-hosted",
    "lexical-offline": "offline determinístico (sem API)",
}


class RerankerRow(BaseModel):
    """Uma linha do comparativo (F7.4): um reranker nas três dimensões + disponibilidade."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model: str
    available: bool = Field(description="False = backend de rede sem credencial/dep (degradou).")
    note: str = Field(default="", description="Motivo da indisponibilidade ou ressalva de custo.")
    faithfulness: float | None = Field(default=None, ge=0.0, le=1.0)
    answer_relevancy: float | None = Field(default=None, ge=0.0, le=1.0)
    context_precision: float | None = Field(default=None, ge=0.0, le=1.0)
    context_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_mean: float | None = Field(default=None, ge=0.0, le=1.0, description="Média RAGAS.")
    latency_ms_per_query: float | None = Field(default=None, ge=0.0, description="Só o rerank.")
    cost_per_1k_queries_usd: float | None = Field(default=None, ge=0.0)


class RerankerComparisonReport(BaseModel):
    """Comparativo NeMo×Cohere (×lexical) — qualidade/latência/custo no mesmo conjunto (F7.4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_questions: int = Field(ge=0)
    rows: tuple[RerankerRow, ...]
    best_quality_provider: str | None = Field(
        default=None, description="Entre os disponíveis, o de maior quality_mean (a decisão F7.5)."
    )


def candidate_rerankers(*, include_network: bool = False) -> dict[str, Reranker]:
    """Os rerankers do comparativo. Default = só o lexical (offline-safe); rede via flag.

    Os backends de rede são **construídos** sempre que pedidos (degradam só ao serem usados, na
    medição) — assim a linha indisponível ainda aparece no relatório com o motivo.
    """
    rerankers: dict[str, Reranker] = {"lexical-offline": LexicalReranker()}
    if include_network:
        rerankers["nv-rerankqa"] = NeMoReranker()
        rerankers["cohere-rerank"] = CohereReranker()
    return rerankers


def measure_reranker(
    reranker: Reranker,
    *,
    retriever: HybridRetriever,
    questions: Sequence[RagQuestion],
) -> RerankerRow:
    """Mede um reranker nas três dimensões; degrada limpo (linha `available=False`) sem infra.

    Latência isola o passo de rerank (recuperação compartilhada, fora do cronômetro); qualidade
    reusa a RAGAS com o mesmo scorer lexical (justo); custo vem da tabela de referência.
    """
    name = reranker.name
    cost = COST_PER_1K_QUERIES_USD.get(name)
    try:
        # Latência: recupera 1x por pergunta (compartilhado) e cronometra só o rerank.
        retrieved = [(q, retriever.search(q.question, limit=RETRIEVE_LIMIT)) for q in questions]
        start = perf_counter()
        for q, chunks in retrieved:
            reranker.rerank(q.question, chunks, top_n=None)
        latency = round((perf_counter() - start) * 1000 / len(questions), 3) if questions else 0.0
        # Qualidade: RAGAS com este reranker e o scorer lexical (mesma régua p/ todos).
        report = evaluate_rag(
            reranker=reranker, retriever=retriever, evaluator=LexicalRagasMetrics()
        )
        agg = report.aggregate
        return RerankerRow(
            provider=name,
            model=reranker.model,
            available=True,
            note=_COST_NOTE.get(name, ""),
            faithfulness=agg.faithfulness,
            answer_relevancy=agg.answer_relevancy,
            context_precision=agg.context_precision,
            context_recall=agg.context_recall,
            quality_mean=agg.mean,
            latency_ms_per_query=latency,
            cost_per_1k_queries_usd=cost,
        )
    except RerankerUnavailable as exc:
        return RerankerRow(
            provider=name,
            model=getattr(reranker, "model", ""),
            available=False,
            note=str(exc),
            cost_per_1k_queries_usd=cost,
        )


def compare_rerankers(
    rerankers: dict[str, Reranker] | None = None,
    *,
    retriever: HybridRetriever | None = None,
    questions: Sequence[RagQuestion] | None = None,
    include_network: bool = False,
) -> RerankerComparisonReport:
    """Roda o comparativo (F7.4) sobre as perguntas NVIDIA (F3.9): qualidade/latência/custo.

    Default offline-safe (só o lexical). `include_network=True` (ou `rerankers=` injetado) inclui o
    NeMo e o Cohere — degradam limpo sem credencial/dep. O vencedor de **qualidade** entre os
    **disponíveis** sai em `best_quality_provider` (a decisão que a F7.5 reporta).
    """
    rerankers = rerankers if rerankers is not None else candidate_rerankers(
        include_network=include_network
    )
    retriever = retriever or build_retriever()
    questions = questions if questions is not None else load_rag_questions()
    rows = tuple(
        measure_reranker(r, retriever=retriever, questions=questions) for r in rerankers.values()
    )
    available = [r for r in rows if r.available and r.quality_mean is not None]
    best = max(available, key=lambda r: r.quality_mean).provider if available else None
    return RerankerComparisonReport(
        n_questions=len(tuple(questions)), rows=rows, best_quality_provider=best
    )


def _print_report(report: RerankerComparisonReport) -> None:
    print(f"Comparativo de reranker (F7.4) — n={report.n_questions} perguntas NVIDIA")
    for r in report.rows:
        if not r.available:
            print(f"  - {r.provider:16} INDISPONÍVEL — {r.note}")
            continue
        mark = " *" if r.provider == report.best_quality_provider else "  "
        c = r.cost_per_1k_queries_usd
        cost = "n/d" if c is None else f"${c:.2f}/1k"
        print(
            f" {mark}{r.provider:16} qualidade={r.quality_mean:.3f} "
            f"(f={r.faithfulness:.2f} cp={r.context_precision:.2f} cr={r.context_recall:.2f}) "
            f"latência={r.latency_ms_per_query:.2f}ms/q  custo={cost}"
        )
    if report.best_quality_provider:
        print(f"  melhor qualidade (disponíveis): {report.best_quality_provider}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI do comparativo (F7.4): offline-safe por default; `--nv`/`--cohere` incluem os reais.

    O comparativo NeMo×Cohere ao vivo exige a chave NVIDIA + a Cohere trial key + a dep `cohere`;
    sem elas as linhas saem como INDISPONÍVEL (degradação limpa), nunca com número falso.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Comparativo de reranker NeMo×Cohere (F7.4).")
    parser.add_argument("--nv", action="store_true", help="inclui o NeMo Reranking NIM (rede/GPU).")
    parser.add_argument("--cohere", action="store_true", help="inclui o Cohere Rerank (trial key).")
    args = parser.parse_args(argv)

    rerankers: dict[str, Reranker] = {"lexical-offline": LexicalReranker()}
    if args.nv:
        rerankers["nv-rerankqa"] = NeMoReranker()
    if args.cohere:
        rerankers["cohere-rerank"] = CohereReranker()
    report = compare_rerankers(rerankers)
    _print_report(report)
    return 0


__all__ = [
    "COST_PER_1K_QUERIES_USD",
    "RerankerRow",
    "RerankerComparisonReport",
    "candidate_rerankers",
    "measure_reranker",
    "compare_rerankers",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())

"""Casos de aderência ao §5.5 (F4.8) — os 7 exemplos do brief como ground-truth do recommender.

Fecha o Entregável 4 (marco M4): assevera que o `recommender` (F4.2/F4.3) **produz o esperado**
para cada um dos 7 exemplos canônicos do §5.5 do brief — a "aderência ao brief". É o ponta-a-ponta
dos 7 (a `tests/test_recommend_rules.py` já cobre 5 deles **no nível de regra**, F4.1; aqui é o nó
inteiro, sobre todos os 7, consolidado como **harness reusável** que a F7.2 agrega em métrica).

Cada caso é um cenário (perfil + AIMI) que reproduz um exemplo do §5.5 e o conjunto de techs NVIDIA
que a recomendação deve conter (`expected_techs`). A avaliação roda o recommender end-to-end sobre
uma **recuperação de recall máximo** — uma citação para **toda** tech recomendável da KB (F3.1),
construída do manifesto real — em vez do `nvidia_rag` (F3.7). Essa é a decisão central do harness:

- **Isola a aderência da prescrição** (gap/setor → tech, F4.1) e o **invariante dos dois lados**
  (F4.5), que é o que o §5.5 mede ("o que recomendo a esta startup?"), do **recall do RAG lexical**
  — uma dimensão à parte, já coberta pela cobertura (F3.8: toda tech do §5.4 + MONAI é indexável/
  recuperável) e medida em qualidade pela RAGAS (F7.3). Dar ao recommender a evidência de todas as
  techs e deixá-lo **selecionar e cruzar** evita tanto a circularidade ("dizer a resposta ao RAG")
  quanto a fragilidade de depender do ranqueamento lexical para fazer surgir 5 techs num caso.
- **É honesto sobre um limite real**: `dados tabulares → RAPIDS/cuDF/cuML` é um eixo de setor
  **exclusivo** do mapa de regras (F4.1) — o `nvidia_rag` (F3.7) **não tem** consulta de setor
  tabular —, então só um harness desacoplado do RAG cobre esse exemplo ponta a ponta.

**Espinha verde offline/determinística** (como todo o F2–F4 e a RAGAS/F3.9): sem rede/GPU/LLM. O
caminho LLM do recommender (Nemotron-Super, F4.2) é plugável via `recommend=` e **só refina a
redação** — a aderência (quais techs) e a evidência dos dois lados continuam deterministas, então
o harness o aceita sem mudar o veredito. Tudo tipado (Pydantic) e o relatório é rastreável (§8).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field

from packages.agents import make_recommendations, recommendable_kb_techs
from packages.agents.recommender import RecommendFn
from packages.rag import load_kb_sources
from packages.schemas import (
    MAX_SCORE_WITHOUT_EVIDENCE,
    AIMIPillar,
    AIMIScore,
    Claim,
    Classification,
    Evidence,
    PillarScore,
    Recommendation,
    RetrievedChunk,
    StartupProfile,
)

#: Data fixa da evidência do lado-startup (offline determinístico, sem `now()` — igual ao resto do
#: projeto). A evidência NVIDIA é datada pelo snapshot do manifesto (F3.1) dentro do recommender.
_FETCHED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


class RecommendationCase(BaseModel):
    """Um dos 7 exemplos do §5.5 como ground-truth: o cenário (perfil + AIMI) + as techs esperadas.

    `pillars` são os 4 sub-scores do AIMI (P1 Data Moat, P2 Workflow Depth, P3 Technical
    Optimization, P4 Distribution Moat) que reproduzem o gap do exemplo; `setor`/`descricao` montam
    o perfil (o setor dispara a tech de domínio, §5.5). `expected_techs` são **substrings** dos
    rótulos de produto que a recomendação deve conter (ex.: "NVIDIA Riva" casa "NVIDIA Riva
    (ASR/TTS)") — verifica-se `expected ⊆ produzido` (subconjunto: o recommender pode prescrever
    mais, p.ex. uma tech de pilar além da de setor). `nota` documenta o que no exemplo **não** é
    tech do recommender (ROI/benchmark é F6; "batching" é um recurso do Triton, não item à parte).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    titulo: str
    gatilho: str = Field(description="O gatilho do §5.5 (gap/domínio) em PT-BR.")
    pillars: tuple[int, int, int, int] = Field(description="AIMI (P1, P2, P3, P4), cada um 0–25.")
    setor: str | None = None
    descricao: str | None = None
    expected_techs: tuple[str, ...] = Field(description="Substrings das techs que devem aparecer.")
    nota: str = ""

    def aimi(self) -> AIMIScore:
        """Monta o `AIMIScore` do cenário (pilar > 6 carrega evidência, como manda a RUBRICA §0)."""
        p1, p2, p3, p4 = self.pillars
        return AIMIScore(
            data_moat=_pillar(AIMIPillar.DATA_MOAT, p1),
            workflow_depth=_pillar(AIMIPillar.WORKFLOW_DEPTH, p2),
            technical_optimization=_pillar(AIMIPillar.TECHNICAL_OPTIMIZATION, p3),
            distribution_moat=_pillar(AIMIPillar.DISTRIBUTION_MOAT, p4),
            classificacao=Classification.AI_NATIVE,
        )

    def profile(self) -> StartupProfile:
        """Monta o `StartupProfile` do cenário — setor/descrição com evidência pública citável."""
        return StartupProfile(
            nome=self.titulo,
            setor=_claim(self.setor) if self.setor is not None else None,
            descricao=_claim(self.descricao) if self.descricao is not None else None,
        )


def _ev() -> Evidence:
    """Evidência pública do lado-startup (descrição/setor/pilar) — fixa e determinística."""
    return Evidence(
        url="https://startup.example",
        snippet="sinal público do perfil da startup",
        fetched_at=_FETCHED,
        content_hash="case55",
    )


def _claim(value: str) -> Claim[str]:
    return Claim[str](value=value, evidence=[_ev()])


def _pillar(pilar: AIMIPillar, score: int) -> PillarScore:
    # RUBRICA §0: score > 6 exige evidência; um gap (≤6, ausência) não a tem — o recommender
    # ancora esse lado no perfil público (descrição), como na espinha do F4.2/F4.3.
    ev = [_ev()] if score > MAX_SCORE_WITHOUT_EVIDENCE else []
    return PillarScore(pilar=pilar, score=score, justificativa="cenário §5.5 (F4.8)", evidencia=ev)


#: Os 7 exemplos canônicos do §5.5 do brief (a ordem e os gatilhos seguem o enunciado da F4.8).
SECTION_55_CASES: tuple[RecommendationCase, ...] = (
    RecommendationCase(
        id="voz",
        titulo="Startup de voz / call center",
        gatilho="produto de voz (ASR/TTS) sobre API externa — domínio voz + gap de inferência (P3)",
        pillars=(20, 20, 4, 22),
        setor="Call center e voz",
        descricao="assistente de voz e transcrição de fala construído sobre API externa de LLM",
        expected_techs=("NVIDIA Riva", "NVIDIA NIM"),
    ),
    RecommendationCase(
        id="dados_tabulares",
        titulo="Startup de dados tabulares / analytics",
        gatilho="pipelines de dados tabulares (ETL/ciência de dados) pesados — domínio tabular",
        pillars=(20, 20, 8, 22),
        setor="Plataforma de analytics",
        descricao="processa grandes volumes de dados tabulares (ETL e ciência de dados) na CPU",
        expected_techs=("NVIDIA RAPIDS", "cuDF", "cuML"),
    ),
    RecommendationCase(
        id="saude",
        titulo="Startup de saúde / healthtech",
        gatilho="IA clínica sobre API externa, cliente regulado — domínio saúde + gaps P3 e P4",
        pillars=(20, 20, 4, 8),
        setor="Saúde / healthtech",
        descricao=(
            "assistente clínico de diagnóstico sobre API externa que vende para hospitais regulados"
        ),
        expected_techs=(
            "NVIDIA Clara",
            "MONAI",
            "NVIDIA NIM",
            "NeMo Guardrails",
            "NVIDIA AI Enterprise",
        ),
    ),
    RecommendationCase(
        id="atendimento_api",
        titulo="Startup de atendimento via API",
        gatilho="produto 100% sobre API externa, voltado ao cliente — gap de inferência (P3) + P4",
        pillars=(20, 20, 4, 8),
        setor=None,
        descricao="produto de respostas ao cliente construído 100% sobre API externa de LLM",
        expected_techs=("NVIDIA NIM", "NeMo Guardrails", "NVIDIA Triton"),
        nota="O ROI/benchmark do atendimento é o GPU Graduation Engine (F6.9–F6.11), não uma tech.",
    ),
    RecommendationCase(
        id="robotica",
        titulo="Startup de robótica",
        gatilho="robótica/manufatura autônoma — domínio robótica (simulação + inferência na borda)",
        pillars=(20, 20, 10, 22),
        setor="Robótica industrial e manufatura autônoma",
        descricao="robôs autônomos para a indústria com percepção e navegação",
        expected_techs=("NVIDIA Isaac", "NVIDIA Omniverse"),
    ),
    RecommendationCase(
        id="latencia",
        titulo="Startup com gargalo de latência",
        gatilho="inferência com gargalo de latência/throughput — gap Technical Optimization (P3)",
        pillars=(20, 20, 3, 22),
        setor=None,
        descricao="API de inferência de LLM com gargalo de latência p95 sob carga concorrente",
        expected_techs=("TensorRT-LLM", "NVIDIA Triton"),
        nota="O dynamic batching é um recurso do Triton (na justificativa), não um item à parte.",
    ),
    RecommendationCase(
        id="governanca",
        titulo="Startup com requisito de governança",
        gatilho="venda enterprise com governança/auditoria — gap de Distribution Moat (P4)",
        pillars=(20, 20, 20, 4),
        setor=None,
        descricao="plataforma de IA para clientes enterprise que exigem governança e auditoria",
        expected_techs=("NeMo Guardrails", "NeMo Evaluator"),
    ),
)


@lru_cache(maxsize=1)
def _doc_source_by_tech() -> dict[str, object]:
    """tech → fonte `doc` do manifesto (F3.1), a 1ª de cada tech — base da citação sintética."""
    by_tech: dict[str, object] = {}
    for s in load_kb_sources():
        if s.source_type == "doc" and s.tech not in by_tech:
            by_tech[s.tech] = s
    return by_tech


def full_recall_retrieval() -> tuple[RetrievedChunk, ...]:
    """Recuperação de recall máximo: uma citação por tech recomendável da KB (F3.1), datável.

    Representa um RAG de recall perfeito — a evidência NVIDIA existe para **toda** tech que as
    regras (F4.1) podem prescrever (o que a cobertura F3.8 garante ser recuperável). O recommender
    ainda precisa **selecionar** (via `match_techs`) e **cruzar** por `kb_tech`; o harness não lhe
    diz a resposta, só não o faz refém do ranqueamento lexical. `chunk_id` casa o doc do manifesto
    para o recommender datar a `Evidence` pelo `captured_at` (determinístico, sem `now()`).
    """
    sources = _doc_source_by_tech()
    chunks: list[RetrievedChunk] = []
    for tech in sorted(recommendable_kb_techs()):
        s = sources.get(tech)
        if s is None:  # amarrado pelo test_every_rule_tech_exists_in_the_kb (F4.1) — defensivo
            continue
        chunks.append(
            RetrievedChunk(
                text=f"{tech}: trecho citável da base de conhecimento NVIDIA.",
                source_url=s.url,
                source_title=s.title,
                score=0.9,
                metadata={"chunk_id": f"{s.id}::00", "tech": tech, "source_type": "doc"},
            )
        )
    return tuple(chunks)


def _matches(expected: str, produced: str) -> bool:
    """`expected` casa `produced` se for substring (case-insensitive) do rótulo emitido."""
    return expected.casefold() in produced.casefold()


class CaseResult(BaseModel):
    """Resultado da avaliação de um caso §5.5 — aderência + invariante dos dois lados."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    titulo: str
    expected_techs: tuple[str, ...]
    produced_techs: tuple[str, ...]
    missing_techs: tuple[str, ...] = Field(description="Esperadas que não apareceram (vazio = ok).")
    both_sided: bool = Field(description="Toda recomendação tem evidência dos dois lados (F4.5).")
    passed: bool = Field(description="Aderência completa E dois lados em tudo.")


class RecommendationEvalReport(BaseModel):
    """Relatório de aderência ao §5.5 (F4.8) — agrega os 7 casos (a F7.2 consolida em métrica)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_cases: int
    n_passed: int
    adherence: float = Field(ge=0.0, le=1.0, description="Fração de casos com aderência completa.")
    per_case: tuple[CaseResult, ...]


def run_case(case: RecommendationCase, *, recommend: RecommendFn | None = None) -> CaseResult:
    """Roda o recommender sobre o cenário do caso e confere a aderência ao §5.5 + os dois lados.

    `recommend` é o adapter LLM injetável (default = espinha determinista offline); mesmo ligado, a
    aderência e a evidência continuam deterministas — o LLM só refina a redação (F4.2).
    """
    recs: list[Recommendation] = make_recommendations(
        case.aimi(), case.profile(), full_recall_retrieval(), recommend=recommend
    )
    produced = tuple(r.tech for r in recs)
    missing = tuple(
        want for want in case.expected_techs if not any(_matches(want, got) for got in produced)
    )
    both_sided = bool(recs) and all(r.evidencia_gap and r.evidencia_nvidia for r in recs)
    return CaseResult(
        case_id=case.id,
        titulo=case.titulo,
        expected_techs=case.expected_techs,
        produced_techs=produced,
        missing_techs=missing,
        both_sided=both_sided,
        passed=not missing and both_sided,
    )


def evaluate_recommendation_cases(
    *,
    cases: Sequence[RecommendationCase] | None = None,
    recommend: RecommendFn | None = None,
) -> RecommendationEvalReport:
    """Avalia os 7 casos do §5.5 e agrega o relatório de aderência (DoD F4 / consolidação F7.2)."""
    cases = cases if cases is not None else SECTION_55_CASES
    results = tuple(run_case(c, recommend=recommend) for c in cases)
    n = len(results)
    n_passed = sum(r.passed for r in results)
    return RecommendationEvalReport(
        n_cases=n,
        n_passed=n_passed,
        adherence=round(n_passed / n, 6) if n else 0.0,
        per_case=results,
    )


def _print_report(report: RecommendationEvalReport) -> None:
    print(
        f"Aderência §5.5 (F4.8): {report.n_passed}/{report.n_cases} casos "
        f"(adherence={report.adherence})"
    )
    for r in report.per_case:
        mark = "OK " if r.passed else "XX "
        detail = "" if r.passed else f" — faltou {list(r.missing_techs)} (2 lados={r.both_sided})"
        print(f"  {mark}{r.case_id}: {list(r.produced_techs)}{detail}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI da aderência ao §5.5 (F4.8): avalia offline e falha (exit 1) se algum caso não aderir."""
    report = evaluate_recommendation_cases()
    _print_report(report)
    return 0 if report.n_passed == report.n_cases else 1


__all__ = [
    "RecommendationCase",
    "SECTION_55_CASES",
    "full_recall_retrieval",
    "CaseResult",
    "RecommendationEvalReport",
    "run_case",
    "evaluate_recommendation_cases",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())

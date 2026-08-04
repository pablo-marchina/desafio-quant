"""DTOs da API TAPI (F5.2) — contratos de request/response dos endpoints HTTP.

Separados dos contratos de domínio (`packages.schemas`): aqui mora só o que cruza a
fronteira HTTP — o corpo do `POST /runs` e a projeção de empresa da lista (F5.4/F5.11) —
enquanto o `Briefing` (F4.4) e os enums (F0.5) são reusados direto na resposta.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from packages.schemas import ExecutionMode, HITLMode


class RunRequest(BaseModel):
    """Corpo do `POST /runs`: a consulta + o modo de execução/HITL (F2.3/F2.8)."""

    query: str = Field(
        min_length=1, description="Nome/domínio (single) ou setor/região (discovery)."
    )
    mode: ExecutionMode = ExecutionMode.SINGLE_COMPANY
    hitl: HITLMode = HITLMode.SYNC


class RunAccepted(BaseModel):
    """Resposta de enfileiramento (`POST /runs` e `/resume`): o `run_id` p/ acompanhar via SSE."""

    run_id: str
    status: str


class RunReviewOut(BaseModel):
    """Payload da revisão HITL de um run (F5.10): o que o gerente revisa antes do briefing.

    Projeta o `review_payload` (F2.8) lido do estado persistido (checkpoint, F2.2) — classe
    (§5.1) + AIMI + as techs recomendadas — quando o run pausou no interrupt sync. A tela de
    aprovação (F5.10) mostra isto e chama `POST /runs/{id}/resume` com a decisão do gerente.
    `awaiting_review` diz se o run está **de fato** parado esperando o humano (a UI distingue
    "pausado p/ revisar" de "já seguiu", ex.: ao recarregar a tela). Os campos de diagnóstico são
    opcionais: run offline sem extração sai com `None`/lista vazia — o payload nunca alucina.
    """

    run_id: str
    awaiting_review: bool
    query: str | None = None
    empresa: str | None = None
    classificacao: str | None = None
    aimi_total: int | None = None
    recomendacoes: list[str] = Field(default_factory=list)


class RunStatusOut(BaseModel):
    """Fase de um run p/ a UI reencontrar uma consulta longa ao voltar à tela (F5.3+).

    O trabalho roda no worker RQ (F2.10) e **sobrevive** à navegação — fechar a tela não para o
    run. Esta projeção diz à UI o que mostrar ao reabrir **sem pendurar no SSE** (o pub/sub de
    progresso não reentrega o que já passou): `running` (job na fila/executando → reabre o stream
    ao vivo), `awaiting_review` (pausado no HITL sync, F2.8 → painel de revisão), `done` (terminou
    — `run_status` carrega o desfecho real, ex.: completed/insufficient_data → hidrata do
    checkpoint), `failed` (job caiu) ou `unknown` (sem job nem checkpoint — run expirado/estranho).
    """

    run_id: str
    phase: str = Field(description="running | awaiting_review | done | failed | unknown")
    run_status: str | None = Field(
        default=None, description="Desfecho (valor de RunStatus) quando phase='done'."
    )


class CompanyOut(BaseModel):
    """Projeção de empresa para a lista (F5.4/F5.11): perfil + diagnóstico AIMI mais recente.

    Achata `Company` (§2) + o `Score` (AIMI/classe/inception_priority) do run mais recente, com
    as `tecnologias` que a startup usa (nomes normalizados dos sinais F1.11/F2.5) e as
    `nvidia_techs` recomendadas (F4.3) — as duas facetas de tech do filtro F5.11. Os campos de
    diagnóstico são opcionais: empresa coletada mas ainda não pontuada aparece sem AIMI.
    """

    id: int
    nome: str
    setor: str | None = None
    pais: str = "BR"
    website: str | None = None
    classificacao: str | None = None
    aimi_total: int | None = None
    inception_priority: int | None = None
    tecnologias: list[str] = Field(default_factory=list)
    nvidia_techs: list[str] = Field(default_factory=list)


class TechFacetsOut(BaseModel):
    """Tags disponíveis para os filtros de tech da lista (F5.11): o vocabulário controlado.

    `tech` são as tags que as startups da coorte **usam** (`Company.tecnologias`); `nvidia_tech`
    são as tags NVIDIA **recomendadas** (`Recommendation`). Já normalizadas e ordenadas — a UI
    monta os controles a partir delas e só envia ao `GET /companies` uma tag que existe (filtro
    determinístico, sem texto livre).
    """

    tech: list[str] = Field(default_factory=list)
    nvidia_tech: list[str] = Field(default_factory=list)


class EvidenceOut(BaseModel):
    """Fonte citável de um sub-score (tabela `evidence`, §8): o link que sustenta o pilar."""

    url: str
    snippet: str
    source_title: str | None = None


class DiscoverHitOut(BaseModel):
    """Uma empresa no resultado da descoberta: o perfil + por que casou (F3.10/F5.12).

    `empresa` é a projeção da lista (reusa `CompanyOut`); `similaridade` é o cosseno 0–1 com a
    pergunta quando o modo é **semântico** (texto livre), `None` no modo só-filtro; `citacao` é a
    fonte rastreável que sustenta o match (§8 — nada sem evidência).
    """

    empresa: CompanyOut
    similaridade: float | None = None
    citacao: EvidenceOut | None = None


class DiscoverOut(BaseModel):
    """Resposta do chat de descoberta da coorte (F3.10/F5.12).

    `entendido` ecoa como a pergunta em PT-BR foi interpretada (filtros captados); `resumo` é a
    frase de resposta; `modo` diz se a ordem veio do **filtro** (Inception Priority) ou do ranking
    **semântico** (relevância à busca em texto livre); `resultados` são os matches nessa ordem, cada
    um com a empresa + a citação que o sustenta. O front desenha como conversa.
    """

    pergunta: str
    entendido: str
    resumo: str
    modo: str = "filtro"
    resultados: list[DiscoverHitOut] = Field(default_factory=list)


class PillarOut(BaseModel):
    """Um pilar do AIMI no detalhe (F5.5): sub-score 0–25 + faixa + justificativa + fontes.

    `pilar` é a chave técnica (`AIMIPillar`, ex.: 'data_moat'); o rótulo PT-BR é da UI. `band`
    vem de `band_for` (RUBRICA §1). As `evidencias` são as linhas `evidence` do score com
    `field=<pilar>` — vazia até a persistência do AIMI gravá-las (a UI degrada sem links).
    """

    pilar: str
    score: int = Field(ge=0, le=25)
    band: str
    justificativa: str | None = None
    evidencias: list[EvidenceOut] = Field(default_factory=list)


class ROIOut(BaseModel):
    """ROI quantificado de uma recomendação (GPU Graduation Engine, F6) — opcional (F5.6).

    Projeta o `roi` JSON da `recommendation` (serializado de `ROIEstimate`, F0.5). Todos os
    campos são opcionais: a recomendação **degrada graciosamente** sem ROI (a UI mostra o cartão
    sem o número enquanto a matriz/benchmark do F6 não existir). Convenção de sinal: delta
    **negativo = melhora** (menos latência / menos custo).
    """

    throughput_speedup: float | None = None
    latency_p95_delta_pct: float | None = None
    cost_delta_pct: float | None = None
    baseline: str | None = None
    optimized: str | None = None
    benchmark_source: str | None = None
    is_live_run: bool = False


class RecommendationOut(BaseModel):
    """Cartão de recomendação no detalhe (§5.5/F5.6): tech + justificativas + evidência dos 2 lados.

    Projeta a `recommendation` (F4.3) com a **evidência dos dois lados** (tabela `evidence`:
    `field='gap'` lado startup / `field='nvidia'` lado KB) e o `roi` opcional (F6). `prioridade`/
    `complexidade` são os valores PT-BR do §5.5; `pilar_origem` é a chave técnica (`AIMIPillar`),
    com o rótulo PT-BR na UI. A lista vem ordenada por prioridade (alta→baixa), como no briefing.
    """

    tech: str
    prioridade: str
    complexidade: str
    justificativa_tecnica: str
    justificativa_negocio: str
    proxima_acao: str
    pilar_origem: str | None = None
    roi: ROIOut | None = None
    evidencia_gap: list[EvidenceOut] = Field(default_factory=list)
    evidencia_nvidia: list[EvidenceOut] = Field(default_factory=list)


class CompanyDetailOut(BaseModel):
    """Detalhe de uma startup (F5.5/F5.6): perfil + radar AIMI + cartões de recomendação.

    Estende a projeção da lista (`CompanyOut`) com a descrição/ano e o **breakdown** do AIMI —
    os 4 sub-scores, suas justificativas e as fontes citáveis (F5.5) — mais os **cartões de
    recomendação** (`recomendacoes`, F5.6) com evidência dos dois lados e ROI opcional.
    `pilares`/`recomendacoes` vêm vazias quando a empresa ainda não foi pontuada/recomendada
    (mesma degradação graciosa da lista: sem AIMI, sem radar; sem recomendação, sem cartão).
    `nvidia_techs` segue como o resumo (só os nomes) das techs recomendadas.
    """

    id: int
    nome: str
    setor: str | None = None
    pais: str = "BR"
    website: str | None = None
    descricao: str | None = None
    ano_fundacao: int | None = None
    classificacao: str | None = None
    aimi_total: int | None = None
    inception_priority: int | None = None
    confidence: float | None = None
    heuristic_version: str | None = None
    pilares: list[PillarOut] = Field(default_factory=list)
    nvidia_techs: list[str] = Field(default_factory=list)
    recomendacoes: list[RecommendationOut] = Field(default_factory=list)


class TraceUsageOut(BaseModel):
    """Rollup de tokens/custo de um run (`trace['usage']`, F2.9) — `None` em run offline sem LLM."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    cost_usd: float = 0.0


class TraceStepOut(BaseModel):
    """Um passo (nó) do grafo no trace do run (F5.7).

    `node` é a chave técnica do nó (`PIPELINE`, F2.1) — o rótulo PT-BR é da UI (reusa
    `PIPELINE_STEPS`). `status`: `done` (deixou artefato no estado persistido), `skipped` (o run
    terminou sem passar aqui — ramo terminal F2.12/F2.13, ou etapa opcional sem saída, ex.:
    `gpu_benchmark` sem ROI) ou `pending` (o run pausou/falhou antes de chegar). `summary` é um
    resumo factual do que o nó produziu (preenchido só nos passos `done`).
    """

    node: str
    status: str
    summary: str | None = None


class RunTraceOut(BaseModel):
    """Trace de um run para o viewer (F5.7): os passos dos agentes + rollup de custo + link.

    Reconstruído do **estado persistido** do run (checkpoint, F2.2): a espinha de nós (`PIPELINE`,
    F2.1) com o que cada um produziu — offline-reproduzível, sem depender do Langfuse no ar. Soma o
    `usage` (tokens/custo, F2.9), a nota de orçamento (F2.11), os `errors` rastreáveis e o
    `langfuse_url` (deep-trace, F0.8) quando o tracing está ligado. `404` quando o run não tem
    checkpoint.
    """

    run_id: str
    status: str
    prompt_version: str | None = None
    steps: list[TraceStepOut] = Field(default_factory=list)
    usage: TraceUsageOut | None = None
    budget_limited: bool = False
    errors: list[str] = Field(default_factory=list)
    langfuse_url: str | None = None


__all__ = [
    "RunRequest",
    "RunAccepted",
    "RunStatusOut",
    "RunReviewOut",
    "CompanyOut",
    "TechFacetsOut",
    "EvidenceOut",
    "PillarOut",
    "ROIOut",
    "RecommendationOut",
    "CompanyDetailOut",
    "TraceUsageOut",
    "TraceStepOut",
    "RunTraceOut",
]

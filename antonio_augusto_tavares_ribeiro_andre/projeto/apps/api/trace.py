"""Projeção do trace de um run (F5.7) — os passos dos agentes a partir do estado persistido.

O trace viewer (F5.7) mostra **o que cada agente do grafo produziu** num run. A fonte é o
`GraphState` persistido no checkpoint (F2.2) — offline-reproduzível, sem depender do Langfuse
estar no ar: cada nó da espinha (`PIPELINE`, F2.1) vira um passo cujo status é derivado da
presença do seu artefato no estado. O `langfuse_url` (deep-trace, F0.8) entra como link opcional
quando o tracing está ligado; o passo-a-passo aqui não depende dele.

Pura e testável: recebe o `GraphState` já carregado (o checkpoint é a dependência da API, ver
`deps.get_trace_loader`) e o `langfuse_url` já resolvido da config — não toca em I/O.
"""

from __future__ import annotations

from packages.agents.graph import PIPELINE
from packages.schemas import GraphState, RunStatus

from .schemas import RunTraceOut, TraceStepOut, TraceUsageOut

# Status terminais do run (F2.1/F2.12/F2.13): o run acabou. Um nó sem artefato num run terminal
# foi **pulado** (saltado por um ramo terminal, ou etapa opcional sem saída); num run ainda em
# curso (pending/running/awaiting_review) ele está **pendente** — não foi alcançado.
_TERMINAL = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.INSUFFICIENT_DATA,
        RunStatus.OUT_OF_SCOPE,
        RunStatus.FAILED,
    }
)


def _produced(state: GraphState) -> dict[str, bool]:
    """Por nó da espinha (F2.1): True se o nó deixou seu artefato no estado persistido.

    `evidence_validator` roda logo após o classifier (sem campo próprio) → herda o `aimi`;
    `human_review` só **conclui** no caminho normal (`completed`) — nos ramos terminais
    (F2.12/F2.13) o grafo salta direto ao briefing sem passar por ele, e no `awaiting_review`
    ele é o ponto de pausa (ainda pendente).
    """
    return {
        "search_planner": bool(state.search_terms or state.sources),
        "scraper": bool(state.raw_docs),
        "extractor": state.profile is not None,
        "classifier": state.aimi is not None,
        "evidence_validator": state.aimi is not None,
        "nvidia_rag": bool(state.retrieved),
        "recommender": bool(state.recommendations),
        "gpu_benchmark": state.benchmark is not None,
        "human_review": state.status is RunStatus.COMPLETED,
        "briefing": state.briefing is not None,
    }


def _summary(node: str, state: GraphState) -> str | None:
    """Resumo factual do que o nó produziu (só faz sentido nos passos `done`)."""
    if node == "search_planner":
        return f"{len(state.search_terms)} termos · {len(state.sources)} fontes"
    if node == "scraper":
        return f"{len(state.raw_docs)} documentos coletados"
    if node == "extractor":
        nome = state.profile.nome if state.profile else None
        return f"perfil: {nome}" if nome else "perfil extraído"
    if node == "classifier" and state.aimi is not None:
        return f"{state.aimi.classificacao.value} · AIMI {state.aimi.total}/100"
    if node == "evidence_validator":
        if state.retry_count:
            return f"{state.retry_count} recoleta(s) de evidência"
        return "evidências validadas"
    if node == "nvidia_rag":
        return f"{len(state.retrieved)} trechos da KB NVIDIA"
    if node == "recommender":
        return f"{len(state.recommendations)} tecnologias recomendadas"
    if node == "gpu_benchmark":
        return "ROI estimado" if state.benchmark is not None else None
    if node == "human_review":
        return "marcado para revisão" if state.needs_review else "aprovado"
    if node == "briefing":
        return "briefing pronto"
    return None


def build_run_trace(state: GraphState, *, langfuse_url: str | None = None) -> RunTraceOut:
    """Projeta o `GraphState` persistido no trace do run (F5.7): passos + custo + link Langfuse.

    Deriva o status de cada nó da presença do seu artefato (`_produced`): com artefato → `done`;
    sem artefato, `skipped` se o run já é terminal, senão `pending`. O `usage`/`budget` vêm do
    `trace` carimbado pelo `stamp_usage` (F2.9/F2.11) — ausentes num run offline sem LLM.
    """
    produced = _produced(state)
    terminal = state.status in _TERMINAL
    steps = [
        TraceStepOut(
            node=node,
            status="done" if produced[node] else ("skipped" if terminal else "pending"),
            summary=_summary(node, state) if produced[node] else None,
        )
        for node in PIPELINE
    ]

    raw_usage = state.trace.get("usage")
    usage = TraceUsageOut(**raw_usage) if raw_usage else None
    budget_limited = bool(state.trace.get("budget", {}).get("limited"))

    return RunTraceOut(
        run_id=state.run_id,
        status=state.status.value,
        prompt_version=state.prompt_version,
        steps=steps,
        usage=usage,
        budget_limited=budget_limited,
        errors=list(state.errors),
        langfuse_url=langfuse_url,
    )

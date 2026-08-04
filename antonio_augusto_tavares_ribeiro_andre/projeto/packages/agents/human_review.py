"""Nó **human_review** (F2.8): interrupt HITL antes do briefing.

Penúltimo nó do grafo (ARQUITETURA §3), entre o `gpu_benchmark` (F6) e o `briefing`
(F4.4). É o ponto de **revisão humana da classificação/recomendação** antes de o briefing
executivo ser escrito: um analista do Inception confere o diagnóstico (classe §5.1 + AIMI)
e as recomendações enquanto ainda dá para corrigir o rumo do run.

**Controle por modo (lê `state.hitl`, F2.3):**
- `sync` (*single-company lookup*): **interrupt bloqueante** — o grafo pausa e espera o
  humano. Retoma via `Command(resume=<decisão>)`; o valor da decisão é o retorno do
  `interrupt()` e fica registrado em `trace["human_review"]` (auditável). Exige um
  **checkpointer** (F2.2) — sem ele o LangGraph não sabe pausar/retomar; o worker (F2.10)
  sempre fornece um.
- `auto` (**batch / cohort builder F1.14**): **não bloqueia a fila** — só marca o run com
  `needs_review=True` e segue para o briefing. Um humano revisa o lote depois,
  assíncronamente, filtrando os runs marcados.

**Decisão de design (política headless b/d, igual F2.3–F2.7):** **offline é o default** — o
gate `settings.hitl_enabled` nasce **off**, então o nó é um **no-op limpo** (`{}`) e a espinha
roda ponta a ponta sem pausa (M2/DoD, runs reprodutíveis F2.14; todos os testes da fase seguem
verdes). A pausa humana é **plugável** atrás da flag **ou** do parâmetro injetável `enabled=`
(testes/worker). Gatear por flag — e não pela mera presença do checkpointer — é de propósito:
o checkpointer (F2.2) habilita resume/retry sozinho, então um run persistido **sem** revisão
humana (CI, reprocesso em lote) não deve travar à espera de gente; a flag separa "persisto o
estado" de "exijo um humano no loop".

O nó **não** roteia (sem `Command goto`): a saída é estática para o `briefing` em todos os
caminhos (offline, auto e o pós-resume do sync) — quem decide o briefing terminal é a F4.4
(e os terminais alternativos F2.12/F2.13 ramificam antes, no evidence_validator/classifier).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.types import interrupt

from packages.config import get_settings
from packages.schemas import HITLMode

if TYPE_CHECKING:
    from packages.schemas import GraphState


def review_payload(state: GraphState) -> dict:
    """Resumo do que o humano revisa (JSON-serializável p/ checkpoint/SSE): classe + AIMI + recs.

    Lê só o que já está no estado neste ponto da espinha (perfil/AIMI/recomendações). Campos
    ausentes (run offline sem extração) viram `None`/lista vazia — o payload nunca alucina.
    """
    profile = state.profile
    aimi = state.aimi
    return {
        "run_id": state.run_id,
        "query": state.query,
        "empresa": profile.nome if profile is not None else None,
        "classificacao": aimi.classificacao.value if aimi is not None else None,
        "aimi_total": aimi.total if aimi is not None else None,
        "recomendacoes": [r.tech for r in state.recommendations],
    }


def human_review(state: GraphState, *, enabled: bool | None = None) -> dict:
    """F2.8 — revisão humana antes do briefing; modo via `state.hitl`. Devolve update parcial.

    - Desligado (offline/default, `hitl_enabled` off): no-op (`{}`) — espinha verde (M2/DoD).
    - `auto`: não bloqueia — marca `needs_review=True` e segue (batch/cohort F1.14).
    - `sync`: `interrupt()` bloqueante — pausa p/ o humano; retoma via `Command(resume=...)` e
      registra a decisão em `trace["human_review"]`. Requer checkpointer (F2.2).
    """
    enabled = get_settings().hitl_enabled if enabled is None else enabled
    if not enabled:
        return {}  # sem pausa humana (default) → espinha verde (M2/DoD)

    if state.hitl is HITLMode.AUTO:
        return {"needs_review": True}  # batch/cohort: marca, não bloqueia a fila

    decision = interrupt(review_payload(state))  # sync: pausa bloqueante (single-company)
    return {"trace": {**state.trace, "human_review": decision}}


__all__ = ["review_payload", "human_review"]

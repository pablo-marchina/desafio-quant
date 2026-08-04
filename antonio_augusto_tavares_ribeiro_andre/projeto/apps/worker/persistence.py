"""Persistência pós-run das saídas do grafo nas tabelas relacionais (F2.10 · F0.6).

Fecha o último elo do "de verdade": depois que o worker (F2.10) roda o grafo, esta camada
lê o `GraphState` **final** e **materializa o run inteiro numa única transação** — a linha
`run` (âncora de FK + auditoria), a `company` (perfil, F1.10), o `score` (AIMI, F6.13) e as
`recommendation` (F4.7), cada uma com sua evidência polimórfica (§8). Sem isto o run corria
mas não deixava rastro: `persist_score`/`persist_recommendations` existiam (e eram testadas em
isolamento), mas **nenhum run real as chamava** — a lista `GET /companies` (F5.4) ficava vazia.

**Por que pós-run (e não um hook por nó):** ler o estado final num só ponto resolve o
`company_id` localmente (a `company` sai do `persist_profile`, e score/recs penduram nela) e
mantém **uma transação atômica** — sem propagar o `company_id` entre nós nem casá-lo com a
serialização do checkpointer (F2.2). O estado já carrega tudo que as três peças exigem
(`profile`/`aimi`/`recommendations`), produzido **antes** do `human_review` (F2.8), então
persistir vale igual para o run completo e para o run pausado para revisão.

**Ordem (FK do schema F0.6):** `run` → `company` (`company.run_id → run.id`) → `score`/
`recommendation` (ambos `run_id → run.id` e `company_id → company.id`). Por isso a linha `run`
é gravada e *flushada* primeiro; só então `persist_profile` insere a company de onde sai o
`company_id` que score/recs exigem.

**Escopo BR / terminais (degrada sem alucinar):** `persist_profile` aplica o escopo BR (F1.10)
e devolve `None` p/ um perfil fora de escopo (F2.13) — aí nada de company/score/recs é gravado
(fica só a linha `run`, marcando o desfecho). Run sem perfil (espinha offline, ou "dados
insuficientes" F2.12) grava **só** a linha `run`.

**Idempotente** (mesmo ethos das peças que orquestra): re-rodar a persistência do mesmo run não
duplica — `run` casa por `id`, `company` por CNPJ>domínio>nome (F1.10), `score` por
`(run, empresa)` (F6.13) e `recommendation` por `(run, empresa, tech)` (F4.7). Assim o worker
pode reprocessar um run (retry, ou o resume do HITL) sem inflar linhas. **`flush`, não
`commit`:** a transação é do caller (o job, F2.10).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from packages.agents.persistence import persist_recommendations, persist_score
from packages.db.models import Run
from packages.schemas import RunStatus
from packages.scraping.persistence import persist_profile

if TYPE_CHECKING:
    from sqlmodel import Session

    from packages.schemas import GraphState


def _run_status(state: GraphState) -> RunStatus:
    """Status a gravar na linha `run` — fiel ao estado, com **uma** tradução (F2.8/F2.10).

    O briefing (F4.4) e os terminais (F2.12/F2.13) sempre cravam um status final
    (`completed`/`insufficient_data`/`out_of_scope`); só a **pausa do HITL sync** (F2.8), que
    interrompe *antes* do briefing, deixa o estado devolvido ainda em `RUNNING`. Mapeia esse
    caso para `awaiting_review` — a responsabilidade que a F2.8 delegou ao worker (F2.10). No
    resume o briefing crava `completed` e o re-persist (idempotente) atualiza a linha.
    """
    return RunStatus.AWAITING_REVIEW if state.status is RunStatus.RUNNING else state.status


def upsert_run(session: Session, state: GraphState) -> Run:
    """Upsert idempotente da linha `run` por `run.id` — âncora de FK + auditoria do run.

    Em miss insere; em hit (retry/resume) **enriquece** a linha existente. `flush` p/ que a
    linha exista na transação antes da `company` (FK `company.run_id → run.id`). O `error`
    concatena as notas rastreáveis do estado (orçamento F2.11, persistência do extractor, …).
    """
    run = session.get(Run, state.run_id)
    if run is None:
        run = Run(id=state.run_id, query=state.query)
        session.add(run)
    run.query = state.query
    run.mode = state.mode
    run.hitl = state.hitl
    run.status = _run_status(state)
    run.briefing_status = state.briefing.status if state.briefing is not None else None
    run.prompt_version = state.prompt_version
    run.retry_count = state.retry_count
    run.error = "\n".join(state.errors) if state.errors else None
    session.flush()
    return run


def persist_run_state(session: Session, state: GraphState) -> Run:
    """Materializa o run inteiro a partir do `GraphState` final (run + company + score + recs).

    Grava a linha `run` (sempre) e, quando o perfil está presente **e em escopo BR**, a company
    (F1.10) + o AIMI (F6.13) + as recomendações (F4.7) penduradas nela, cada uma com a evidência
    polimórfica (§8). Devolve a linha `run`. **`flush`, não `commit`:** a transação é do caller
    (o job, F2.10) — assim o run inteiro grava de forma atômica (ou nada).
    """
    run = upsert_run(session, state)

    profile = state.profile
    if profile is None:
        return run  # espinha offline / "dados insuficientes" (F2.12) → só a linha run

    company = persist_profile(session, profile, run_id=state.run_id)
    if company is None:
        return run  # fora de escopo BR (F2.13) → não materializa company/score/recs

    if state.aimi is not None:
        persist_score(session, state.aimi, company_id=company.id, run_id=state.run_id)
    if state.recommendations:
        persist_recommendations(
            session, state.recommendations, company_id=company.id, run_id=state.run_id
        )
    return run


__all__ = ["persist_run_state", "upsert_run"]

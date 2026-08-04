"""Evidence Validator (nó do grafo): decide se há evidência suficiente.

Heurística SEM LLM: conta quantas respostas do checklist ficaram "inconclusivo".
Se forem muitas E ainda não recoletamos, pede uma nova rodada de coleta — o grafo
volta ao scraper (ciclo), que na 2ª tentativa coleta MAIS páginas (e usa o fallback
de navegador se a coleta vier fraca). O guard MAX_RETRIES evita loop infinito.

É este ciclo que torna o grafo de fato agêntico (não uma chain): ele reage à
qualidade do próprio resultado e decide reagir.
"""

from __future__ import annotations

from graph.state import StartupState

MAX_INCONCLUSIVOS = 4  # de 6 perguntas; a partir daqui, evidência é fraca
MAX_RETRIES = 1        # no máximo 1 recoleta (evita loop e gasto)


def _conta_inconclusivos(checklist: list[dict]) -> int:
    """Quantas respostas do checklist começam com 'inconcl' (inconclusivo)."""
    return sum(
        1 for item in checklist
        if str(item.get("resposta", "")).lower().startswith("inconcl")
    )


def evidence_validator_node(state: StartupState) -> dict:
    """Marca 'revalidar' quando a evidência é fraca e ainda cabe uma recoleta."""
    inconclusivos = _conta_inconclusivos(state.get("checklist", []))
    retries = state.get("retries", 0)

    if inconclusivos >= MAX_INCONCLUSIVOS and retries < MAX_RETRIES:
        return {"revalidar": True, "retries": retries + 1}
    return {"revalidar": False}

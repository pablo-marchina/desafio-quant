"""Funções de roteamento do grafo — as decisões das arestas condicionais.

Cada função recebe o estado e devolve o NOME do próximo nó. Concentrar as
decisões aqui mantém o pipeline.py focado só na montagem do grafo, e deixa
explícito onde o fluxo deixa de ser linear (o que torna o grafo agêntico).
"""

from __future__ import annotations

from agents.scraper import MIN_CHARS_MINIMO
from graph.state import StartupState


def route_after_scraper(state: StartupState) -> str:
    """Logo após a coleta: se veio quase nada, desvia para 'dados insuficientes'.

    Evita rodar extractor + classifier + recommender + briefing (4 chamadas de LLM)
    em cima de um texto vazio — típico de site SPA/JS que não rende conteúdo.
    Acima do piso, segue o caminho normal (extractor).
    """
    if len(state.get("raw_text", "")) < MIN_CHARS_MINIMO:
        return "insufficient_data"
    return "extractor"


def route_after_validator(state: StartupState) -> str:
    """Depois da validação de evidências. Três saídas:

    1. Evidência fraca (revalidar=True) → volta ao 'scraper' (ciclo/recoleta).
    2. Non-AI (nível 0) → 'briefing' direto (não há stack NVIDIA a recomendar).
    3. Demais níveis (1 a 3) → 'nvidia_rag' (caminho completo).

    Aceita o nível como número (0) ou texto ("0"). Na dúvida, caminho completo.
    """
    if state.get("revalidar"):
        return "scraper"
    if str(state.get("level")) == "0":
        return "briefing"
    return "nvidia_rag"

"""Grafo LangGraph que orquestra os agentes da pipeline.

Fluxo: START → search_planner → scraper → [roteamento] → extractor → classifier → [roteamento] → ... → END.
O grafo NÃO é linear — tem dois pontos de decisão (é o que o torna agêntico):

1. Depois do scraper: se a coleta veio praticamente vazia (site SPA/JS ou URL não
   encontrada), desvia para 'insufficient_data' e encerra sem gastar LLM.
2. Depois do classifier, o Evidence Validator decide: se a evidência é fraca (muitos
   "inconclusivo"), o grafo VOLTA ao scraper (CICLO/recoleta com mais páginas);
   senão, Non-AI (0) vai direto ao briefing e os demais seguem para o RAG.

O primeiro nó (search_planner) descobre a URL a partir do nome, quando ela não é
informada. As decisões ficam em graph/routing.py. O estado (StartupState) vai sendo
preenchido por cada nó ao longo do caminho.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.briefing import briefing_node
from agents.classifier import classifier_node
from agents.evidence_validator import evidence_validator_node
from agents.extractor import extractor_node
from agents.github import github_node
from agents.nvidia_rag import nvidia_rag_node
from agents.recommender import recommender_node
from agents.scraper import scraper_node
from agents.search_planner import search_planner_node
from graph.routing import route_after_scraper, route_after_validator
from graph.state import StartupState


def insufficient_data_node(state: StartupState) -> dict:
    """Nó de desvio: coleta insuficiente → encerra com um resultado honesto.

    Não chama LLM. Em vez de classificar/recomendar sem base (e gastar 4 chamadas),
    devolve um briefing claro de 'dados insuficientes'. Quando o fetcher de navegador
    do P1 existir, este será o ponto natural para um fallback real de coleta.
    """
    nome = state.get("startup_name", "a startup")
    url = (state.get("url") or "").strip()
    if not url:
        # O Search Planner não conseguiu descobrir o site oficial.
        motivo = (
            "não foi possível localizar o site oficial automaticamente "
            "(o Search Planner não encontrou uma URL confiável)"
        )
        proximo = (
            "informar a URL do site manualmente, ou habilitar busca web no "
            "Search Planner (P1)"
        )
    else:
        # A URL existe, mas a coleta veio quase vazia.
        motivo = (
            f"a coleta pública de {url} trouxe conteúdo insuficiente (provável site "
            "SPA/JavaScript, que só renderiza o conteúdo no navegador)"
        )
        proximo = (
            "coletar via fetcher de navegador (previsto no P1) ou informar uma "
            "URL/fonte com conteúdo legível"
        )
    briefing = (
        "# Briefing não gerado — dados insuficientes\n\n"
        f"Para **{nome}**, {motivo}. A análise foi interrompida para não gerar "
        "classificação e recomendações sem base.\n\n"
        f"**Próximo passo:** {proximo}."
    )
    return {
        "level_name": "Não classificado (dados insuficientes)",
        "briefing": briefing,
    }


def build_graph():
    """Monta e compila o grafo de agentes, com os dois pontos de roteamento."""
    builder = StateGraph(StartupState)

    # Registra os nós (cada um é uma função que recebe e atualiza o estado).
    builder.add_node("search_planner", search_planner_node)
    builder.add_node("scraper", scraper_node)
    builder.add_node("extractor", extractor_node)
    builder.add_node("github", github_node)
    builder.add_node("classifier", classifier_node)
    builder.add_node("evidence_validator", evidence_validator_node)
    builder.add_node("nvidia_rag", nvidia_rag_node)
    builder.add_node("recommender", recommender_node)
    builder.add_node("briefing", briefing_node)
    builder.add_node("insufficient_data", insufficient_data_node)

    builder.add_edge(START, "search_planner")
    builder.add_edge("search_planner", "scraper")

    # 1ª aresta condicional: coleta vazia → curto-circuito; senão → extractor.
    builder.add_conditional_edges(
        "scraper",
        route_after_scraper,
        {"extractor": "extractor", "insufficient_data": "insufficient_data"},
    )
    builder.add_edge("insufficient_data", END)

    builder.add_edge("extractor", "github")
    builder.add_edge("github", "classifier")
    builder.add_edge("classifier", "evidence_validator")

    # 2ª aresta condicional + CICLO: evidência fraca → volta ao scraper (recoleta);
    # Non-AI (0) → briefing direto; demais níveis → caminho completo (RAG).
    builder.add_conditional_edges(
        "evidence_validator",
        route_after_validator,
        {"scraper": "scraper", "nvidia_rag": "nvidia_rag", "briefing": "briefing"},
    )

    builder.add_edge("nvidia_rag", "recommender")
    builder.add_edge("recommender", "briefing")
    builder.add_edge("briefing", END)

    return builder.compile()

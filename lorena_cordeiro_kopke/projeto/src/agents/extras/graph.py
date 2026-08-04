"""
Montagem e compilação do grafo LangGraph de recomendação de tecnologias NVIDIA.

Uso básico:
    from agents.extras.graph import criar_grafo

    grafo = criar_grafo()
    resultado = grafo.invoke(
        {"empresa_id": 42},
        config={"configurable": {"thread_id": "empresa-42-run-1"}},
    )
    print(resultado["output_final"])

Uso com checkpointer externo (ex: SqliteSaver em produção):
    from langgraph.checkpoint.sqlite import SqliteSaver
    checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
    grafo = criar_grafo(checkpointer=checkpointer)

Retomar run interrompido:
    # O mesmo thread_id retoma do último checkpoint salvo.
    resultado = grafo.invoke(
        None,
        config={"configurable": {"thread_id": "empresa-42-run-1"}},
    )
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.extras.nodes import (
    buscar_e_reranquear,
    carregar_perfil,
    checar_json_valido,
    explicar_negocio,
    explicar_tecnico,
    finalizar_sem_resultado,
    kit_inicio_node,
    montar_query,
    roadmap_adocao_node,
    rotear_apos_busca,
    salvar_resultado,
    sintese_executiva_node,
    validar_json,
)
from agents.extras.state import EstadoRecomendacao


def criar_grafo(checkpointer=None):
    """
    Compila o grafo de recomendação.

    Args:
        checkpointer: instância de checkpointer do LangGraph.
                      Padrão: MemorySaver (in-memory, adequado para dev/testes).
                      Em produção, passar SqliteSaver ou PostgresSaver.
    """
    grafo = StateGraph(EstadoRecomendacao)

    # ── Registro de nós ───────────────────────────────────────────────────────
    grafo.add_node("carregar_perfil",     carregar_perfil)
    grafo.add_node("montar_query",        montar_query)
    grafo.add_node("buscar_e_reranquear", buscar_e_reranquear)

    # LLM 1 — dois branches com prompt distinto, mesma estrutura de saída
    grafo.add_node("explicar_tecnico",    explicar_tecnico)
    grafo.add_node("explicar_negocio",    explicar_negocio)
    grafo.add_node("validar_json",        validar_json)

    # LLMs 2-4 — sequência linear após LLM 1 validado
    grafo.add_node("sintese_executiva",   sintese_executiva_node)
    grafo.add_node("roadmap_adocao",      roadmap_adocao_node)
    grafo.add_node("kit_inicio",          kit_inicio_node)

    # Persistência e encerramento
    grafo.add_node("salvar_resultado",    salvar_resultado)
    grafo.add_node("sem_resultado",       finalizar_sem_resultado)

    # ── Fluxo principal ───────────────────────────────────────────────────────
    grafo.set_entry_point("carregar_perfil")
    grafo.add_edge("carregar_perfil", "montar_query")
    grafo.add_edge("montar_query",    "buscar_e_reranquear")

    # ÚNICO conditional edge de buscar_e_reranquear.
    # Funde ciclo de qualidade + roteamento por perfil em uma função.
    # Dois add_conditional_edges do mesmo nó fonte não são permitidos —
    # o LangGraph sobrescreve o primeiro silenciosamente.
    grafo.add_conditional_edges(
        "buscar_e_reranquear",
        rotear_apos_busca,
        {
            "re_buscar":        "buscar_e_reranquear",
            "sem_resultado":    "sem_resultado",
            "explicar_tecnico": "explicar_tecnico",
            "explicar_negocio": "explicar_negocio",
        },
    )

    grafo.add_edge("explicar_tecnico", "validar_json")
    grafo.add_edge("explicar_negocio", "validar_json")

    # Retry de JSON inválido.
    # Não adicionar add_edge("validar_json", ...) aqui — conflitaria com este conditional edge.
    grafo.add_conditional_edges(
        "validar_json",
        checar_json_valido,
        {
            "valido":         "sintese_executiva",
            "retry_tecnico":  "explicar_tecnico",
            "retry_negocio":  "explicar_negocio",
            "falha":          "sem_resultado",
        },
    )

    grafo.add_edge("sintese_executiva", "roadmap_adocao")
    grafo.add_edge("roadmap_adocao",    "kit_inicio")
    grafo.add_edge("kit_inicio",        "salvar_resultado")
    grafo.add_edge("salvar_resultado",  END)
    grafo.add_edge("sem_resultado",     END)

    # ── Compilação com checkpointer ───────────────────────────────────────────
    # MemorySaver como padrão: não persiste entre processos, mas habilita
    # interrupt_before/interrupt_after e recovery dentro da mesma sessão.
    cp = checkpointer if checkpointer is not None else MemorySaver()
    return grafo.compile(checkpointer=cp)

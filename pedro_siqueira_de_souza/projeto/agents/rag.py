"""NVIDIA RAG Agent — sétima estação do grafo.

O Evidence Validator entrega startups com perfil estruturado e confiança
validada. Este nó consulta a BASE DE CONHECIMENTO NVIDIA (Qdrant + Cohere
Rerank) para, a cada startup, recuperar os trechos de tecnologia NVIDIA mais
relevantes ao PERFIL dela. É o insumo que o Recommendation Agent (próximo) vai
cruzar para sugerir a stack — e os trechos já vêm com proveniência (tech + url)
para virar CITAÇÃO no briefing.

Decisões de design (alinhadas ao resto do grafo):
  - Uma consulta RAG POR STARTUP: o contexto recuperado é focado no perfil
    individual, sem contaminação entre empresas (mesma disciplina do
    extractor/classifier). Batching fica como otimização futura.
  - Reusa `retrieve_and_rerank` (rag.rerank): o nó não conhece Qdrant/Cohere
    direto — fala com a função do pipeline RAG, que os testes trocam por um
    fake (mesma "costura" do get_llm/fetch_static).
  - Perfil POBRE (só metadata, sem descrição/sinais) => NÃO consulta: sem
    matéria-prima, a query seria ruído e recuperaria trechos genéricos. O jeito
    honesto é não perguntar, registrando o motivo.
  - Erro POR STARTUP: uma consulta que falha vira contexto vazio + log, não
    derruba as demais.
"""
from loguru import logger

from agents.state import RadarState
from rag.rerank import retrieve_and_rerank

# Quantos trechos NVIDIA guardar por startup (depois do rerank).
TOP_N_POR_STARTUP = 4


def _build_query(startup: dict) -> str | None:
    """Monta a query de busca a partir do perfil estruturado da startup.

    Junta os campos que descrevem a NECESSIDADE técnica (o que a startup faz e
    com qual IA/stack), para casar semanticamente com a doc das tecnologias
    NVIDIA. Retorna None se não houver perfil aproveitável (só nome/metadata).
    """
    partes: list[str] = []
    if startup.get("description"):
        partes.append(startup["description"])
    if startup.get("sector"):
        partes.append(f"Setor: {startup['sector']}")
    if startup.get("ai_signals"):
        partes.append("Sinais de IA: " + "; ".join(startup["ai_signals"]))
    if startup.get("tech_stack"):
        partes.append("Stack atual: " + ", ".join(startup["tech_stack"]))

    # Só nome/metadata, sem nada que descreva a necessidade técnica -> não vale
    # consultar (recuperaria trechos genéricos e enganosos).
    if not partes:
        return None
    return ". ".join(partes)


def rag_node(state: RadarState) -> dict:
    """Nó 7 do grafo: recupera contexto NVIDIA relevante para cada startup."""
    validadas = state.get("validated_startups", [])

    contextos: list[dict] = []
    com_contexto = 0
    for v in validadas:
        startup = v["classified"]["startup"]
        name = startup.get("name", "")
        query = _build_query(startup)

        if query is None:
            contextos.append(
                {"name": name, "query": None, "chunks": [],
                 "note": "perfil insuficiente para RAG"}
            )
            continue

        try:
            chunks = retrieve_and_rerank(query, top_n=TOP_N_POR_STARTUP)
        except Exception:  # uma startup não pode derrubar as outras
            logger.exception("rag falhou em {}", name)
            contextos.append(
                {"name": name, "query": query, "chunks": [],
                 "note": "falha ao consultar a base NVIDIA"}
            )
            continue

        contextos.append(
            {"name": name, "query": query,
             "chunks": [c.model_dump() for c in chunks]}
        )
        com_contexto += 1

    return {
        "rag_contexts": contextos,
        "messages": [
            (
                "ai",
                f"[rag] {com_contexto}/{len(validadas)} startups com contexto "
                f"NVIDIA recuperado (top {TOP_N_POR_STARTUP} por startup)",
            )
        ],
    }

"""NVIDIA RAG Agent: busca na base NVIDIA as tecnologias relevantes ao perfil da startup.

Monta uma query a partir dos dados estruturados da startup e recupera (via Qdrant,
do Bloco 2) os trechos de tecnologias NVIDIA mais próximos em significado.
"""

from __future__ import annotations

from graph.state import StartupState
from rag.retrieval import search
from rag.vector_store import get_client


def _clean(value) -> str:
    """Normaliza um campo do 'structured' em texto; descarta vazio/'inconclusivo'."""
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    value = str(value or "").strip()
    return "" if value.lower() in ("", "inconclusivo", "none") else value


def _build_query(state: StartupState) -> str:
    """Monta a query de busca a partir do perfil TÉCNICO da startup.

    Em vez de achatar tudo (inclusive o nome, que é ruído e não casa com os docs
    NVIDIA), descreve em linguagem natural O QUE a empresa faz e COMO usa IA — que
    é o que bate com os casos de uso das tecnologias NVIDIA (voz, dados tabulares,
    serving, saúde...). Produto e uso de IA vêm primeiro por concentrarem o sinal.
    """
    structured = state.get("structured", {})
    produto = _clean(structured.get("produto"))
    usa_ia = _clean(structured.get("usa_ia"))
    setor = _clean(structured.get("setor"))
    techs = _clean(structured.get("tecnologias_citadas"))
    sinais = _clean(structured.get("sinais_time_tecnico"))

    partes = []
    if produto:
        partes.append(f"Produto: {produto}.")
    if usa_ia:
        partes.append(f"Uso de IA: {usa_ia}.")
    if setor:
        partes.append(f"Setor: {setor}.")
    if techs:
        partes.append(f"Tecnologias usadas: {techs}.")
    if sinais:
        partes.append(f"Perfil técnico do time: {sinais}.")
    return " ".join(partes).strip()


def _dedup_por_tecnologia(chunks: list[dict], top_n: int = 5) -> list[dict]:
    """Mantém só o melhor chunk (maior score) de cada tecnologia.

    Os chunks já vêm ordenados por score desc, então o primeiro de cada tecnologia
    é o melhor. Evita o top-5 virar '3x AI Enterprise' e dá tecnologias distintas
    ao recommender. Devolve as top_n tecnologias distintas.
    """
    melhor_por_tech: dict[str, dict] = {}
    for chunk in chunks:
        tech = chunk.get("technology")
        if tech and tech not in melhor_por_tech:
            melhor_por_tech[tech] = chunk
    return list(melhor_por_tech.values())[:top_n]


def nvidia_rag_node(state: StartupState) -> dict:
    """Monta a busca a partir do perfil e recupera os trechos NVIDIA relevantes.

    Busca vetorial por cosseno num pool amplo (20) e depois faz dedup por tecnologia,
    devolvendo até 5 tecnologias DISTINTAS. O reranker (rag/reranker.py) existe como
    opção fora do fluxo (a query por perfil técnico deixou o cosseno preciso o
    bastante).
    """
    query = _build_query(state) or state.get("startup_name", "")
    client = get_client()
    candidates = search(client, query, limit=20)
    chunks = _dedup_por_tecnologia(candidates, top_n=5)
    return {"nvidia_context": chunks}

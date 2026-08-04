import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from pipeline.config.settings import TOP_K_RAG, RERANK_TOP_N
from busca_hibrida import busca_hibrida
from rerank import rerank


def _construir_query(startup: dict) -> str:
    nome = startup.get("nome", "")
    produto = startup.get("produto_principal", "") or ""
    ramo = startup.get("ramo_principal", "") or ""
    gaps = startup.get("gaps_identificados", [])
    gap_principal = gaps[0] if gaps else ""

    if produto and gap_principal:
        return f"{produto} startup {ramo} que {gap_principal}"
    if produto:
        return f"{produto} startup {ramo}"
    return f"startup {ramo} {' '.join(gaps)}"


def _avaliar_relevancia(chunk: dict, startup: dict) -> str | None:
    tech = chunk.get("tech", "").lower()
    descricao = (startup.get("descricao", "") or "").lower()
    produto = (startup.get("produto_principal", "") or "").lower()
    gaps = " ".join(startup.get("gaps_identificados", [])).lower()

    termos_relevantes = [descricao, produto, gaps]
    texto_chunk = chunk.get("texto", chunk.get("text", "")).lower()

    for termo in termos_relevantes:
        if termo and any(palavra in texto_chunk for palavra in termo.split()[:5]):
            return f"Chunk relacionado a {tech}: contém termos encontrados no perfil da startup"

    return None


def run_rag_agent(startups_validadas: list[dict]) -> list[dict]:
    recomendacoes = []

    for startup in startups_validadas:
        if startup.get("low_confidence"):
            continue

        nome = startup.get("nome", "desconhecida")
        print(f"[RAG Agent] Buscando tecnologias para: {nome}")

        query = _construir_query(startup)
        candidatos = busca_hibrida(query, top_k=TOP_K_RAG)
        if not candidatos:
            continue

        resultados = rerank(query, candidatos, top_n=RERANK_TOP_N)

        chunks_aprovados = []
        for r in resultados:
            if r.get("relevance_score", 0) < 1e-6:
                continue

            motivo = _avaliar_relevancia(r, startup)
            chunks_aprovados.append({
                "tech": r.get("tech", ""),
                "category": r.get("category", ""),
                "url": r.get("url", ""),
                "relevance_score": r.get("relevance_score", 0),
                "texto_resumido": r.get("text", "")[:300],
                "motivo_relevancia": motivo or f"Score de relevância: {r.get('relevance_score', 0):.2f}"
            })

        if chunks_aprovados:
            recomendacoes.append({
                "startup_id": startup.get("startup_id"),
                "startup_nome": nome,
                "ramo": startup.get("ramo_principal"),
                "gaps": startup.get("gaps_identificados", []),
                "chunks_aprovados": chunks_aprovados
            })

        import time
        time.sleep(1)

    print(f"[RAG Agent] {len(recomendacoes)} startups com recomendações geradas")
    return recomendacoes

import argparse
import json
import sys
import os
from loguru import logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.graph.graph import build_graph
from pipeline.graph.state import AgentState
from pipeline.config.settings import MAX_STARTUPS_PER_RUN

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <cyan>{message}</cyan>", level="INFO")
logger.add("pipeline.log", rotation="10 MB", level="DEBUG", format="{time} | {level} | {message}")


def carregar_setores() -> list[dict]:
    with open("pipeline/config/setores.json", "r", encoding="utf-8") as f:
        return json.load(f)


def run_skip_scraping(setores: list[str] | None = None) -> dict:
    from pipeline.db.connection import fetch_all, fetch_one
    from pipeline.agents.classifier import run_classifier
    from pipeline.agents.evidence_validator import run_evidence_validator
    from pipeline.agents.rag_agent import run_rag_agent
    from pipeline.agents.recommendation_agent import run_recommendation_agent
    from pipeline.agents.briefing_agent import run_briefing_agent

    logger.info("Modo --skip-scraping: carregando startups do banco sem classificação/recomendação")

    where_setor = ""
    params: list = []
    if setores:
        placeholders = ",".join("?" for _ in setores)
        where_setor = f"AND s.setor IN ({placeholders})"
        params.extend(setores)

    rows_sem_class = fetch_all(
        f"""SELECT s.id, s.nome, s.website, s.setor, s.descricao,
                   s.produto_principal, s.cidade, s.estagio, s.email_contato
            FROM startups s
            WHERE s.id NOT IN (
                SELECT DISTINCT startup_id FROM classificacoes
            )
            {where_setor}
            ORDER BY s.created_at ASC
            LIMIT 50""",
        tuple(params)
    )
    logger.info(f"Startups sem classificação: {len(rows_sem_class)}")

    if rows_sem_class:
        logger.info(f"Classificando {len(rows_sem_class)} startups...")
        classificadas = run_classifier(rows_sem_class, setor_relevance=0.5)
        if classificadas:
            for c in classificadas:
                sid = c.get("startup_id")
                if sid and sid in {s["id"] for s in rows_sem_class}:
                    orig = next(s for s in rows_sem_class if s["id"] == sid)
                    c["descricao"] = orig.get("descricao", "") or ""
                    c["produto_principal"] = orig.get("produto_principal", "") or ""
        else:
            logger.warning("Nenhuma startup classificada (limite Cohere?)")
    else:
        classificadas = []

    sem_recom = fetch_all(
        f"""SELECT s.id, s.nome, s.website, s.setor, s.descricao,
                   s.produto_principal, s.cidade, s.estagio, s.email_contato
            FROM startups s
            WHERE s.id IN (
                SELECT DISTINCT startup_id FROM classificacoes
            )
            AND s.id NOT IN (
                SELECT DISTINCT startup_id FROM recomendacoes
            )
            {where_setor}
            ORDER BY s.created_at ASC
            LIMIT 50""",
        tuple(params)
    )
    logger.info(f"Startups com classificação mas sem recomendação: {len(sem_recom)}")

    sem_brief = fetch_all(
        f"""SELECT s.id, s.nome, s.website, s.setor, s.descricao,
                   s.produto_principal, s.cidade, s.estagio, s.email_contato
            FROM startups s
            WHERE s.id IN (
                SELECT DISTINCT startup_id FROM recomendacoes
            )
            AND s.id NOT IN (
                SELECT DISTINCT startup_id FROM briefings
            )
            {where_setor}
            ORDER BY s.created_at ASC
            LIMIT 50""",
        tuple(params)
    )
    logger.info(f"Startups com recomendação mas sem briefing: {len(sem_brief)}")

    if sem_recom:
        for s in sem_recom:
            clas = fetch_one(
                "SELECT * FROM classificacoes WHERE startup_id = ? ORDER BY classificado_em DESC LIMIT 1",
                (s["id"],)
            )
            if clas:
                s["startup_id"] = s["id"]
                s["ai_classification"] = clas["ai_classification"]
                s["ramo_principal"] = clas["ramo_principal"]
                s["usa_nvidia"] = clas["usa_nvidia"]
                s["nvidia_confidence"] = clas["nvidia_confidence"]
                s["gaps_identificados"] = json.loads(clas["gaps_identificados"]) if clas.get("gaps_identificados") else []
                s["score_fit_nvidia"] = clas["score_fit_nvidia"]
                s["justificativa"] = clas["justificativa"]

        classificadas.extend(sem_recom)

    briefings = []

    if classificadas:
        logger.info(f"Total a processar: {len(classificadas)}")
        validadas = run_evidence_validator(classificadas)
        validas = [s for s in validadas if not s.get("low_confidence")]
        logger.info(f"Validadas: {len(validadas)}, válidas: {len(validas)}")

        recomendacoes = run_rag_agent(validas)
        if recomendacoes:
            finais = run_recommendation_agent(recomendacoes)
            briefings = run_briefing_agent(finais)

    if sem_brief:
        logger.info(f"Processando {len(sem_brief)} startups com recomendação mas sem briefing...")
        rec_para_brief = []
        for s in sem_brief:
            s["startup_id"] = s["id"]
            recs_db = fetch_all(
                "SELECT * FROM recomendacoes WHERE startup_id = ? ORDER BY rank ASC",
                (s["id"],)
            )
            recs_list = [
                {
                    "rank": r["rank"],
                    "tecnologia": r["tecnologia"],
                    "categoria": r["categoria"],
                    "justificativa_tecnica": r["justificativa_tecnica"],
                    "justificativa_negocio": r["justificativa_negocio"],
                    "nivel_prioridade": r["nivel_prioridade"],
                    "complexidade_implementacao": r["complexidade_implementacao"],
                    "melhor_encaixe": r.get("melhor_encaixe"),
                    "proxima_acao_sugerida": r["proxima_acao_sugerida"],
                    "evidencias_usadas": json.loads(r["evidencias_usadas"]) if isinstance(r.get("evidencias_usadas"), str) else r.get("evidencias_usadas", []),
                    "url_referencia": r["url_referencia"]
                }
                for r in recs_db
            ]
            if recs_list:
                rec_para_brief.append({
                    "startup_id": s["id"],
                    "startup_nome": s["nome"],
                    "recomendacoes": recs_list
                })
        if rec_para_brief:
            briefings_extra = run_briefing_agent(rec_para_brief)
            briefings.extend(briefings_extra)
            logger.info(f"Briefings extras: {len(briefings_extra)}")

    if not classificadas and not sem_brief:
        logger.warning("Nenhuma startup para processar")

    logger.info(f"Resumo: {len(briefings)} briefings gerados")
    return {"startups_coletadas": classificadas, "briefings": briefings, "erros": []}


def run_pipeline(setor_alvo: str) -> dict:
    logger.info("Iniciando pipeline NVIDIA Startup AI Radar")
    logger.info(f"Setor alvo: {setor_alvo}")

    initial_state: AgentState = {
        "setor_alvo": setor_alvo,
        "consulta_usuario": None,
        "queries_geradas": [],
        "startups_coletadas": [],
        "erros": [],
        "startups_classificadas": [],
        "startups_validadas": [],
        "recomendacoes_rag": [],
        "recomendacoes_finais": [],
        "briefings": [],
        "etapa_atual": "",
        "iteracao": 0
    }

    try:
        graph = build_graph()
        logger.info("Grafo LangGraph compilado com sucesso")

        resultado = graph.invoke(initial_state)
        logger.info("Pipeline executado com sucesso")

        briefings = resultado.get("briefings", [])
        erros = resultado.get("erros", [])
        logger.info(f"Resumo: {len(resultado.get('startups_coletadas', []))} startups coletadas, "
                     f"{len(briefings)} briefings gerados, {len(erros)} erros")

        return resultado

    except Exception as e:
        logger.error(f"Falha na execução do pipeline: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="NVIDIA Startup AI Radar Pipeline")
    parser.add_argument("--setor", type=str, help="ID do setor (ex: healthtech)")
    parser.add_argument("--all-setores", action="store_true", help="Processar todos os setores")
    parser.add_argument("--startup-id", type=str, help="Reprocessar startup específica")
    parser.add_argument("--fase0-only", action="store_true", help="Executar apenas a Fase 0")
    parser.add_argument("--skip-scraping", action="store_true", help="Pular scraping, usar dados do banco")

    args = parser.parse_args()

    if args.fase0_only:
        logger.info("Modo --fase0-only: executando scripts da Fase 0")
        import subprocess
        scripts = ["coletar.py", "enriquecer.py", "limpar.py", "chunking.py", "embeddings.py", "indexar_qdrant.py"]
        for script in scripts:
            caminho = os.path.join("src", script)
            logger.info(f"Executando {caminho}...")
            subprocess.run([sys.executable, caminho], cwd="src")
        logger.info("Fase 0 concluída")
        return

    if args.skip_scraping:
        setores_alvo = None
        if args.setor:
            setores_alvo = [args.setor]
        resultado = run_skip_scraping(setores=setores_alvo)
        logger.info(f"Backfill concluído: {len(resultado.get('briefings', []))} briefings")
        return

    if args.setor:
        run_pipeline(setor_alvo=args.setor)
        return

    setores = carregar_setores()
    for setor in setores:
        setor_id = setor["id"]
        logger.info(f"Processando setor: {setor['nome']} ({setor_id})")
        try:
            run_pipeline(setor_alvo=setor_id)
        except Exception as e:
            logger.error(f"Erro no setor {setor_id}: {e}")


if __name__ == "__main__":
    main()

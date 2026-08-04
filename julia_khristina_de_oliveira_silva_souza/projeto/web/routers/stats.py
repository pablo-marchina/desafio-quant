from fastapi import APIRouter
from pipeline.db.connection import fetch_one, fetch_all

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats():
    total = fetch_one("SELECT COUNT(*) as total FROM startups") or {}
    ai_native = fetch_one(
        "SELECT COUNT(*) as total FROM classificacoes WHERE ai_classification = 'ai-native'"
    ) or {}
    com_recomendacao = fetch_one(
        "SELECT COUNT(DISTINCT startup_id) as total FROM recomendacoes"
    ) or {}
    score_medio = fetch_one(
        "SELECT AVG(score_fit_nvidia) as media FROM classificacoes"
    ) or {}
    ultimas_24h = fetch_one(
        "SELECT COUNT(*) as total FROM startups WHERE datetime(created_at) > datetime('now', '-1 day')"
    ) or {}
    distribuicao_setor = fetch_all("""
        SELECT s.setor, COUNT(*) as total
        FROM startups s
        GROUP BY s.setor
        ORDER BY total DESC
    """)

    sem_email = fetch_one(
        "SELECT COUNT(*) as total FROM startups WHERE email_contato IS NULL OR email_contato = ''"
    ) or {}
    sem_cidade = fetch_one(
        "SELECT COUNT(*) as total FROM startups WHERE cidade IS NULL OR cidade = ''"
    ) or {}
    incompletas = fetch_one(
        """SELECT COUNT(*) as total FROM startups
           WHERE (email_contato IS NULL OR email_contato = '')
              OR (cidade IS NULL OR cidade = '')"""
    ) or {}

    return {
        "total_startups": total.get("total", 0),
        "total_ai_native": ai_native.get("total", 0),
        "total_com_recomendacao": com_recomendacao.get("total", 0),
        "score_fit_medio": round(float(score_medio.get("media", 0) or 0), 1),
        "ultimas_24h": ultimas_24h.get("total", 0),
        "distribuicao_setor": distribuicao_setor,
        "sem_email": sem_email.get("total", 0),
        "sem_cidade": sem_cidade.get("total", 0),
        "incompletas": incompletas.get("total", 0)
    }
